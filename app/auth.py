
import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from flask_login import current_user, login_required

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    request,
    session,
    url_for,
)

from app.models import db, OAuthTransaction, BufferConnection
from app.security import encrypt_token, decrypt_token
from app.buffer_client import (
    exchange_authorization_code,
    get_buffer_account,
    BufferAPIError,
)


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


def is_transaction_expired(transaction):
    """Check expiry safely across SQLite and PostgreSQL."""

    expires_at = transaction.expires_at

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    return expires_at <= datetime.now(timezone.utc)


@auth_bp.route("/connect/buffer")
@login_required
def connect_buffer():
    """Start the Buffer OAuth authorization process."""

    state = secrets.token_urlsafe(32)
    verifier, challenge = generate_pkce_pair()

    transaction = OAuthTransaction(
        seller_id=current_user.id,
        state=state,
        code_verifier_encrypted=encrypt_token(verifier),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )

    db.session.add(transaction)
    db.session.commit()

    session["buffer_oauth_state"] = state

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


@auth_bp.route("/callback")
def buffer_callback():
    """Handle Buffer's OAuth callback and save the connection."""

    returned_state = session.get("buffer_oauth_state")
    callback_state = request.args.get("state", "")

    # Reject callbacks that did not originate from our session.
    if (
        not returned_state
        or not callback_state
        or not secrets.compare_digest(returned_state, callback_state)
    ):
        abort(400, description="Invalid OAuth state.")

    transaction = OAuthTransaction.query.filter_by(
        state=callback_state
    ).first()

    if transaction is None:
        abort(400, description="OAuth transaction not found or already used.")
            # Ensure the seller completing OAuth is the one who initiated it.
    if not current_user.is_authenticated:
        abort(401, description="Please log in before completing Buffer connection.")

    if transaction.seller_id != current_user.id:
        abort(403, description="This OAuth transaction belongs to another seller.")

    if is_transaction_expired(transaction):
        db.session.delete(transaction)
        db.session.commit()
        session.pop("buffer_oauth_state", None)

        flash("Your Buffer connection request expired. Please try again.", "error")
        return redirect(url_for("home"))

    # Decrypt the verifier before consuming the transaction.
    try:
        code_verifier = decrypt_token(
            transaction.code_verifier_encrypted
        )
    except ValueError:
        current_app.logger.exception(
            "Could not decrypt OAuth PKCE verifier."
        )
        abort(500, description="Could not complete Buffer authentication.")

    # Consume the transaction so the callback cannot be reused.
    db.session.delete(transaction)
    db.session.commit()
    session.pop("buffer_oauth_state", None)

    # Handle a user declining authorization.
    oauth_error = request.args.get("error")

    if oauth_error:
        flash("Buffer authorization was cancelled or denied.", "info")
        return redirect(url_for("home"))

    authorization_code = request.args.get("code")

    if not authorization_code:
        flash("Buffer did not return an authorization code.", "error")
        return redirect(url_for("home"))

    try:
        tokens = exchange_authorization_code(
            authorization_code,
            code_verifier,
            current_app.config,
        )

        account = get_buffer_account(tokens["access_token"])

        connection = BufferConnection.query.filter_by(
            buffer_account_id=account["id"]
        ).first()

        if connection is None:
            connection = BufferConnection(
                seller_id=current_user.id,
                buffer_account_id=account["id"],
            )
            db.session.add(connection)

        elif (
            connection.seller_id is not None
            and connection.seller_id != current_user.id
        ):
            raise PermissionError(
                "This Buffer account is already connected to another seller."
            )

        else:
            # An existing unowned connection can be claimed only through
            # this seller's authenticated Buffer authorization.
            connection.seller_id = current_user.id

        connection.email = account["email"]
        connection.access_token_encrypted = encrypt_token(
            tokens["access_token"]
        )
        connection.refresh_token_encrypted = encrypt_token(
            tokens["refresh_token"]
        )
        connection.token_expires_at = (
            datetime.now(timezone.utc)
            + timedelta(seconds=tokens["expires_in"])
        )
        connection.scopes = tokens.get("scope")

        db.session.commit()

    except BufferAPIError:
        db.session.rollback()
        current_app.logger.exception(
            "Buffer OAuth connection failed."
        )
        flash("We couldn't connect your Buffer account. Please try again.", "error")
        return redirect(url_for("home"))

    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Unexpected error while saving Buffer connection."
        )
        flash("Something went wrong while connecting Buffer.", "error")
        return redirect(url_for("home"))

    flash("Your Buffer account is connected successfully!", "success")
    return redirect(url_for("home"))
