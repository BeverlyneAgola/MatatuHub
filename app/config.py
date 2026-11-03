import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Daraja Config
    MPESA_CONSUMER_KEY = os.getenv("KEY")
    MPESA_CONSUMER_SECRET = os.getenv("SECRET")
    MPESA_SHORTCODE = os.getenv("code")
    MPESA_PASSKEY = os.getenv("PASSKEY")
    MPESA_CALLBACK_URL = os.getenv("CALLBACK")
    MPESA_PASSWORD = os.getenv("PASSWORD")
    MPESA_OAUTH_URL = os.getenv("O_URL")
    MPESA_STK_URL = os.getenv("S_URL")
    MPESA_TIMESTAMP = os.getenv("TIMESTAMP")