"""
routes/job_routes.py

Three endpoints:
    GET  /jobs/search            — fetch jobs from JSearch by major + country
    POST /jobs/match             — match user CV against jobs
    POST /jobs/improvement-plan  — generate plan for a specific low-match job

Change from original:
    search_jobs() now reads an optional `country` query param and
    passes it to fetch_jobs(). Everything else is unchanged.
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models.analysis import ResumeAnalysis, AtsResult
from app.services.job_service import fetch_jobs, SUPPORTED_COUNTRIES
from app.services.job_matching_service import (
    match_cv_to_jobs,
    generate_job_improvement_plan,
    MATCH_THRESHOLD_LOW,
)

job_bp = Blueprint("jobs", __name__, url_prefix="/jobs")


# ── GET /jobs/search ──────────────────────────────────────────────────────────

@job_bp.route("/search", methods=["GET"])
@jwt_required()
def search_jobs():
    """
    Fetch jobs from JSearch API for the user's major and selected country.

    Query params:
        major:   industry major (technology/medical/engineering/financial/marketing)
        country: country key from SUPPORTED_COUNTRIES e.g. 'malaysia' (default 'any')
        page:    page number (default 1)

    Returns list of normalized job objects.
    """
    major   = request.args.get("major",   "technology").strip().lower()
    country = request.args.get("country", "any").strip().lower()
    page    = int(request.args.get("page", 1))

    valid_majors = {"technology", "medical", "engineering", "financial", "marketing"}
    if major not in valid_majors:
        major = "technology"

    # Validate country key — fall back to 'any' if unknown
    if country not in SUPPORTED_COUNTRIES:
        country = "any"

    jobs, error = fetch_jobs(major=major, page=page, country=country)

    if error:
        return jsonify({"error": error}), 503

    return jsonify({
        "jobs":    jobs,
        "total":   len(jobs),
        "major":   major,
        "country": country,
        "page":    page,
    }), 200


# ── POST /jobs/match ──────────────────────────────────────────────────────────

@job_bp.route("/match", methods=["POST"])
@jwt_required()
def match_jobs():
    """
    Match user's CV against a list of jobs using existing ATS analysis data.

    Body:
        analysis_id: int  — which analysis to use for matching
        jobs:        list — job objects from /jobs/search

    Returns jobs sorted by match score.
    """
    user_id = get_jwt_identity()
    data    = request.get_json()

    if not data:
        return jsonify({"error": "Request body required."}), 400

    analysis_id = data.get("analysis_id")
    jobs        = data.get("jobs", [])

    if not jobs:
        return jsonify({"error": "No jobs provided for matching."}), 400

    # Load analysis from DB
    if analysis_id:
        analysis = ResumeAnalysis.query.filter_by(
            id=analysis_id, user_id=user_id
        ).first()
    else:
        # Fall back to most recent analysis
        analysis = ResumeAnalysis.query.filter_by(
            user_id=user_id
        ).order_by(ResumeAnalysis.created_at.desc()).first()

    if not analysis:
        return jsonify({
            "error": "No CV analysis found. Please analyse your CV first."
        }), 404

    ats = AtsResult.query.filter_by(analysis_id=analysis.id).first()

    analysis_result = {
        "overall_score":     analysis.overall_score or 0,
        "missing_keywords":  ats.missing_keywords  if ats else [],
        "missing_sections":  ats.missing_sections  if ats else [],
        "detected_sections": [],
        "scores": {
            "keyword_score":            ats.keyword_score            if ats else 0,
            "keyword_placement_score":  ats.keyword_placement_score  if ats else 0,
            "formatting_score":         ats.formatting_score         if ats else 0,
            "structure_score":          ats.structure_score          if ats else 0,
            "experience_recency_score": ats.experience_recency_score if ats else 0,
            "achievements_score":       ats.achievements_score       if ats else 0,
            "job_title_score":          ats.job_title_score          if ats else 0,
            "education_score":          ats.education_score          if ats else 0,
            "resume_length_score":      ats.resume_length_score      if ats else 0,
            "contact_info_score":       ats.contact_info_score       if ats else 0,
        }
    }

    # Get detected sections from resume
    from app.models.analysis import ResumeSection
    from app.models.resume import Resume
    resume = Resume.query.get(analysis.resume_id)
    if resume and resume.parsed_data and isinstance(resume.parsed_data, dict):
        analysis_result["detected_sections"] = list(resume.parsed_data.keys())

    matched_jobs = match_cv_to_jobs(analysis_result, jobs)

    return jsonify({
        "matched_jobs":  matched_jobs,
        "total":         len(matched_jobs),
        "analysis_id":   analysis.id,
        "overall_score": analysis.overall_score,
    }), 200


# ── POST /jobs/improvement-plan ───────────────────────────────────────────────

@job_bp.route("/improvement-plan", methods=["POST"])
@jwt_required()
def improvement_plan():
    """
    Generate a specific improvement plan for a low-match job.

    Only useful when match_score < 40%.

    Body:
        job:         dict — the specific job object
        analysis_id: int  — which analysis to use
        major:       str  — user's major
    """
    user_id = get_jwt_identity()
    data    = request.get_json()

    if not data:
        return jsonify({"error": "Request body required."}), 400

    job         = data.get("job")
    analysis_id = data.get("analysis_id")
    major       = data.get("major", "technology")

    if not job:
        return jsonify({"error": "Job data is required."}), 400

    if analysis_id:
        analysis = ResumeAnalysis.query.filter_by(
            id=analysis_id, user_id=user_id
        ).first()
    else:
        analysis = ResumeAnalysis.query.filter_by(
            user_id=user_id
        ).order_by(ResumeAnalysis.created_at.desc()).first()

    if not analysis:
        return jsonify({"error": "No CV analysis found."}), 404

    ats = AtsResult.query.filter_by(analysis_id=analysis.id).first()

    analysis_result = {
        "overall_score":    analysis.overall_score or 0,
        "missing_keywords": ats.missing_keywords if ats else [],
        "missing_sections": ats.missing_sections if ats else [],
        "scores": {
            "keyword_score":            ats.keyword_score            if ats else 0,
            "keyword_placement_score":  ats.keyword_placement_score  if ats else 0,
            "formatting_score":         ats.formatting_score         if ats else 0,
            "structure_score":          ats.structure_score          if ats else 0,
            "experience_recency_score": ats.experience_recency_score if ats else 0,
            "achievements_score":       ats.achievements_score       if ats else 0,
            "job_title_score":          ats.job_title_score          if ats else 0,
            "education_score":          ats.education_score          if ats else 0,
            "resume_length_score":      ats.resume_length_score      if ats else 0,
            "contact_info_score":       ats.contact_info_score       if ats else 0,
        }
    }

    plan, error = generate_job_improvement_plan(job, analysis_result, major)

    if error:
        return jsonify({"error": error}), 500

    return jsonify({
        "plan": plan,
        "job":  {"title": job.get("title"), "company": job.get("company")},
    }), 200