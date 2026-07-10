from flask import Flask
from app.config import Config
from app.extensions import db, bcrypt, jwt, migrate, mail
from flask_cors import CORS


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    jwt.init_app(app)
    mail.init_app(app)
    CORS(app)

    from app.models.user import User
    from app.models.resume import Resume
    from app.models.analysis import ResumeAnalysis, AtsResult, ResumeSection, Recommendation, JobDescription
    from app.models.generated_cv import GeneratedCv

    from app.routes.google_auth_routes import init_google_oauth
    from app.routes import register_blueprints

    init_google_oauth(app)
    register_blueprints(app)

    # ═══════════════════════════════════════════════════════════════
    # NEW: Pre-load NLP models at startup
    # ═══════════════════════════════════════════════════════════════
    with app.app_context():
        from app.services.model_loader import preload_models
        preload_models()
    # ═══════════════════════════════════════════════════════════════

    return app