
import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from flask import Blueprint, current_app, redirect, session

from app.models import db, OAuthTransaction
from app.security import encrypt_token


auth_bp = Blueprint("auth", __name__)

BUFFER_AUTH_URL = "https://auth.buffer.com/auth"

BUFFER_SCOPES = [
    "account:read",
    "posts:read",
    "posts:write",
    "offline_access",
]


def generate_pkce_pair():
    """Generate a PKCE verifier and its SHA-256 challenge."""

    verifier = secrets.token_urlsafe(64)

    digest = hashlib.sha256(verifier.encode("ascii")).digest()

    challenge = (
        base64.urlsafe_b64encode(digest)
        .rstrip(b"=")
        .decode("ascii")
    )

    return verifier, challenge


@auth_bp.route("/connect/buffer")
def connect_buffer():
    """Start the Buffer OAuth authorization process."""

    # Generate a unique state value for this authorization attempt.
    state = secrets.token_urlsafe(32)

    # Generate the PKCE verifier and challenge.
    verifier, challenge = generate_pkce_pair()

    # Store the verifier encrypted in our database.
    transaction = OAuthTransaction(
        state=state,
        code_verifier_encrypted=encrypt_token(verifier),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )

    db.session.add(transaction)
    db.session.commit()

    # Keep the state in the signed Flask session for callback verification.
    session["buffer_oauth_state"] = state

    # Build Buffer's authorization request.
    params = {
        "client_id": current_app.config["BUFFER_CLIENT_ID"],
        "redirect_uri": current_app.config["BUFFER_REDIRECT_URI"],
        "response_type": "code",
        "scope": " ".join(BUFFER_SCOPES),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "prompt": "consent",
    }

    authorization_url = f"{BUFFER_AUTH_URL}?{urlencode(params)}"

    return redirect(authorization_url)
