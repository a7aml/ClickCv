#lastversion
from flask import Flask
from app.routes.auth_routes import auth_bp
from app.routes.main_routes import main_bp
from app.routes.google_auth_routes import google_bp
from app.routes.user_routes import profile_bp      
from app.routes.analysis_routes import analysis_bp
from app.routes.history_routes import history_bp
from app.routes.rebuild_routes import build_bp
from app.routes.compare_routes import compare_bp
from app.routes.cv_builder_routes import cv_builder_bp
from app.routes.job_routes import job_bp
from app.routes.chatbot_routes import chatbot_bp
from app.routes.cover_letter_routes import cover_letter_bp  # ← ADD THIS


from app.routes.admin_routes import admin_bp
from app.routes.statistics import stats_bp

def register_blueprints(app: Flask):
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(google_bp)
    app.register_blueprint(profile_bp)      
    app.register_blueprint(analysis_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(build_bp)
    app.register_blueprint(compare_bp)
    app.register_blueprint(cv_builder_bp)
    app.register_blueprint(job_bp)
    app.register_blueprint(chatbot_bp)
    app.register_blueprint(cover_letter_bp)  # ← ADD THIS
    app.register_blueprint(admin_bp)
    app.register_blueprint(stats_bp)


