import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()   


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://postgres:ahMed2005%23@localhost:5432/ClickCv'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=1)
    UPLOAD_FOLDER = "app/static/uploads"
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")