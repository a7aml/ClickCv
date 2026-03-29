# user_routes.py
import os
import uuid
import bcrypt
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models.user import User

profile_bp = Blueprint("profile", __name__, url_prefix="/api/profile")

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
AVATAR_FOLDER = os.path.join("app", "static", "uploads", "avatars")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
os.makedirs(AVATAR_FOLDER, exist_ok=True)


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _get_user() -> User | None:
    user_id = get_jwt_identity()
    return User.query.get(int(user_id))


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
        "avatar_url":    getattr(user, "avatar_url", None),
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
# POST /api/profile/avatar
# NOTE: Add avatar_url = db.Column(db.String(300), nullable=True) to User
#       then: flask db migrate -m "add avatar_url" && flask db upgrade
# ---------------------------------------------------------------------------
@profile_bp.route("/avatar", methods=["POST"])
@jwt_required()
def update_avatar():
    user = _get_user()
    if not user:
        return jsonify({"error": "User not found."}), 404

    if "avatar" not in request.files:
        return jsonify({"error": "No file provided."}), 400

    file = request.files["avatar"]

    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    if not _allowed_file(file.filename):
        return jsonify({"error": "Invalid file type. Use PNG, JPG, GIF or WEBP."}), 400

    if request.content_length and request.content_length > 5 * 1024 * 1024:
        return jsonify({"error": "File too large. Max is 5 MB."}), 413

    old_url = getattr(user, "avatar_url", None)
    if old_url:
        old_path = os.path.join("app", "static", old_url.lstrip("/static/"))
        if os.path.exists(old_path):
            os.remove(old_path)

    ext      = secure_filename(file.filename).rsplit(".", 1)[1].lower()
    filename = f"{user.id}_{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(AVATAR_FOLDER, filename))

    user.avatar_url = f"/static/uploads/avatars/{filename}"
    db.session.commit()

    return jsonify({
        "message":    "Avatar updated successfully.",
        "avatar_url": user.avatar_url,
    }), 200


# ---------------------------------------------------------------------------
# DELETE /api/profile/account
# ---------------------------------------------------------------------------
@profile_bp.route("/account", methods=["DELETE"])
@jwt_required()
def delete_account():
    user = _get_user()
    if not user:
        return jsonify({"error": "User not found."}), 404

    if user.auth_provider == "local":
        data     = request.get_json(silent=True) or {}
        password = data.get("password", "").strip()

        if not password:
            return jsonify({"error": "Password confirmation is required."}), 400

        if not _check_password(user.password_hash, password):
            return jsonify({"error": "Incorrect password."}), 400

    avatar_url = getattr(user, "avatar_url", None)
    if avatar_url:
        path = os.path.join("app", "static", avatar_url.lstrip("/static/"))
        if os.path.exists(path):
            os.remove(path)

    db.session.delete(user)
    db.session.commit()

    return jsonify({"message": "Account deleted successfully."}), 200

# ---------------------------------------------------------------------------
# GET /api/profile/stats  — real account statistics
# Add this route to your existing user_routes.py
# ---------------------------------------------------------------------------
@profile_bp.route("/stats", methods=["GET"])
@jwt_required()
def get_stats():
    from app.models.analysis import Analysis  # adjust import to your model name

    user = _get_user()
    if not user:
        return jsonify({"error": "User not found."}), 404

    # Total analyses
    total = Analysis.query.filter_by(user_id=user.id).count()

    # Average score — assumes your Analysis model has a `score` column (0-100)
    from sqlalchemy import func
    avg_result = db.session.query(func.avg(Analysis.score)).filter_by(user_id=user.id).scalar()
    avg_score  = round(avg_result, 1) if avg_result else 0

    # Last analysis date
    last = Analysis.query.filter_by(user_id=user.id)\
                         .order_by(Analysis.created_at.desc())\
                         .first()
    last_date = last.created_at.strftime("%b %d") if last else "—"

    # Member since
    member_since = user.created_at.strftime("%b %Y")

    return jsonify({
        "total_analyses": total,
        "avg_score":      avg_score,
        "last_analysis":  last_date,
        "member_since":   member_since,
    }), 200