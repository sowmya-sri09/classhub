import os

# Base directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')

# Ensure the data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# Database path
DB_PATH = os.path.join(DATA_DIR, 'classhub.db')

# App secret key (for sessions)
SECRET_KEY = 'supersecretkey123'

# Upload folder for memes
UPLOAD_FOLDER = os.path.join('static', 'memes')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Allowed extensions for uploads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
