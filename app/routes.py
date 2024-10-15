import os, re, uuid, subprocess, threading, logging, discord, asyncio, requests
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask import abort, current_app, copy_current_request_context, Flask, Response, g, send_file
from flask_login import login_required, current_user, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from . import db, login_manager
from .models import User, Upload
from .discord_bot import bot, send_embed
from datetime import datetime

app= Flask(__name__)

# Create a Blueprint for your routes
auth_bp = Blueprint('auth', __name__)

# Global dictionary to hold encoding progress for each job
encoding_lock = threading.Lock()
encoding_progress = {}

# Define allowed file extensions
ALLOWED_EXTENSIONS_IMAGES = {'png', 'jpg', 'jpeg', 'gif'}
ALLOWED_EXTENSIONS_VIDEOS = {'mp4', 'mov', 'avi'}

# Combine them into a single variable for the template
ALLOWED_EXTENSIONS = {
    'images': ALLOWED_EXTENSIONS_IMAGES,
    'videos': ALLOWED_EXTENSIONS_VIDEOS
}

def init_app(app):
    """Initialize routes with the given app instance."""
    app.register_blueprint(auth_bp)  # Register the blueprint for routes

# Function to check if a file has an allowed extension
def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def encode_video_and_save(input_path, output_path, job_id, title, user_id):
    global encoding_progress

    with encoding_lock:
        encoding_progress[job_id] = 0  # Initialize progress to 0%

    command = [
        'ffmpeg', '-stats', '-i', input_path, '-c:v', 'h264_nvenc',
        '-preset', 'slow', '-profile:v', 'high', '-tune', 'hq',
        '-rc', 'vbr', '-b:v', '10M', '-maxrate', '10M', '-bufsize', '20M',
        '-c:a', 'aac', '-b:a', '192k', '-movflags', 'faststart', '-y', output_path
    ]

    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except Exception as e:
        logging.error(f"Error starting encoding process: {e}")
        return  # Exit if subprocess fails to start

    regex = re.compile(r'time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})')
    duration_regex = re.compile(r'Duration: (\d{2}):(\d{2}):(\d{2})\.(\d{2})')

    duration = None
    while True:
        output = process.stderr.readline()
        if output == '' and process.poll() is not None:
            break  # Exit loop if no more output and process has finished

        if output:
            logging.debug(f"FFmpeg output: {output.strip()}")

            # Try to extract duration early on
            if duration is None:
                duration_output = duration_regex.search(output)
                if duration_output:
                    hours = int(duration_output.group(1))
                    minutes = int(duration_output.group(2))
                    seconds = int(duration_output.group(3))
                    milliseconds = int(duration_output.group(4))
                    duration = hours * 3600 + minutes * 60 + seconds + milliseconds / 100
                    logging.debug(f"Extracted total duration: {duration} seconds")
            
            # Continue if we can calculate progress
            if duration:
                match = regex.search(output)
                if match:
                    # Extract current time from the output
                    hours = int(match.group(1))
                    minutes = int(match.group(2))
                    seconds = int(match.group(3))
                    milliseconds = int(match.group(4))
                    current_time = hours * 3600 + minutes * 60 + seconds + milliseconds / 100

                    logging.debug(f"Extracted current time: {current_time} seconds")

                    if duration > 0:
                        progress = (current_time / duration) * 100
                        progress = min(progress, 100)  # Cap the progress at 100%
                        logging.debug(f"Current time: {current_time}, Duration: {duration}, Progress calculated: {progress}%")
                        with encoding_lock:
                            encoding_progress[job_id] = int(progress)  # Update progress
                            logging.debug(f"Job ID: {job_id}, Progress updated: {encoding_progress[job_id]}%")
            else:
                logging.debug(f"Duration not available yet.")

    process.wait()  # Wait for the FFmpeg process to finish

    with encoding_lock:
        del encoding_progress[job_id]

    if process.returncode == 0:
        try:
            logging.debug(f"Current user ID: {user_id}")  # Corrected to use user_id parameter
            with current_app.app_context():
                delete_and_save(input_path, output_path, title, user_id)
                generate_thumbnail(output_path)  # Generate thumbnail after encoding
        except Exception as e:
            logging.error(f"Error in delete_and_save: {e}")
    else:
        logging.error(f"Encoding failed for job ID: {job_id} with return code: {process.returncode}")

def delete_and_save(input_path, output_path, title, user_id):
    logging.debug(f"Active app context: {current_app.name}")  # Log current app name
    logging.debug(f"Current app: {current_app}")
    #logging.debug(f"SQLAlchemy bound to app: {db.app}")  # Ensure db is bound to the current app context

    try:
        if os.path.exists(input_path):
            os.remove(input_path)
            logging.debug(f"Deleted original video: {input_path}")
        else:
            logging.debug(f"Original video not found for deletion: {input_path}")

        # Save the new upload info in the database
        new_upload = Upload(title=title, filename=os.path.basename(output_path), user_id=user_id)
        db.session.add(new_upload)
        db.session.commit()
        logging.debug(f"Upload info saved for: {os.path.basename(output_path)}")


    except Exception as e:
        logging.error(f"Error deleting original video or saving upload info: {e}")
        
def generate_thumbnail(output_path):
    thumbnail_path = os.path.join(current_app.config['UPLOAD_FOLDER_THUMBNAILS'], os.path.basename(output_path).replace('.mp4', '.jpg'))
    timestamp = "00:00:01"  # Adjust this to capture a different time frame (01 second into the video)

    command = [
        'ffmpeg', '-i', output_path, '-ss', timestamp, '-vframes', '1',
        '-vf', 'scale=480:-1', '-y', thumbnail_path
    ]

    try:
        subprocess.run(command, check=True)
        logging.debug(f"Thumbnail generated at: {thumbnail_path}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error generating thumbnail: {e}")


def clean_filename(filename):
    # Remove leading and trailing spaces
    filename = filename.strip()
    # Replace spaces with underscores
    filename = filename.replace(' ', '_')
    # Remove or replace unwanted characters
    filename = re.sub(r'[^\w\-_\.]', '', filename)  # Only allow alphanumeric, underscores, dashes, and dots
    return filename

def get_upload_by_id(upload_id):
    return Upload.query.get(upload_id)

def exists(file_url):
    response = requests.head(file_url)
    return response.status_code == 200

def delete_upload_from_db(upload_id):
    upload = get_upload_by_id(upload_id)  # Assuming this function retrieves the upload
    if upload:
        try:
            db.session.delete(upload)  # Assuming you're using SQLAlchemy
            db.session.commit()
            return True
        except Exception as e:
            logging.error(f"Error deleting upload from database: {e}")
            db.session.rollback()  # In case of any issue
            return False
    return False

@app.before_request
def log_request_info():
    logging.basicConfig(level=logging.INFO)
    logging.info('Request Path: %s', request.path)

# User loader for Flask-Login (required)
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Route: Home (protected, login required)
@auth_bp.route('/') 
def home():
    logging.debug("Index route hit")  # Debugging line
    return redirect(url_for('auth.gallery'))

# Route: Registration
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check if the username already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'danger')
            return redirect(url_for('auth.register'))

        # Hash the password
        password_hash = generate_password_hash(password)

        # Create a new user and add to the database
        new_user = User(username=username, password_hash=password_hash)
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')

# Route: Login
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check if the user exists
        user = User.query.filter_by(username=username).first()

        if not user:
            flash('The account does not exist. Please register first.', 'danger')
            return redirect(url_for('auth.login'))

        if check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('auth.gallery'))  # Redirect to the gallery
        else:
            flash('Invalid credentials', 'danger')
            return redirect(url_for('auth.login'))

    return render_template('login.html')

# Define allowed file extensions
ALLOWED_EXTENSIONS_IMAGES = {'png', 'jpg', 'jpeg', 'gif'}
ALLOWED_EXTENSIONS_VIDEOS = {'mp4', 'mov', 'avi'}

# Route: File Upload
@auth_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_file():
    if request.method == 'POST':
        title = request.form['title']
        file = request.files['file']
        logging.debug(f"Uploading file: {file.filename} with title: {title}")

        if file and allowed_file(file.filename, ALLOWED_EXTENSIONS_IMAGES.union(ALLOWED_EXTENSIONS_VIDEOS)):
            original_filename = file.filename
            clean_name = clean_filename(original_filename)
            ext = clean_name.rsplit('.', 1)[1].lower()

            random_filename = f"{uuid.uuid4().hex}.{ext}"
            logging.debug(f"Generated random filename: {random_filename}")

            try:
                if ext in ALLOWED_EXTENSIONS_IMAGES:
                    save_path = os.path.join(current_app.config['UPLOAD_FOLDER_IMAGES'], random_filename)
                    file.save(save_path)  # Save the file
                    # Save the new upload info in the database
                    new_upload = Upload(title=title, filename=os.path.basename(save_path), user_id= current_user.id)
                    db.session.add(new_upload)
                    db.session.commit()
                    logging.debug(f"Upload info saved for: {os.path.basename(save_path)}")
                    logging.debug(f"File saved at: {save_path}")
                    
                    flash('Image uploaded successfully!', 'success')
                    return jsonify({'message': 'Image uploaded successfully'})  # Redirect or return JSON as needed

                else:
                    save_path = os.path.join(current_app.config['UPLOAD_FOLDER_VIDEOS'], random_filename)
                    file.save(save_path)  # Save the video file
                    logging.debug(f"File saved at: {save_path}")

                    encoded_save_path = os.path.join(current_app.config['UPLOAD_FOLDER_VIDEOS'], f"{uuid.uuid4().hex}.mp4")
                    job_id = str(uuid.uuid4())  # Unique job ID for this encoding process

                    @copy_current_request_context
                    def async_encode():
                        encode_video_and_save(save_path, encoded_save_path, job_id, title, current_user.id)

                    threading.Thread(target=async_encode).start()  # Start encoding in a separate thread
                    logging.debug(f"Started encoding for job ID: {job_id}")

                    flash('Video uploaded successfully!', 'success')
                    return jsonify({'job_id': job_id})  # Redirect or return JSON as needed

            except Exception as e:
                logging.error(f"Error during upload process: {e}")
                flash('An error occurred during upload. Please try again.', 'danger')

        else:
            flash('Invalid file type!', 'danger')

    return render_template('upload.html')

# Route: Gallery
@auth_bp.route('/gallery')
@login_required
def gallery():
    uploads = Upload.query.filter_by(user_id=current_user.id).all()
    return render_template('gallery.html', uploads=uploads)

# Route: Progress check for encoding
@auth_bp.route('/encoding_progress/<job_id>', methods=['GET'])
@login_required
def get_encoding_progress(job_id):
    with encoding_lock:
        progress = encoding_progress.get(job_id, None)  # Get the progress for the job ID
    
    # If progress is None, it means the job is complete or doesn't exist
    if progress is None:
        logging.debug(f"Job {job_id} completed")
        response = jsonify({'progress': 100, 'status': 'completed'})  # Return completed status
    else:
        logging.debug(f"Job {job_id} progress: {progress}%")
        response = jsonify({'progress': progress, 'status': 'in_progress'})  # Return current progress
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@auth_bp.route('/share_discord', methods=['POST'])
def share_discord():
    data = request.get_json()

    uploader_name = data.get('uploader_name')
    discord_channel_id = data.get('discord_channel_id')
    upload_id = data.get('upload_id')

    # Assuming you have a way to query uploads from your database
    upload = get_upload_by_id(upload_id)  # Replace with actual query logic

    if not upload:
        return jsonify({'error': 'Upload not found'}), 404

    # Media details for the embed
    media_title = upload.title

    # Determine the media URL based on the file type
    if upload.filename.endswith(('.png', '.jpg', '.jpeg', '.gif')):
        media_url = url_for('static', filename='images/' + upload.filename, _external=True, _scheme='https')
        video_url = None  # No video URL for images
    elif upload.filename.endswith(('.mp4', '.mov', '.avi')):  # Include other video formats if necessary
        media_url = url_for('static', filename='thumbnails/' + upload.filename.replace('.mp4', '.jpg'), _external=True, _scheme='https')
        video_url = url_for('auth.stream_video', filename=upload.filename, _external=True, _scheme='https')
    else:
        return jsonify({'error': 'Unsupported file type'}), 400

    # Create the Discord embed
    embed = discord.Embed(
        title=media_title,
        description=f"Uploaded by {uploader_name}",
        color=0x7289da
    )

    # If it's an image, set it as a thumbnail
    if media_url:
        embed.set_image(url=media_url)

    # Use `asyncio.run_coroutine_threadsafe` to call send_embed directly
    asyncio.run_coroutine_threadsafe(
        send_embed(discord_channel_id, embed, video_url),  # Pass the embed and video URL
        bot.loop  # Make sure this is the bot's event loop
    )

    return jsonify({'message': 'Embed is being sent to Discord'}), 200


@auth_bp.route('/generate_share_token/<int:upload_id>', methods=['POST'])
def generate_share_token(upload_id):
    upload = Upload.query.get(upload_id)
    if upload is None:
        return jsonify({'error': 'Upload not found'}), 404

    if upload.share_token is None:
        # Generate a new unique share token
        upload.share_token = str(uuid.uuid4())
        db.session.commit()

    return jsonify({'share_token': upload.share_token})

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

@auth_bp.route('/media/<share_token>')
def view_shared_media(share_token):
    # Log the received share token
    print(f"Received share token: {share_token}")

    # Query the database for the upload associated with the share_token
    upload = Upload.query.filter_by(share_token=share_token).first()

    if not upload:
        # Log if the upload is not found
        print(f"No upload found for share token: {share_token}")
        abort(404)

    # Log if the upload is found
    print(f"Found upload: {upload.filename}")

    # Query the user associated with the upload
    user = User.query.get(upload.user_id)
    
    # Log the username
    print(f"Upload belongs to: {user.username}")
    
    thumbnail = upload.filename.replace('.mp4', '.jpg')
    print(f"Retreived thumbnail name: {thumbnail}")
    
    # Inside your view_shared_media function
    current_time = datetime.now().timestamp()

    # Render the HTML page and pass the necessary context to the template
    return render_template(
        'view_shared_media.html',
        upload=upload,
        username=user.username,
        allowed_extensions=ALLOWED_EXTENSIONS,
        current_time=current_time,
        thumbnail=thumbnail
    )
    
# Route: Delete Upload
@auth_bp.route('/delete_upload/<int:upload_id>', methods=['POST'])
@login_required
def delete_upload(upload_id):
    upload = get_upload_by_id(upload_id)

    if upload:
        try:
            # Determine the folder based on file type (videos or images)
            if upload.filename.endswith(('.png', '.jpg', '.jpeg', '.gif')):
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER_IMAGES'], upload.filename)
                thumbnail_path = None  # No thumbnail for images
            elif upload.filename.endswith(('.mp4', '.mov', '.avi')):  # Add other video formats if necessary
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER_VIDEOS'], upload.filename)
                # Generate the thumbnail path based on the video filename
                thumbnail_filename = upload.filename.replace('.mp4', '.jpg')  # Adjust this as needed for other formats
                thumbnail_path = os.path.join(current_app.config['UPLOAD_FOLDER_THUMBNAILS'], thumbnail_filename)
            else:
                flash('Unsupported file type.', 'danger')
                return redirect(url_for('auth.gallery'))
            
            # Delete the file from the server if it exists
            if os.path.exists(file_path):
                os.remove(file_path)
                logging.debug(f"Deleted file: {file_path}")
            else:
                flash('File not found on server.', 'warning')

            # Delete the thumbnail if it exists
            if thumbnail_path and os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
                logging.debug(f"Deleted thumbnail: {thumbnail_path}")
            elif thumbnail_path:
                flash('Thumbnail not found on server.', 'warning')

            # Delete the entry from the database
            if delete_upload_from_db(upload_id):
                flash('Upload deleted successfully.', 'success')
            else:
                flash('Failed to delete upload from database.', 'danger')

        except Exception as e:
            logging.error(f"Error deleting upload: {e}")
            flash('An error occurred while deleting the upload.', 'danger')
    else:
        flash('Upload not found.', 'warning')

    return redirect(url_for('auth.gallery'))


@auth_bp.route('/static/videos/<path:filename>', methods=['GET'])
def serve_video(filename):
    try:
        # Get the upload folder path from the app configuration
        upload_folder_videos = current_app.config['UPLOAD_FOLDER_VIDEOS']
        return send_from_directory(upload_folder_videos, filename, mimetype='video/mp4')
    except Exception as e:
        # Log the error and return a 404 if the file isn't found
        current_app.logger.error(f"Error serving video {filename}: {e}")
        abort(404)

@auth_bp.route('/stream_video/<path:filename>')
def stream_video(filename):
    # Log the full request information for debugging
    print(f"Request URL: {request.url}")
    print(f"Request Headers: {request.headers}")
    print(f"Request Arguments: {request.args}")
    print(f"Referer: {request.referrer}")

    video_path = os.path.join(current_app.config['UPLOAD_FOLDER_VIDEOS'], filename)

    if os.path.exists(video_path):
        file_size = os.path.getsize(video_path)
        range_header = request.headers.get('Range', None)
        byte1, byte2 = 0, None

        if range_header:
            byte_range = range_header.replace('bytes=', '').split('-')
            byte1 = int(byte_range[0]) if byte_range[0] else 0
            if len(byte_range) == 2 and byte_range[1]:
                byte2 = int(byte_range[1])
            else:
                byte2 = file_size - 1
        else:
            byte2 = file_size - 1

        length = (byte2 - byte1) + 1

        # Chunk size reduction for testing
        chunk_size = 256 * 1024  # 256 KB chunks

        def generate():
            with open(video_path, 'rb') as f:
                f.seek(byte1)
                remaining_length = length
                while remaining_length > 0:
                    chunk = f.read(min(chunk_size, remaining_length))
                    if not chunk:
                        break
                    yield chunk
                    remaining_length -= len(chunk)

        status_code = 206 if range_header else 200
        response = Response(generate(), status=status_code, mimetype='video/mp4')
        
        # Headers adjustments
        response.headers['Content-Disposition'] = 'inline'  # Important for inline video display
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Content-Length'] = str(length)
        response.headers['Content-Range'] = f'bytes {byte1}-{byte2}/{file_size}'
        response.headers['Cache-Control'] = 'no-cache'  # Disable caching to avoid stale partial requests
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Range, Content-Type, Authorization'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'

        return response

    print(f"File does not exist: {video_path}")
    return Response("File not found", status=404)

# Route: Logout
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('auth.login'))

@app.route('/test-static/<path:filename>')
def test_static(filename):
    return send_from_directory(app.static_folder, filename)
    
@auth_bp.route('/test_token')
def test_token():
    token = current_app.config.get('DISCORD_BOT_TOKEN')
    return f"Discord Bot Token: {token}"
