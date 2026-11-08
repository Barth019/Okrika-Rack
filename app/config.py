# Reads settings from the environment so no secrets live in the code.

import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    TOKEN_ENCRYPTION_KEY = os.environ["TOKEN_ENCRYPTION_KEY"].strip()
    SECRET_KEY = os.environ["SECRET_KEY"]
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///thrift.db")
    BUFFER_CLIENT_ID = os.environ["BUFFER_CLIENT_ID"].strip()
    BUFFER_CLIENT_SECRET = os.environ["BUFFER_CLIENT_SECRET"].strip()
    BUFFER_REDIRECT_URI = os.environ["BUFFER_REDIRECT_URI"].strip()
    CLOUDINARY_CLOUD_NAME = os.environ["CLOUDINARY_CLOUD_NAME"].strip()
    CLOUDINARY_API_KEY = os.environ["CLOUDINARY_API_KEY"].strip()
    CLOUDINARY_API_SECRET = os.environ["CLOUDINARY_API_SECRET"].strip()
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024