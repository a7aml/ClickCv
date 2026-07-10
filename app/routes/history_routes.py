"""
routes/history_routes.py

All API endpoints consumed by the History page.

Blueprint prefix: /history

Endpoints:
    GET  /history/              — list all analyses for current user (enriched)
    GET  /history/<id>          — full detail of one analysis (for preview modal)
    DELETE /history/<id>        — delete one analysis + its ATS result + recommendations
    GET  /history/page          — serve the history.html template

Registration in app/__init__.py:
    from app.routes.history_routes import history_bp
    app.register_blueprint(history_bp)
"""

import os
from flask import Blueprint, jsonify, request, render_template, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models.resume   import Resume
from app.models.analysis import (
    ResumeAnalysis, AtsResult, Recommendation, ResumeSection
)

history_bp = Blueprint("history", __name__, url_prefix="/history")


# ── Helper ──────────────────────────────────────────────────────────────────

def _band(score: float) -> str:
    """Return score band string matching frontend BAND config."""
    if score is None:
        return "weak"
    if score >= 75:
        return "strong"
    if score >= 65:
        return "good"
    if score >= 50:
        return "borderline"
    return "weak"


def _serialise_ats(ats: AtsResult) -> dict:
    """Return all 10 criterion scores as a flat dict (None → 0)."""
    if not ats:
        return {
            "keyword_score": 0, "keyword_placement_score": 0,
            "formatting_score": 0, "structure_score": 0,
            "experience_recency_score": 0, "achievements_score": 0,
            "job_title_score": 0, "education_score": 0,
            "resume_length_score": 0, "contact_info_score": 0,
            "missing_sections": [], "missing_keywords": [],
        }
    return {
        "keyword_score":            round(ats.keyword_score            or 0, 1),
        "keyword_placement_score":  round(ats.keyword_placement_score  or 0, 1),
        "formatting_score":         round(ats.formatting_score         or 0, 1),
        "structure_score":          round(ats.structure_score          or 0, 1),
        "experience_recency_score": round(ats.experience_recency_score or 0, 1),
        "achievements_score":       round(ats.achievements_score       or 0, 1),
        "job_title_score":          round(ats.job_title_score          or 0, 1),
        "education_score":          round(ats.education_score          or 0, 1),
        "resume_length_score":      round(ats.resume_length_score      or 0, 1),
        "contact_info_score":       round(ats.contact_info_score       or 0, 1),
        "missing_sections":         ats.missing_sections  or [],
        "missing_keywords":         ats.missing_keywords  or [],
    }


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE 1 — Serve the history page
# ══════════════════════════════════════════════════════════════════════════════

@history_bp.route("/", methods=["GET"])
@history_bp.route("", methods=["GET"])
def history_page():
    """Serve history.html template (Jinja2)."""
    return render_template("history.html")


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE 2 — List all analyses (enriched, for card list)
# GET /history/analyses
#
# Returns every analysis for the authenticated user, enriched with:
#   - filename from the Resume model
#   - all 10 criterion scores from AtsResult
#   - score_band computed server-side
#   - missing_keywords and missing_sections
#   - recommendation count
#
# The frontend renders all cards from this single response — no N+1 calls.
# ══════════════════════════════════════════════════════════════════════════════

@history_bp.route("/analyses", methods=["GET"])
@jwt_required()
def list_analyses():
    """
    Return all analyses for the current user, enriched with scores and metadata.

    Query params (all optional):
        major   — filter by industry (technology | medical | engineering |
                  financial | marketing)
        sort    — date_desc (default) | date_asc | score_desc | score_asc
        page    — page number, 1-based (default 1)
        per_page — items per page (default 10, max 50)
    """
    user_id = get_jwt_identity()

    # ── Query params ───────────────────────────────────────────────────────
    major    = request.args.get("major", "").strip().lower()
    sort     = request.args.get("sort",  "date_desc")
    page     = max(int(request.args.get("page",     1)),  1)
    per_page = min(int(request.args.get("per_page", 10)), 50)

    # ── Base query ─────────────────────────────────────────────────────────
    q = ResumeAnalysis.query.filter_by(user_id=user_id)

    if major and major in {"technology", "medical", "engineering",
                           "financial", "marketing"}:
        q = q.filter_by(major=major)

    # ── Sort ───────────────────────────────────────────────────────────────
    if sort == "date_asc":
        q = q.order_by(ResumeAnalysis.created_at.asc())
    elif sort == "score_desc":
        q = q.order_by(ResumeAnalysis.overall_score.desc())
    elif sort == "score_asc":
        q = q.order_by(ResumeAnalysis.overall_score.asc())
    else:  # date_desc (default)
        q = q.order_by(ResumeAnalysis.created_at.desc())

    # ── Pagination ─────────────────────────────────────────────────────────
    total     = q.count()
    analyses  = q.offset((page - 1) * per_page).limit(per_page).all()

    # ── Enrich each analysis ───────────────────────────────────────────────
    result = []
    for a in analyses:
        # Resume (for filename)
        resume   = Resume.query.get(a.resume_id)
        filename = resume.file_name if resume else f"CV_{a.resume_id}"

        # ATS scores
        ats      = AtsResult.query.filter_by(analysis_id=a.id).first()
        scores   = _serialise_ats(ats)

        # Recommendation count
        rec_count = Recommendation.query.filter_by(analysis_id=a.id).count()

        # Build item
        score = round(a.overall_score or 0, 1)
        result.append({
            "analysis_id":      a.id,
            "resume_id":        a.resume_id,
            "major":            a.major,
            "overall_score":    score,
            "score_band":       _band(score),
            "created_at":       a.created_at.isoformat(),
            "filename":         filename,
            "rec_count":        rec_count,
            # Flat criterion scores (used by mini-bars + expand detail)
            **scores,
        })

    # ── Stats (over ALL user analyses, not just this page) ─────────────────
    all_analyses  = ResumeAnalysis.query.filter_by(user_id=user_id).all()
    all_scores    = [a.overall_score for a in all_analyses if a.overall_score]
    stats = {
        "total":        len(all_analyses),
        "average_score": round(sum(all_scores) / len(all_scores), 1) if all_scores else 0,
        "best_score":    round(max(all_scores), 1)                    if all_scores else 0,
        "last_created":  all_analyses[0].created_at.isoformat()       if all_analyses else None,
    }

    return jsonify({
        "analyses":    result,
        "total":       total,
        "page":        page,
        "per_page":    per_page,
        "total_pages": max(1, -(-total // per_page)),  # ceiling division
        "stats":       stats,
    }), 200


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE 3 — Full detail for one analysis (preview modal)
# GET /history/analyses/<analysis_id>
#
# Returns everything: scores, recommendations, detected sections,
# missing keywords, missing sections — used to populate the preview modal.
# ══════════════════════════════════════════════════════════════════════════════

@history_bp.route("/analyses/<int:analysis_id>", methods=["GET"])
@jwt_required()
def get_analysis_detail(analysis_id):
    """
    Return full detail of one analysis for the preview modal.
    Ownership check: analysis must belong to the requesting user.
    """
    user_id  = get_jwt_identity()
    analysis = ResumeAnalysis.query.filter_by(
        id=analysis_id, user_id=user_id
    ).first()

    if not analysis:
        return jsonify({"error": "Analysis not found."}), 404

    # Resume filename
    resume   = Resume.query.get(analysis.resume_id)
    filename = resume.file_name if resume else f"CV_{analysis.resume_id}"

    # ATS scores
    ats    = AtsResult.query.filter_by(analysis_id=analysis.id).first()
    scores = _serialise_ats(ats)

    # Recommendations (ordered by priority: 1=critical → 3=minor)
    recs = Recommendation.query.filter_by(
        analysis_id=analysis.id
    ).order_by(Recommendation.priority.asc()).all()

    # Detected sections (section types found in this resume)
    sections = ResumeSection.query.filter_by(
        resume_id=analysis.resume_id
    ).all()
    detected_sections = [s.section_type.value for s in sections]

    score = round(analysis.overall_score or 0, 1)

    return jsonify({
        "analysis_id":       analysis.id,
        "resume_id":         analysis.resume_id,
        "filename":          filename,
        "major":             analysis.major,
        "overall_score":     score,
        "score_band":        _band(score),
        "created_at":        analysis.created_at.isoformat(),
        "detected_sections": detected_sections,
        "recommendations": [
            {
                "id":          r.id,
                "title":       r.title,
                "description": r.description,
                "priority":    r.priority,
            }
            for r in recs
        ],
        # All criterion scores + missing arrays
        **scores,
    }), 200


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE 4 — Delete one analysis
# DELETE /history/analyses/<analysis_id>
#
# Deletes:
#   1. Recommendation rows linked to this analysis
#   2. AtsResult row linked to this analysis
#   3. ResumeAnalysis row itself
#
# Does NOT delete the Resume row or its file — user may have other analyses
# for the same uploaded CV.
# ══════════════════════════════════════════════════════════════════════════════

@history_bp.route("/analyses/<int:analysis_id>", methods=["DELETE"])
@jwt_required()
def delete_analysis(analysis_id):
    """
    Permanently delete one analysis and its child records.
    Ownership check: analysis must belong to the requesting user.
    """
    user_id  = get_jwt_identity()
    analysis = ResumeAnalysis.query.filter_by(
        id=analysis_id, user_id=user_id
    ).first()

    if not analysis:
        return jsonify({"error": "Analysis not found."}), 404

    try:
        # Delete child records first to respect FK constraints
        Recommendation.query.filter_by(analysis_id=analysis_id).delete()
        AtsResult.query.filter_by(analysis_id=analysis_id).delete()

        # Delete the analysis itself
        db.session.delete(analysis)
        db.session.commit()

        current_app.logger.info(
            f"Analysis {analysis_id} deleted by user {user_id}"
        )
        return jsonify({"message": "Analysis deleted successfully."}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Delete analysis {analysis_id} failed: {e}"
        )
        return jsonify({"error": "Failed to delete analysis. Please try again."}), 500