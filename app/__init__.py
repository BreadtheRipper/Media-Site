from flask import Flask,g, logging, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_cors import CORS
from .discord_bot import run_bot
import os, logging, threading, time, cProfile

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()

logging.basicConfig(level=logging.DEBUG)

def create_app():
    app = Flask(__name__, static_folder='../instance/static', static_url_path='/static')

    # Configure the database URI
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(app.instance_path, "site.db")}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.urandom(24).hex()

    # Define the upload folders
    app.config['UPLOAD_FOLDER_IMAGES'] = os.path.join(app.instance_path, 'static/images')
    app.config['UPLOAD_FOLDER_VIDEOS'] = os.path.join(app.instance_path, 'static/videos')
    app.config['UPLOAD_FOLDER_THUMBNAILS'] = os.path.join(app.instance_path, 'static/thumbnails')
    
    app.config['DISCORD_BOT_TOKEN'] = os.environ.get('DISCORD_BOT_TOKEN')  # Store token as an environment variable
    
    # Create the directories if they don't exist
    os.makedirs(app.config['UPLOAD_FOLDER_IMAGES'], exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER_VIDEOS'], exist_ok=True)

    # Initialize extensions with the app
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'  # Or whatever the name of your login route is
    CORS(app, resources={r"/stream_video/*": {"origins": "*"}})
    
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    
    @app.before_request
    def start_timer():
        g.start = time.time()

    @app.after_request
    def log_response(response):
        duration = time.time() - g.start
        logger.info(f"{request.method} {request.path} - {response.status} - {duration:.2f}s")
        return response
    
    def profile_app():
        cProfile.run('app.run()')

    #threading.Thread(target=run_bot).start()
    
    # Register the single Blueprint
    from .routes import auth_bp  # or main_bp if you rename it
    app.register_blueprint(auth_bp)

    return app
