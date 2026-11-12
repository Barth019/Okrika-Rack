
from cryptography.fernet import Fernet


def validate_production_config(config):
    """Validate required configuration before production startup."""

    required_settings = [
        "SECRET_KEY",
        "TOKEN_ENCRYPTION_KEY",
        "BUFFER_CLIENT_ID",
        "BUFFER_CLIENT_SECRET",
        "BUFFER_REDIRECT_URI",
        "CLOUDINARY_CLOUD_NAME",
        "CLOUDINARY_API_KEY",
        "CLOUDINARY_API_SECRET",
    ]

    missing = [
        setting
        for setting in required_settings
        if not str(config.get(setting, "")).strip()
    ]

    if missing:
        raise RuntimeError(
            "Missing required production settings: "
            + ", ".join(missing)
        )

    secret_key = config["SECRET_KEY"]

    if len(secret_key) < 32:
        raise RuntimeError(
            "SECRET_KEY must contain at least 32 characters."
        )

    try:
        Fernet(config["TOKEN_ENCRYPTION_KEY"].encode("utf-8"))
    except (ValueError, TypeError):
        raise RuntimeError(
            "TOKEN_ENCRYPTION_KEY is not a valid Fernet key."
        ) from None

    database_url = config.get("SQLALCHEMY_DATABASE_URI", "")

    if not database_url.startswith("postgresql+psycopg://"):
        raise RuntimeError(
            "Production requires PostgreSQL using the Psycopg 3 driver."
        )
