from flask import Flask, render_template
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from app.items import items_bp
import cloudinary


from app.config import Config
from app.models import db, BufferConnection, Seller
from app.auth import auth_bp
from app.accounts import accounts_bp
from app.scheduler import scheduler_bp
from app.config_validation import validate_production_config


migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)
    if app.config.get("APP_ENV") == "production":
        validate_production_config(app.config)
    cloudinary.config(
        cloud_name=app.config["CLOUDINARY_CLOUD_NAME"],
        api_key=app.config["CLOUDINARY_API_KEY"],
        api_secret=app.config["CLOUDINARY_API_SECRET"],
        secure=True,
    )

    # Secure session cookies.
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SECURE"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    # Initialize extensions.
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "accounts.login"
    login_manager.login_message = "Please log in to access that page."

    @login_manager.user_loader
    def load_seller(seller_id):
        try:
            return db.session.get(Seller, int(seller_id))
        except (ValueError, TypeError):
            return None

    # Register application routes.
    app.register_blueprint(auth_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(items_bp)
    app.register_blueprint(scheduler_bp)

    @app.route("/")
    def home():
        buffer_connection = None

        if current_user.is_authenticated:
            buffer_connection = BufferConnection.query.filter_by(
                seller_id=current_user.id
            ).first()

        return render_template(
            "index.html",
            buffer_connection=buffer_connection
        )

    return app