
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from email.utils import parseaddr
import re

from app.models import (
    db,
    Seller,
    BufferConnection,
    Item,
    ScheduledPost,
)

accounts_bp = Blueprint("accounts", __name__)

def normalize_whatsapp_number(number):
    """Validate and normalize a WhatsApp number to international digits."""

    if not number:
        return None

    cleaned = re.sub(r"[\s().-]", "", number.strip())

    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]

    if cleaned.startswith("0") and len(cleaned) == 11:
        cleaned = "234" + cleaned[1:]

    elif cleaned.startswith("+"):
        cleaned = cleaned[1:]

    if not cleaned.isdigit() or not 8 <= len(cleaned) <= 15:
        raise ValueError(
            "Enter a valid WhatsApp number with its country code."
        )

    if cleaned.startswith("0"):
        raise ValueError(
            "Include your international country code."
        )

    return cleaned


@accounts_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirmation = request.form.get("confirm_password", "")

        if not email or not password:
            flash("Please provide your email and password.", "error")
            return redirect(url_for("accounts.register"))

        parsed_name, parsed_email = parseaddr(email)

        if (
            parsed_name
            or parsed_email != email
            or email.count("@") != 1
            or "." not in email.split("@")[-1]
            or any(character.isspace() for character in email)
        ):
            flash("Please enter a valid email address.", "error")
            return redirect(url_for("accounts.register"))

        if len(password) < 12:
            flash(
                "Your password must contain at least 12 characters.",
                "error",
            )
            return redirect(url_for("accounts.register"))

        if password != confirmation:
            flash("Your passwords do not match.", "error")
            return redirect(url_for("accounts.register"))

        existing_seller = Seller.query.filter_by(email=email).first()

        if existing_seller:
            flash("An account with this email already exists.", "error")
            return redirect(url_for("accounts.register"))

        seller = Seller(
            email=email,
            password_hash=generate_password_hash(password),
        )

        db.session.add(seller)
        db.session.commit()

        login_user(seller)

        flash(
            "Your Okrika-Rack account has been created successfully!",
            "success",
        )
        return redirect(url_for("home"))

    return render_template("register.html")


@accounts_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        seller = Seller.query.filter_by(email=email).first()

        if seller is None or not check_password_hash(
            seller.password_hash, password
        ):
            flash("Invalid email or password.", "error")
            return redirect(url_for("accounts.login"))

        login_user(seller)

        flash("Welcome back!", "success")
        return redirect(url_for("home"))

    return render_template("login.html")


@accounts_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("accounts.login"))

@accounts_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        whatsapp_number = request.form.get(
            "whatsapp_number", ""
        ).strip()

        try:
            current_user.whatsapp_number = normalize_whatsapp_number(
                whatsapp_number
            )

            db.session.commit()

            if current_user.whatsapp_number:
                flash(
                    "Your WhatsApp number has been saved successfully!",
                    "success",
                )
            else:
                flash(
                    "Your WhatsApp number has been removed.",
                    "success",
                )

            return redirect(url_for("accounts.settings"))

        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "error")

    buffer_connection = BufferConnection.query.filter_by(
        seller_id=current_user.id
    ).first()

    return render_template(
        "settings.html",
        buffer_connection=buffer_connection,
    )


@accounts_bp.route("/dashboard")
@login_required
def dashboard():
    seller_id = current_user.id

    buffer_connection = BufferConnection.query.filter_by(
        seller_id=seller_id
    ).first()

    inventory_query = Item.query.filter_by(
        seller_id=seller_id,
        is_deleted=False,
    )

    post_query = ScheduledPost.query.filter_by(
        seller_id=seller_id
    )

    inventory_stats = {
        "total": inventory_query.count(),
        "available": inventory_query.filter_by(
            availability="available"
        ).count(),
        "sold": inventory_query.filter_by(
            availability="sold"
        ).count(),
    }

    post_stats = {
        "total": post_query.count(),
        "pending": post_query.filter_by(status="pending").count(),
        "scheduled": post_query.filter_by(status="scheduled").count(),
        "published": post_query.filter_by(status="published").count(),
        "cancelled": post_query.filter_by(status="cancelled").count(),
        "failed": post_query.filter_by(status="failed").count(),
    }

    recent_posts = (
        post_query
        .order_by(ScheduledPost.created_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "dashboard.html",
        buffer_connection=buffer_connection,
        inventory_stats=inventory_stats,
        post_stats=post_stats,
        recent_posts=recent_posts,
    )
