"""
routes/cover_letter_routes.py

Handles cover letter generation via AI.
User uploads CV + pastes job description → generates tailored cover letter.
"""

import os
import uuid
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.resume import Resume
from app.models.analysis import JobDescription
from app.models.cover_letter import CoverLetter
from app.services.cover_letter_service import generate_cover_letter

cover_letter_bp = Blueprint("cover_letter", __name__, url_prefix="/api/cover-letter")


@cover_letter_bp.route("/generate", methods=["POST"])
@jwt_required()
def generate():
    """
    Generate a cover letter from uploaded CV + job description.

    Request: multipart/form-data
        cv_file         — PDF or DOCX CV file (required)
        job_description — JD text (required)
        company_name    — Company name (optional)
        position_title  — Position title (optional)

    Returns:
        {
            "cover_letter_id": int,
            "cover_letter": str,
            "company_name": str,
            "position_title": str,
            "created_at": str,
            "resume_filename": str
        }
    """
    user_id = get_jwt_identity()

    # ── Validate inputs ───────────────────────────────────────────────────
    if "cv_file" not in request.files:
        return jsonify({"error": "CV file is required."}), 400

    file             = request.files["cv_file"]
    job_description  = request.form.get("job_description", "").strip()
    company_name     = request.form.get("company_name", "").strip()
    position_title   = request.form.get("position_title", "").strip()

    if not file or file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    if not job_description or len(job_description) < 50:
        return jsonify({"error": "Job description is required (minimum 50 characters)."}), 400

    # Validate file type
    ext = os.path.splitext(secure_filename(file.filename))[1].lower()
    if ext not in {".pdf", ".docx"}:
        return jsonify({"error": "Only PDF and DOCX files are supported."}), 400

    # Validate file size (max 5MB)
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    max_size = 5 * 1024 * 1024  # 5MB
    if file_size > max_size:
        return jsonify({"error": "File size must be less than 5MB."}), 400

    # ── Save CV file temporarily ──────────────────────────────────────────
    upload_folder = current_app.config.get(
        "UPLOAD_FOLDER",
        os.path.abspath(os.path.join(current_app.root_path, "static", "uploads"))
    )
    os.makedirs(upload_folder, exist_ok=True)
    
    tmp_filename = f"coverletter_{user_id}_{uuid.uuid4().hex[:8]}{ext}"
    tmp_path     = os.path.abspath(os.path.join(upload_folder, tmp_filename))
    
    try:
        file.save(tmp_path)
    except Exception as e:
        current_app.logger.error(f"File save failed for user {user_id}: {e}")
        return jsonify({"error": "Failed to save file. Please try again."}), 500

    try:
        # ── Extract text from CV ──────────────────────────────────────────
        from app.services.extraction_service import extract_text_from_file
        
        resume_text, error = extract_text_from_file(tmp_path)
        if error or not resume_text or not resume_text.strip():
            return jsonify({"error": "Could not extract text from CV. Please ensure it's a text-based PDF or DOCX."}), 422

        # ── Save or retrieve Resume record ────────────────────────────────
        # Check if this exact file was already uploaded by this user
        resume = Resume.query.filter_by(
            user_id=user_id,
            file_name=secure_filename(file.filename)
        ).first()

        if not resume:
            # Create new resume record
            safe_filename = f"{user_id}_{uuid.uuid4().hex[:8]}{ext}"
            permanent_path = os.path.abspath(os.path.join(upload_folder, safe_filename))
            
            # Move temp file to permanent location
            os.rename(tmp_path, permanent_path)
            tmp_path = permanent_path  # Update for cleanup
            
            resume = Resume(
                user_id=user_id,
                file_name=secure_filename(file.filename),
                file_path=permanent_path,
                raw_text=resume_text,
                parsed_data=None  # Not needed for cover letter
            )
            db.session.add(resume)
            db.session.flush()  # Get resume.id without committing

        # ── Save or retrieve JobDescription ───────────────────────────────
        job_desc = JobDescription(
            user_id=user_id,
            title=f"{position_title or 'Position'} at {company_name or 'Company'}",
            description=job_description
        )
        db.session.add(job_desc)
        db.session.flush()  # Get job_desc.id

        # ── Generate cover letter via LLM ─────────────────────────────────
        cover_letter_text, error = generate_cover_letter(
            resume_text=resume_text,
            job_description=job_description,
            company_name=company_name,
            position_title=position_title
        )

        if error:
            current_app.logger.error(f"Cover letter generation failed for user {user_id}: {error}")
            db.session.rollback()
            return jsonify({"error": f"Failed to generate cover letter: {error}"}), 422

        # ── Save to database ──────────────────────────────────────────────
        cover_letter = CoverLetter(
            user_id=user_id,
            resume_id=resume.id,
            job_description_id=job_desc.id,
            cover_letter_text=cover_letter_text,
            company_name=company_name or None,
            position_title=position_title or None
        )
        db.session.add(cover_letter)
        db.session.commit()

        current_app.logger.info(
            f"Cover letter generated: id={cover_letter.id}, "
            f"user={user_id}, company={company_name or 'N/A'}"
        )

        return jsonify({
            "message": "Cover letter generated successfully.",
            "cover_letter_id": cover_letter.id,
            "cover_letter": cover_letter_text,
            "company_name": company_name,
            "position_title": position_title,
            "created_at": cover_letter.created_at.isoformat(),
            "resume_filename": resume.file_name
        }), 200

    except Exception as e:
        db.session.rollback()
        import traceback
        current_app.logger.error(
            f"Cover letter generation failed for user {user_id}: {e}\n{traceback.format_exc()}"
        )
        return jsonify({"error": "Failed to generate cover letter. Please try again."}), 500

    finally:
        # Clean up temporary file if it still exists
        try:
            if tmp_path and os.path.exists(tmp_path) and "coverletter_" in os.path.basename(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


@cover_letter_bp.route("/<int:cover_letter_id>", methods=["GET"])
@jwt_required()
def get_cover_letter(cover_letter_id):
    """
    Retrieve a previously generated cover letter by ID.

    Returns:
        {
            "id": int,
            "cover_letter": str,
            "company_name": str,
            "position_title": str,
            "created_at": str,
            "resume_filename": str,
            "job_description_title": str
        }
    """
    user_id = get_jwt_identity()
    
    cover_letter = CoverLetter.query.filter_by(
        id=cover_letter_id,
        user_id=user_id
    ).first()

    if not cover_letter:
        return jsonify({"error": "Cover letter not found."}), 404

    return jsonify(cover_letter.to_dict()), 200


@cover_letter_bp.route("/history", methods=["GET"])
@jwt_required()
def get_history():
    """
    Get all cover letters for the current user, most recent first.

    Returns:
        {
            "cover_letters": [
                {
                    "id": int,
                    "company_name": str,
                    "position_title": str,
                    "created_at": str,
                    "resume_filename": str
                },
                ...
            ],
            "total": int
        }
    """
    user_id = get_jwt_identity()

    cover_letters = CoverLetter.query.filter_by(user_id=user_id).order_by(
        CoverLetter.created_at.desc()
    ).all()

    return jsonify({
        "cover_letters": [
            {
                "id": cl.id,
                "company_name": cl.company_name,
                "position_title": cl.position_title,
                "created_at": cl.created_at.isoformat(),
                "resume_filename": cl.resume.file_name if cl.resume else None,
                "preview": cl.cover_letter_text[:100] + "..." if len(cl.cover_letter_text) > 100 else cl.cover_letter_text
            }
            for cl in cover_letters
        ],
        "total": len(cover_letters)
    }), 200


@cover_letter_bp.route("/<int:cover_letter_id>", methods=["DELETE"])
@jwt_required()
def delete_cover_letter(cover_letter_id):
    """
    Delete a cover letter by ID.

    Returns:
        {"message": "Cover letter deleted successfully."}
    """
    user_id = get_jwt_identity()

    cover_letter = CoverLetter.query.filter_by(
        id=cover_letter_id,
        user_id=user_id
    ).first()

    if not cover_letter:
        return jsonify({"error": "Cover letter not found."}), 404

    try:
        db.session.delete(cover_letter)
        db.session.commit()
        
        current_app.logger.info(f"Cover letter deleted: id={cover_letter_id}, user={user_id}")
        
        return jsonify({"message": "Cover letter deleted successfully."}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Delete failed for cover_letter {cover_letter_id}: {e}")
        return jsonify({"error": "Failed to delete cover letter."}), 500