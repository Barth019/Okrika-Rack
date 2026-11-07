from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from email.utils import parseaddr

from app.models import db, Seller, BufferConnection

accounts_bp = Blueprint("accounts", __name__)


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
            flash("Your password must contain at least 12 characters.", "error")
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

        flash("Your Okrika-Rack account has been created successfully!", "success")
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


@accounts_bp.route("/dashboard")
@login_required
def dashboard():
    buffer_connection = BufferConnection.query.filter_by(
        seller_id=current_user.id
    ).first()

    return render_template(
        "dashboard.html",
        buffer_connection=buffer_connection,
    )