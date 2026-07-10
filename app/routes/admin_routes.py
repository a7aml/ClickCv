"""
routes/admin_routes.py

Admin-only endpoints for the User Management panel.

Endpoints:
    GET    /admin/users               — list all active (non-deleted) users
    GET    /admin/users/deleted       — list soft-deleted users
    PATCH  /admin/users/<id>          — edit a user's name/email/password
    PATCH  /admin/users/<id>/admin    — promote/demote admin status
    PATCH  /admin/users/<id>/restore  — restore a soft-deleted user
    DELETE /admin/users/<id>          — SOFT delete a user (sets deleted_at)

Soft delete policy:
    Admin DELETE now soft-deletes — sets deleted_at on the User row.
    All resumes, analyses, and other data are preserved.
    The user can be restored via PATCH /admin/users/<id>/restore.
    Only admins can restore or permanently inspect deleted accounts.
"""

from functools import wraps
from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db, bcrypt
from app.models.user import User
from app.models.analysis import (
    ResumeAnalysis,
    AtsResult,
    ResumeSection,
    Recommendation,
    JobDescription,
    ResumeComparison,
)
from app.models.resume import Resume

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ── Access control ──────────────────────────────────────────────────────────

def admin_required(fn):
    """
    Decorator: requires a valid JWT AND user.is_admin == True.
    Uses get_active() so soft-deleted admins cannot access this.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user_id = get_jwt_identity()
        user = User.get_active(int(user_id))

        if not user:
            return jsonify({"error": "User not found."}), 404

        if not user.is_admin:
            return jsonify({"error": "Admin access required."}), 403

        request._current_admin_user = user
        return fn(*args, **kwargs)

    return wrapper


def _user_dict(u: User) -> dict:
    """Shared serialiser for a User row."""
    return {
        "id":            u.id,
        "name":          u.name,
        "email":         u.email,
        "auth_provider": u.auth_provider,
        "is_admin":      bool(u.is_admin),
        "has_password":  u.password_hash is not None,
        "is_deleted":    u.is_deleted,
        "deleted_at":    u.deleted_at.isoformat() if u.deleted_at else None,
        "created_at":    u.created_at.isoformat() if u.created_at else None,
    }


# ── GET /admin/users — active users only ────────────────────────────────────

@admin_bp.route("/users", methods=["GET"])
@jwt_required()
@admin_required
def list_users():
    """Return all active (not soft-deleted) users."""
    users = (
        User.query
        .filter(User.deleted_at.is_(None))   # active only
        .order_by(User.created_at.desc())
        .all()
    )
    return jsonify({
        "users": [_user_dict(u) for u in users],
        "total": len(users),
    }), 200


# ── GET /admin/users/deleted — soft-deleted users ───────────────────────────

@admin_bp.route("/users/deleted", methods=["GET"])
@jwt_required()
@admin_required
def list_deleted_users():
    """Return all soft-deleted users so admins can review or restore them."""
    users = (
        User.query
        .filter(User.deleted_at.isnot(None))  # deleted only
        .order_by(User.deleted_at.desc())
        .all()
    )
    return jsonify({
        "users": [_user_dict(u) for u in users],
        "total": len(users),
    }), 200


# ── PATCH /admin/users/<id> — edit name/email/password ──────────────────────

@admin_bp.route("/users/<int:user_id>", methods=["PATCH"])
@jwt_required()
@admin_required
def update_user(user_id):
    """
    Edit a user's name, email, and/or password.
    Works on both active and soft-deleted users.
    """
    # Allow editing deleted users too (admin may want to fix before restoring)
    target_user = User.query.get(user_id)
    if not target_user:
        return jsonify({"error": "User not found."}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required."}), 400

    # ── Name ──
    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Name cannot be empty."}), 400
        target_user.name = name

    # ── Email ──
    if "email" in data:
        email = (data.get("email") or "").strip().lower()
        if not email:
            return jsonify({"error": "Email cannot be empty."}), 400

        existing = User.query.filter(
            User.email == email,
            User.id != target_user.id,
        ).first()
        if existing:
            return jsonify({"error": "This email is already in use."}), 409

        target_user.email = email

    # ── Password ──
    if "password" in data:
        password = data.get("password") or ""
        if password.strip():
            if target_user.auth_provider == "google" or target_user.password_hash is None:
                return jsonify({
                    "error": "This account uses Google Sign-In. Password changes are not available."
                }), 400

            if len(password) < 6:
                return jsonify({"error": "Password must be at least 6 characters."}), 400

            target_user.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to update user: {str(e)}"}), 500

    return jsonify({
        "message": "User updated successfully.",
        "user": _user_dict(target_user),
    }), 200


# ── PATCH /admin/users/<id>/admin — promote / demote ────────────────────────

@admin_bp.route("/users/<int:user_id>/admin", methods=["PATCH"])
@jwt_required()
@admin_required
def set_admin_status(user_id):
    """Promote or demote a user's admin status. Cannot change your own."""
    current_admin = request._current_admin_user

    if user_id == current_admin.id:
        return jsonify({"error": "You cannot change your own admin status."}), 400

    data = request.get_json()
    if not data or "is_admin" not in data:
        return jsonify({"error": "'is_admin' (boolean) is required."}), 400

    new_status = data.get("is_admin")
    if not isinstance(new_status, bool):
        return jsonify({"error": "'is_admin' must be a boolean."}), 400

    target_user = User.query.get(user_id)
    if not target_user:
        return jsonify({"error": "User not found."}), 404

    target_user.is_admin = new_status
    db.session.commit()

    return jsonify({
        "message": f"User {'promoted to' if new_status else 'demoted from'} admin.",
        "user": _user_dict(target_user),
    }), 200


# ── PATCH /admin/users/<id>/restore — restore soft-deleted user ─────────────

@admin_bp.route("/users/<int:user_id>/restore", methods=["PATCH"])
@jwt_required()
@admin_required
def restore_user(user_id):
    """
    Restore a soft-deleted user by clearing their deleted_at timestamp.
    The user regains full access immediately after restore.
    """
    target_user = User.query.get(user_id)
    if not target_user:
        return jsonify({"error": "User not found."}), 404

    if not target_user.is_deleted:
        return jsonify({"error": "User is not deleted."}), 400

    try:
        target_user.restore()   # clears deleted_at, commits
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to restore user: {str(e)}"}), 500

    return jsonify({
        "message": f"User {target_user.email} restored successfully.",
        "user": _user_dict(target_user),
    }), 200


# ── DELETE /admin/users/<id> — SOFT DELETE ──────────────────────────────────

@admin_bp.route("/users/<int:user_id>", methods=["DELETE"])
@jwt_required()
@admin_required
def delete_user(user_id):
    """
    Soft-delete a user by setting deleted_at = now.
    All their data (resumes, analyses, etc.) is preserved.
    The user is immediately blocked from logging in.
    Can be reversed via PATCH /admin/users/<id>/restore.
    Cannot delete your own account via this endpoint.
    """
    current_admin = request._current_admin_user

    if user_id == current_admin.id:
        return jsonify({"error": "You cannot delete your own account."}), 400

    target_user = User.query.get(user_id)
    if not target_user:
        return jsonify({"error": "User not found."}), 404

    if target_user.is_deleted:
        return jsonify({"error": "User is already deleted."}), 400

    try:
        target_user.soft_delete()   # sets deleted_at = now, commits
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to delete user: {str(e)}"}), 500

    return jsonify({
        "message": f"User {target_user.email} soft-deleted successfully. "
                   f"Their data is preserved and can be restored.",
        "user": _user_dict(target_user),
    }), 200