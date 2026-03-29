from flask import Flask
from app.routes.auth_routes import auth_bp
from app.routes.main_routes import main_bp
from app.routes.google_auth_routes import google_bp
from app.routes.user_routes import profile_bp      
from app.routes.analysis_routes import analysis_bp


def register_blueprints(app: Flask):
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(google_bp)
    app.register_blueprint(profile_bp)      
    app.register_blueprint(analysis_bp)
                  # ← ADD THIS
