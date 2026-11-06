
from flask import Flask, render_template

from app.config import Config
from app.models import db


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Connect SQLAlchemy to this Flask application.
    db.init_app(app)

    # Register the homepage.
    @app.route("/")
    def home():
        return render_template("index.html")

    # Create any database tables that do not already exist.
    with app.app_context():
        db.create_all()

    return app
