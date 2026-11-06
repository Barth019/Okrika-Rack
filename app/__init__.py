
from flask import Flask, render_template

from app.config import Config
from app.models import db
from app.auth import auth_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Configure secure session cookies.
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SECURE"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    # Initialize the database.
    db.init_app(app)

    # Register authentication routes.
    app.register_blueprint(auth_bp)

    @app.route("/")
    def home():
        return render_template("index.html")

    # Create database tables if they do not exist.
    with app.app_context():
        db.create_all()

    return app
