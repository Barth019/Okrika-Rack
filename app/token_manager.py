from datetime import timedelta, timezone

from flask import current_app

from app.models import db, utc_now
from app.security import encrypt_token, decrypt_token
from app.buffer_client import refresh_access_token


def refresh_buffer_connection(connection):
    """Refresh and securely persist a seller's Buffer tokens."""

    # Decrypt the currently stored refresh token.
    old_refresh_token = decrypt_token(
        connection.refresh_token_encrypted
    )

    # Request a new access token and refresh token from Buffer.
    tokens = refresh_access_token(
        old_refresh_token,
        current_app.config,
    )

    # Encrypt both new tokens before storing them.
    connection.access_token_encrypted = encrypt_token(
        tokens["access_token"]
    )

    connection.refresh_token_encrypted = encrypt_token(
        tokens["refresh_token"]
    )

    # Update the access token expiration time.
    connection.token_expires_at = (
        utc_now() + timedelta(seconds=tokens["expires_in"])
    )

    try:
        db.session.commit()

    except Exception:
        db.session.rollback()
        raise

    return connection

def get_valid_buffer_access_token(connection):
    """Return a valid access token, refreshing it when necessary."""

    now = utc_now()
    expires_at = connection.token_expires_at

    # SQLite may return timezone-naive datetimes.
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    # Reuse the existing token if it has more than five minutes left.
    if expires_at and expires_at > now + timedelta(minutes=5):
        return decrypt_token(connection.access_token_encrypted)

    # Otherwise, refresh and persist the replacement tokens.
    refreshed_connection = refresh_buffer_connection(connection)

    return decrypt_token(
        refreshed_connection.access_token_encrypted
    )