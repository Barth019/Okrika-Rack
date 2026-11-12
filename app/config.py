
# Application configuration

import os

from dotenv import load_dotenv

load_dotenv()


def get_database_url():
    """Return a database URL compatible with SQLAlchemy and Psycopg 3."""

    database_url = os.environ.get(
        "DATABASE_URL",
        "sqlite:///thrift.db",
    ).strip()

    # Render may provide PostgreSQL URLs using the older postgres:// scheme.
    if database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://",
            "postgresql+psycopg://",
            1,
        )

    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1,
        )

    return database_url


class Config:
    APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()
    SECRET_KEY = os.environ["SECRET_KEY"].strip()
    TOKEN_ENCRYPTION_KEY = os.environ["TOKEN_ENCRYPTION_KEY"].strip()

    SQLALCHEMY_DATABASE_URI = get_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Check database connections before reusing them.
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
    }

    BUFFER_CLIENT_ID = os.environ["BUFFER_CLIENT_ID"].strip()
    BUFFER_CLIENT_SECRET = os.environ["BUFFER_CLIENT_SECRET"].strip()
    BUFFER_REDIRECT_URI = os.environ["BUFFER_REDIRECT_URI"].strip()

    CLOUDINARY_CLOUD_NAME = os.environ["CLOUDINARY_CLOUD_NAME"].strip()
    CLOUDINARY_API_KEY = os.environ["CLOUDINARY_API_KEY"].strip()
    CLOUDINARY_API_SECRET = os.environ["CLOUDINARY_API_SECRET"].strip()

    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
