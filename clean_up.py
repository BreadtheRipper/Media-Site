import os
from app import create_app, db  # Import the create_app function
from app.models import Upload  # Import your Upload model

def clean_up_db():
    uploads = Upload.query.all()
    removed_count = 0
    
    for upload in uploads:
        # Determine the path based on file type
        if upload.filename.lower().endswith(('png', 'jpg', 'jpeg', 'gif')):
            file_path = os.path.join(app.config['UPLOAD_FOLDER_IMAGES'], upload.filename)
        elif upload.filename.lower().endswith(('mp4', 'mov', 'avi')):
            file_path = os.path.join(app.config['UPLOAD_FOLDER_VIDEOS'], upload.filename)
        else:
            continue  # Skip unsupported files
        
        # Check if the file exists
        if not os.path.exists(file_path):
            # If file doesn't exist, delete the record
            db.session.delete(upload)
            removed_count += 1

    db.session.commit()
    return removed_count

if __name__ == "__main__":
    # Set up the application context
    app = create_app()  # Create the app instance
    with app.app_context():
        removed = clean_up_db()
        print(f"Removed {removed} broken entries from the database.")
