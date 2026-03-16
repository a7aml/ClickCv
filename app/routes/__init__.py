from flask import Flask
from app.routes.auth_routes import auth_bp
from app.routes.main_routes import main_bp
from app.routes.google_auth_routes import google_bp


def register_blueprints(app: Flask):
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(google_bp)