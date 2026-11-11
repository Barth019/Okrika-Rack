from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utc_now():
    return datetime.now(timezone.utc)


class Seller(UserMixin, db.Model):
    """Represents an individual thrift seller using Okrika-Rack."""

    __tablename__ = "sellers"

    id = db.Column(db.Integer, primary_key=True)

    email = db.Column(
        db.String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    buffer_connections = db.relationship(
        "BufferConnection",
        back_populates="seller",
    )
    items = db.relationship(
        "Item",
        back_populates="seller",
        cascade="all, delete-orphan",
    )
    scheduled_posts = db.relationship(
        "ScheduledPost",
        back_populates="seller",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Seller {self.email}>"

class Item(db.Model):
    """Represents an individual thrift item in a seller's inventory."""

    __tablename__ = "items"

    __table_args__ = (
        db.CheckConstraint(
            "price >= 0",
            name="ck_items_price_nonnegative",
        ),
        db.CheckConstraint(
            "availability IN ('available', 'sold')",
            name="ck_items_availability",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    seller_id = db.Column(
        db.Integer,
        db.ForeignKey("sellers.id"),
        nullable=False,
        index=True,
    )

    seller = db.relationship(
        "Seller",
        back_populates="items",
    )

    scheduled_posts = db.relationship(
        "ScheduledPost",
        back_populates="item",
    )

    name = db.Column(
        db.String(150),
        nullable=False,
    )

    description = db.Column(
        db.Text,
        nullable=True,
    )
    image_url = db.Column(db.String(500), nullable=True)
    image_public_id = db.Column(db.String(255), nullable=True)

    price = db.Column(
        db.Numeric(10, 2),
        nullable=False,
    )

    size = db.Column(
        db.String(50),
        nullable=True,
    )

    condition = db.Column(
        db.String(30),
        nullable=False,
    )

    notes = db.Column(
        db.Text,
        nullable=True,
    )

    availability = db.Column(
        db.String(20),
        default="available",
        nullable=False,
        index=True,
    )

    is_deleted = db.Column(
    db.Boolean,
    default=False,
    nullable=False,
    index=True,
)

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    def __repr__(self):
        return f"<Item {self.name} - Seller {self.seller_id}>"


class BufferConnection(db.Model):
    """Stores a seller's connected Buffer account and encrypted tokens."""

    __tablename__ = "buffer_connections"

    id = db.Column(db.Integer, primary_key=True)

    seller_id = db.Column(
        db.Integer,
        db.ForeignKey("sellers.id"),
        nullable=True,
        index=True,
    )

    seller = db.relationship(
        "Seller",
        back_populates="buffer_connections",
    )

    buffer_account_id = db.Column(
        db.String(120),
        unique=True,
        nullable=False,
        index=True,
    )

    email = db.Column(db.String(255), nullable=True)
    display_name = db.Column(db.String(255), nullable=True)

    access_token_encrypted = db.Column(db.Text, nullable=False)
    refresh_token_encrypted = db.Column(db.Text, nullable=False)

    token_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    scopes = db.Column(db.Text, nullable=True)

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False,
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

    seller_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "sellers.id",
            name="fk_oauth_transactions_seller_id_sellers",
        ),
        nullable=True,
        index=True,
    )

    state = db.Column(
        db.String(128),
        unique=True,
        nullable=False,
        index=True,
    )

    code_verifier_encrypted = db.Column(db.Text, nullable=False)

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    expires_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
    )

    def __repr__(self):
        return f"<OAuthTransaction {self.id}>"

class ScheduledPost(db.Model):
    """Tracks a seller's scheduled social media posts."""

    __tablename__ = "scheduled_posts"

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('pending', 'scheduled', 'published', 'failed', 'cancelled')",
            name="ck_scheduled_posts_status",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    seller_id = db.Column(
        db.Integer,
        db.ForeignKey("sellers.id"),
        nullable=False,
        index=True,
    )

    item_id = db.Column(
        db.Integer,
        db.ForeignKey("items.id"),
        nullable=False,
        index=True,
    )

    buffer_connection_id = db.Column(
        db.Integer,
        db.ForeignKey("buffer_connections.id"),
        nullable=False,
        index=True,
    )

    buffer_channel_id = db.Column(
        db.String(120),
        nullable=False,
    )

    buffer_post_id = db.Column(
        db.String(120),
        nullable=True,
        unique=True,
    )

    caption = db.Column(
        db.Text,
        nullable=False,
    )

    scheduled_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    status = db.Column(
        db.String(20),
        default="pending",
        nullable=False,
        index=True,
    )

    error_message = db.Column(
        db.Text,
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    seller = db.relationship(
        "Seller",
        back_populates="scheduled_posts",
    )

    item = db.relationship(
        "Item",
        back_populates="scheduled_posts",
    )

    buffer_connection = db.relationship("BufferConnection")

    def __repr__(self):
        return f"<ScheduledPost {self.id} - {self.status}>"