# user_routes.py
import bcrypt
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func

from app.extensions import db
from app.models.user import User
from app.models.resume import Resume
from app.models.analysis import (
    ResumeAnalysis, AtsResult, ResumeSection, Recommendation,
    JobDescription, ResumeComparison,
)
from app.models.generated_cv import GeneratedCv

profile_bp = Blueprint("profile", __name__, url_prefix="/api/profile")


def _get_user() -> "User | None":
    """Return the current user only if they exist and are NOT soft-deleted."""
    user_id = get_jwt_identity()
    return User.get_active(int(user_id))


def _check_password(stored_hash: str, password: str) -> bool:
    """Verify password against bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))


def _hash_password(password: str) -> str:
    """Hash a new password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# ---------------------------------------------------------------------------
# GET /api/profile
# ---------------------------------------------------------------------------
@profile_bp.route("", methods=["GET"])
@jwt_required()
def get_profile():
    user = _get_user()
    if not user:
        return jsonify({"error": "User not found."}), 404

    parts      = (user.name or "").split(" ", 1)
    first_name = parts[0]
    last_name  = parts[1] if len(parts) > 1 else ""

    return jsonify({
        "id":            user.id,
        "first_name":    first_name,
        "last_name":     last_name,
        "email":         user.email,
        "auth_provider": user.auth_provider,
        "avatar_url":    None,
        "created_at":    user.created_at.strftime("%b %d, %Y"),
    }), 200


# ---------------------------------------------------------------------------
# PUT /api/profile/info
# ---------------------------------------------------------------------------
@profile_bp.route("/info", methods=["PUT"])
@jwt_required()
def update_info():
    user = _get_user()
    if not user:
        return jsonify({"error": "User not found."}), 404

    data       = request.get_json(silent=True) or {}
    first_name = data.get("first_name", "").strip()
    last_name  = data.get("last_name",  "").strip()

    if not first_name:
        return jsonify({"error": "First name is required."}), 400

    user.name = f"{first_name} {last_name}".strip()
    db.session.commit()

    return jsonify({"message": "Name updated successfully."}), 200


# ---------------------------------------------------------------------------
# PUT /api/profile/password
# ---------------------------------------------------------------------------
@profile_bp.route("/password", methods=["PUT"])
@jwt_required()
def update_password():
    user = _get_user()
    if not user:
        return jsonify({"error": "User not found."}), 404

    if user.auth_provider == "google":
        return jsonify({"error": "Your password is managed by Google."}), 403

    if not user.password_hash or not user.password_hash.strip():
        return jsonify({"error": "No password is set for this account."}), 400

    data             = request.get_json(silent=True) or {}
    current_password = data.get("current_password", "").strip()
    new_password     = data.get("new_password",     "").strip()
    confirm_password = data.get("confirm_password", "").strip()

    if not current_password or not new_password or not confirm_password:
        return jsonify({"error": "All password fields are required."}), 400

    if not _check_password(user.password_hash, current_password):
        return jsonify({"error": "Current password is incorrect."}), 400

    if new_password != confirm_password:
        return jsonify({"error": "New passwords do not match."}), 400

    if len(new_password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    user.password_hash = _hash_password(new_password)
    db.session.commit()

    return jsonify({"message": "Password updated successfully."}), 200


# ---------------------------------------------------------------------------
# DELETE /api/profile/account  — SOFT DELETE
#
# Marks the user as deleted (sets deleted_at timestamp).
# All data is preserved in the DB — only the user record is flagged.
# The user cannot log in after this point because _get_user() and
# auth_service both use get_active() which filters deleted_at IS NULL.
# ---------------------------------------------------------------------------
@profile_bp.route("/account", methods=["DELETE"])
@jwt_required()
def delete_account():
    user = _get_user()
    if not user:
        return jsonify({"error": "User not found."}), 404

    # Local accounts must confirm with password
    if user.auth_provider == "local":
        data     = request.get_json(silent=True) or {}
        password = data.get("password", "").strip()

        if not password:
            return jsonify({"error": "Password confirmation is required."}), 400

        if not _check_password(user.password_hash, password):
            return jsonify({"error": "Incorrect password."}), 400

    try:
        user.soft_delete()   # sets deleted_at = now, commits
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to delete account. Please try again."}), 500

    return jsonify({"message": "Account deleted successfully."}), 200


# ---------------------------------------------------------------------------
# GET /api/profile/stats
# ---------------------------------------------------------------------------
@profile_bp.route("/stats", methods=["GET"])
@jwt_required()
def get_stats():
    user = _get_user()
    if not user:
        return jsonify({"error": "User not found."}), 404

    total = ResumeAnalysis.query.filter_by(user_id=user.id).count()

    avg_result = db.session.query(
        func.avg(ResumeAnalysis.overall_score)
    ).filter_by(user_id=user.id).scalar()
    avg_score = round(avg_result) if avg_result is not None else None

    last = ResumeAnalysis.query.filter_by(user_id=user.id) \
                                .order_by(ResumeAnalysis.created_at.desc()) \
                                .first()
    last_date    = last.created_at.strftime("%b %d, %Y") if last else None
    member_since = user.created_at.strftime("%b %d, %Y")

    return jsonify({
        "total_analyses": total,
        "avg_score":      avg_score,
        "last_analysis":  last_date,
        "member_since":   member_since,
    }), 200