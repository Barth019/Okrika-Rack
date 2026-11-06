
from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


def get_cipher():
    """Create an encryption tool using the key stored in .env."""
    key = current_app.config["TOKEN_ENCRYPTION_KEY"].encode()
    return Fernet(key)


def encrypt_token(token: str) -> str:
    """Encrypt a Buffer token before database storage."""
    if not token:
        raise ValueError("Cannot encrypt an empty token.")

    encrypted = get_cipher().encrypt(token.encode())
    return encrypted.decode()


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a previously encrypted Buffer token."""
    if not encrypted_token:
        raise ValueError("Cannot decrypt an empty token.")

    try:
        decrypted = get_cipher().decrypt(encrypted_token.encode())
        return decrypted.decode()
    except InvalidToken as exc:
        raise ValueError(
            "Token decryption failed. Check the encryption key."
        ) from exc
