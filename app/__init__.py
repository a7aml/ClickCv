from flask import Flask
from app.config import Config
from app.extensions import db, bcrypt, jwt
from flask_cors import CORS


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    CORS(app)

    # Initialize Google OAuth
    from app.routes.google_auth_routes import init_google_oauth
    init_google_oauth(app)

    # Register all blueprints
    from app.routes import register_blueprints
    register_blueprints(app)

    return app