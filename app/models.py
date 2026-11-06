
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utc_now():
    return datetime.now(timezone.utc)


class BufferConnection(db.Model):
    """Stores a seller's connected Buffer account and encrypted tokens."""

    __tablename__ = "buffer_connections"

    id = db.Column(db.Integer, primary_key=True)

    buffer_account_id = db.Column(
        db.String(120), unique=True, nullable=False, index=True
    )
    email = db.Column(db.String(255), nullable=True)
    display_name = db.Column(db.String(255), nullable=True)

    access_token_encrypted = db.Column(db.Text, nullable=False)
    refresh_token_encrypted = db.Column(db.Text, nullable=False)

    token_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    scopes = db.Column(db.Text, nullable=True)

    created_at = db.Column(
        db.DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    def __repr__(self):
        return f"<BufferConnection {self.buffer_account_id}>"


class OAuthTransaction(db.Model):
    """Temporarily stores data needed to complete Buffer OAuth securely."""

    __tablename__ = "oauth_transactions"

    id = db.Column(db.Integer, primary_key=True)

    state = db.Column(db.String(128), unique=True, nullable=False, index=True)
    code_verifier_encrypted = db.Column(db.Text, nullable=False)

    created_at = db.Column(
        db.DateTime(timezone=True), default=utc_now, nullable=False
    )
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)

    def __repr__(self):
        return f"<OAuthTransaction {self.id}>"
