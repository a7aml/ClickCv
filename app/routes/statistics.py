# app/routes/statistics.py
"""
Statistics routes for user account dashboard.

Provides:
    GET /api/user/stats - Returns total analyses, average score, last analysis date,
                          and membership start date for the currently authenticated user.
"""

from flask import Blueprint, jsonify, g
from sqlalchemy import func

# CORRECTED IMPORTS – models live inside the 'app' package
from app.extensions import db
from app.models.analysis import ResumeAnalysis
from app.models.user import User   # <-- User model must exist (fields: id, created_at)

stats_bp = Blueprint("stats", __name__, url_prefix="/api/user")


@stats_bp.route("/stats", methods=["GET"])
def get_user_stats():
    """
    Retrieve account statistics for the current user.

    Returns:
        JSON response with:
            total_analyses   (int)
            average_score    (float or None)
            last_analysis    (ISO format string or None)
            member_since     (ISO format string)
    """
    # --- Authentication ---
    # Replace this with your actual authentication method.
    # For example, using Flask-Login: user = current_user
    user = getattr(g, "user", None)
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    # --- Query statistics from the database ---
    total_analyses = ResumeAnalysis.query.filter_by(user_id=user.id).count()

    avg_score_result = (
        ResumeAnalysis.query
        .filter_by(user_id=user.id)
        .with_entities(func.avg(ResumeAnalysis.overall_score))
        .scalar()
    )
    average_score = round(avg_score_result, 2) if avg_score_result is not None else None

    last_analysis_record = (
        ResumeAnalysis.query
        .filter_by(user_id=user.id)
        .order_by(ResumeAnalysis.created_at.desc())
        .first()
    )
    last_analysis = (
        last_analysis_record.created_at.isoformat()
        if last_analysis_record and last_analysis_record.created_at
        else None
    )

    member_since = (
        user.created_at.isoformat()
        if hasattr(user, "created_at") and user.created_at
        else None
    )

    stats = {
        "total_analyses": total_analyses,
        "avg_score": average_score,          # note: key matches frontend expectation
        "last_analysis": last_analysis,
        "member_since": member_since,
    }

    return jsonify(stats)