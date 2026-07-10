"""
routes/compare_routes.py

Handles the CV comparison feature.

Blueprint prefix: /compare

Endpoints:
    POST /compare/run  — upload two CVs + JD, run full comparison pipeline

Pipeline (POST /compare/run):
    1. Validate both files + JD from multipart form
    2. Extract raw text from both files
    3. Run NLP section detection on both
    4. Extract JD key phrases properly (technical bigrams + unigrams)
    5. Run calculate_ats_score() on both CVs with JD keywords injected directly
    6. Build per-CV JD keyword hit/miss maps and pass to LLM
    7. Call generate_comparison() in llm_service.py with full JD context
    8. Save result to resume_comparisons + comparison_resumes tables
    9. Return full comparison JSON to frontend

COMPARE-SPECIFIC IMPROVEMENTS (does not affect any other feature):
    - JD keywords are extracted here with extract_jd_keyphrases() and passed
      directly into calculate_ats_score() so scoring is driven by the real JD,
      not the generic industry keyword database.
    - Per-CV keyword hit/miss maps are built here and forwarded to the LLM
      so the verdict references specific JD terms each CV has or lacks.
    - Full JD text (up to 1500 chars) is passed to the LLM instead of 600.

Registration in app/__init__.py:
    from app.routes.compare_routes import compare_bp
    app.register_blueprint(compare_bp)
"""

import os
import re
import uuid
import tempfile

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models.analysis import ResumeComparison, ComparisonResume
from app.services.extraction_service import extract_text_from_file
from app.services.nlp_service import detect_sections, extract_keywords_per_section
from app.services.scoring_service import calculate_ats_score
from app.services.llm_service import generate_comparison

compare_bp = Blueprint("compare", __name__, url_prefix="/compare")

# Allowed file extensions
ALLOWED_EXTENSIONS = {"pdf", "docx"}
MAX_FILE_SIZE      = 5 * 1024 * 1024  # 5 MB

# Stop words for JD key phrase extraction
_JD_STOP = {
    "the", "and", "or", "to", "a", "an", "of", "in", "for", "with",
    "on", "at", "by", "is", "are", "was", "were", "be", "been", "have",
    "has", "had", "do", "does", "did", "will", "would", "could", "should",
    "may", "might", "must", "shall", "we", "you", "our", "your", "their",
    "this", "that", "these", "those", "from", "as", "it", "its", "not",
    "but", "if", "so", "up", "out", "about", "into", "through", "during",
    "including", "ability", "experience", "skills", "knowledge", "work",
    "team", "position", "job", "role", "candidate", "responsibilities",
    "required", "preferred", "strong", "good", "excellent", "looking",
    "seeking", "join", "working", "minimum", "years", "plus", "least",
    "also", "well", "new", "use", "using", "used", "help", "support",
    "ensure", "provide", "develop", "manage", "create", "build", "make",
    "able", "both", "all", "any", "can", "her", "his", "him", "she",
    "they", "them", "who", "what", "when", "where", "how", "which",
    "other", "more", "than", "such", "each", "get", "set", "relevant",
    "motivated", "familiarity", "proficiency", "responsibilities",
    "understanding", "related", "must", "ideally", "nice", "plus",
    "demonstrated", "proven", "solid", "hands", "day", "basis",
    "environment", "growing", "fast", "paced", "startup", "company",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _allowed(filename: str) -> bool:
    return "." in filename and \
           filename.rsplit(".", 1)[-1].lower() in ALLOWED_EXTENSIONS


def _save_temp(file) -> str:
    """
    Save an uploaded file to a temp path so extraction_service
    can open it by file path.
    Returns the temp file path.
    """
    ext      = file.filename.rsplit(".", 1)[-1].lower()
    tmp_path = os.path.join(
        tempfile.gettempdir(),
        f"clickcv_compare_{uuid.uuid4().hex}.{ext}"
    )
    file.save(tmp_path)
    return tmp_path


def _cleanup(*paths):
    """Delete temp files — errors are swallowed so they never block response."""
    for p in paths:
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except Exception:
            pass


def _band(score: float) -> str:
    if score >= 75: return "strong"
    if score >= 65: return "good"
    if score >= 50: return "borderline"
    return "weak"


def extract_jd_keyphrases(jd_text: str) -> list:
    """
    Extract meaningful technical key phrases from a job description.

    COMPARE-SPECIFIC: This replaces the generic _infer_major() approach.
    Instead of guessing the industry and using a 200+ word keyword database,
    we pull the actual required terms directly from the JD text.

    Strategy:
        1. Extract technical unigrams (single words that are not stop words)
        2. Extract technical bigrams (two-word phrases — catches "REST API",
           "machine learning", "CI/CD pipeline", "unit testing", etc.)
        3. Extract version/tool strings like "Python 3", "Node.js", "Vue.js"
        4. Deduplicate and return up to 60 phrases

    Why bigrams matter:
        "REST" alone matches too broadly. "REST API" is the real skill.
        "machine" alone is useless. "machine learning" is the keyword.
        Without bigrams the comparison misses the most specific JD requirements.

    Args:
        jd_text: raw job description string

    Returns:
        list of lowercase key phrase strings, max 60 items
    """
    if not jd_text:
        return []

    jd_lower = jd_text.lower()

    # ── Step 1: Technical unigrams ────────────────────────────────────
    # Match words that look like tech terms: allow +, #, ., /
    raw_words = re.findall(r'\b[a-z][a-z0-9+#\./\-]{1,25}\b', jd_lower)
    unigrams = [
        w for w in raw_words
        if w not in _JD_STOP
        and len(w) > 2
        # keep tech symbols like c++, c#, .net, node.js
        and not re.match(r'^\d+$', w)
    ]

    # ── Step 2: Meaningful bigrams ────────────────────────────────────
    # Only form bigrams from clean alpha-numeric tokens
    clean_tokens = re.findall(r'\b[a-z][a-z0-9+#\./\-]{1,20}\b', jd_lower)
    bigrams = []
    for i in range(len(clean_tokens) - 1):
        t1 = clean_tokens[i]
        t2 = clean_tokens[i + 1]
        if (t1 not in _JD_STOP
                and t2 not in _JD_STOP
                and len(t1) > 2
                and len(t2) > 2):
            bigram = f"{t1} {t2}"
            bigrams.append(bigram)

    # ── Step 3: Explicit tech pattern extraction ──────────────────────
    # Catches "REST API", "CI/CD", "Node.js v18", "Python 3.x", etc.
    tech_patterns = re.findall(
        r'\b('
        r'rest\s+api|restful\s+api|graphql\s+api|'
        r'ci[/\s]cd|ci\s+pipeline|cd\s+pipeline|'
        r'unit\s+test(?:ing)?|integration\s+test(?:ing)?|'
        r'test\s+driven|test\s+driven\s+development|tdd|'
        r'object[\s\-]oriented|oop|'
        r'machine\s+learning|deep\s+learning|'
        r'natural\s+language\s+processing|nlp|'
        r'data\s+pipeline|data\s+engineer(?:ing)?|'
        r'version\s+control|source\s+control|'
        r'agile\s+method(?:ology)?|scrum\s+master|'
        r'micro\s*service[s]?|event[\s\-]driven|'
        r'cloud\s+native|serverless|'
        r'react(?:\.js)?|vue(?:\.js)?|angular(?:\.js)?|next(?:\.js)?|'
        r'node(?:\.js)?|express(?:\.js)?|'
        r'fast\s*api|spring\s+boot|django\s+rest|'
        r'docker\s+compose|kubernetes\s+cluster|'
        r'postgresql|mysql|mongodb|redis|elasticsearch|'
        r'aws\s+lambda|aws\s+ec2|aws\s+s3|'
        r'azure\s+devops|google\s+cloud|'
        r'git\s+workflow|pull\s+request|code\s+review'
        r')\b',
        jd_lower
    )

    # ── Combine and deduplicate ───────────────────────────────────────
    combined = []
    seen = set()

    # Tech patterns first — highest priority
    for phrase in tech_patterns:
        phrase = phrase.strip()
        if phrase not in seen:
            seen.add(phrase)
            combined.append(phrase)

    # Then bigrams
    for bg in bigrams:
        if bg not in seen:
            seen.add(bg)
            combined.append(bg)

    # Then unigrams (fill remaining slots)
    for ug in unigrams:
        if ug not in seen:
            seen.add(ug)
            combined.append(ug)

    return combined[:60]


def _build_cv_keyword_map(raw_text: str, jd_keyphrases: list) -> dict:
    """
    Build a hit/miss map showing which JD key phrases appear in a CV.

    COMPARE-SPECIFIC: This map is passed to the LLM so it can make
    specific statements like "CV A mentions Docker and Kubernetes which
    the JD requires, but CV B does not mention either."

    Without this, the LLM only sees aggregate scores and produces
    generic verdicts.

    Args:
        raw_text:       cleaned CV text
        jd_keyphrases:  list of phrases from extract_jd_keyphrases()

    Returns:
        dict with keys:
            "matched":  list of JD phrases found in the CV
            "missing":  list of JD phrases NOT found in the CV
            "match_pct": int percentage of JD phrases matched
    """
    cv_lower = raw_text.lower()
    matched = []
    missing = []

    for phrase in jd_keyphrases:
        if phrase in cv_lower:
            matched.append(phrase)
        else:
            missing.append(phrase)

    total = len(jd_keyphrases)
    pct   = round((len(matched) / total) * 100) if total > 0 else 0

    return {
        "matched":   matched[:30],   # cap for LLM prompt size
        "missing":   missing[:30],
        "match_pct": pct,
    }


# ══════════════════════════════════════════════════════════════════════════════
# POST /compare/run
# ══════════════════════════════════════════════════════════════════════════════

@compare_bp.route("/run", methods=["POST"])
@jwt_required()
def run_comparison():
    """
    Run a full CV comparison against a job description.

    Expects multipart/form-data with:
        cv_a            — PDF or DOCX file (required)
        cv_b            — PDF or DOCX file (required)
        job_description — plain text string (required, min 50 chars)

    Returns 200 with full comparison JSON on success.
    Returns 4xx/5xx with error message on failure.
    """
    user_id = get_jwt_identity()

    # ── STEP 1 — Validate inputs ──────────────────────────────────────────
    if "cv_a" not in request.files or "cv_b" not in request.files:
        return jsonify({"error": "Both cv_a and cv_b files are required."}), 400

    file_a = request.files["cv_a"]
    file_b = request.files["cv_b"]
    jd     = request.form.get("job_description", "").strip()

    if not file_a.filename or not file_b.filename:
        return jsonify({"error": "Both files must have a filename."}), 400

    if not _allowed(file_a.filename):
        return jsonify({"error": "CV A must be a PDF or DOCX file."}), 400

    if not _allowed(file_b.filename):
        return jsonify({"error": "CV B must be a PDF or DOCX file."}), 400

    if len(jd) < 50:
        return jsonify({
            "error": "Job description is required (minimum 50 characters)."
        }), 400

    if len(jd) > 8000:
        jd = jd[:8000]

    # ── STEP 2 — Save to temp files ───────────────────────────────────────
    path_a = path_b = None
    try:
        path_a = _save_temp(file_a)
        path_b = _save_temp(file_b)
    except Exception as e:
        _cleanup(path_a, path_b)
        current_app.logger.error(f"Temp file save failed: {e}")
        return jsonify({"error": "Failed to process uploaded files."}), 500

    try:
        # ── STEP 3 — Extract text ─────────────────────────────────────────
        raw_a, err = extract_text_from_file(path_a)
        if err:
            return jsonify({"error": f"Failed to extract text from CV A: {err}"}), 422

        raw_b, err = extract_text_from_file(path_b)
        if err:
            return jsonify({"error": f"Failed to extract text from CV B: {err}"}), 422

        if not raw_a or len(raw_a.strip()) < 50:
            return jsonify({"error": "CV A appears to be empty or unreadable."}), 422

        if not raw_b or len(raw_b.strip()) < 50:
            return jsonify({"error": "CV B appears to be empty or unreadable."}), 422

        # ── STEP 4 — NLP section detection ────────────────────────────────
        sections_a, err = detect_sections(raw_a)
        if err or not sections_a:
            sections_a = {}

        sections_b, err = detect_sections(raw_b)
        if err or not sections_b:
            sections_b = {}

        kw_placement_a, _ = extract_keywords_per_section(sections_a)
        kw_placement_b, _ = extract_keywords_per_section(sections_b)
        kw_placement_a = kw_placement_a or {}
        kw_placement_b = kw_placement_b or {}

        # ── STEP 5 — Extract JD key phrases for compare scoring ───────────
        jd_keyphrases = extract_jd_keyphrases(jd)
        major = _infer_major(jd)

        current_app.logger.info(
            f"Compare: extracted {len(jd_keyphrases)} JD keyphrases, "
            f"inferred major={major}"
        )

        # ── STEP 6 — ATS Scoring with JD keyphrases injected ─────────────
        scoring_a, err = calculate_ats_score(
            raw_text          = raw_a,
            sections          = sections_a,
            keyword_placement = kw_placement_a,
            major             = major,
            job_description   = jd,
            file_path         = path_a,
        )
        if err:
            return jsonify({"error": f"Failed to score CV A: {err}"}), 422

        scoring_b, err = calculate_ats_score(
            raw_text          = raw_b,
            sections          = sections_b,
            keyword_placement = kw_placement_b,
            major             = major,
            job_description   = jd,
            file_path         = path_b,
        )
        if err:
            return jsonify({"error": f"Failed to score CV B: {err}"}), 422

        # ── STEP 7 — Build per-CV JD keyword hit/miss maps ───────────────
        kw_map_a = _build_cv_keyword_map(raw_a, jd_keyphrases)
        kw_map_b = _build_cv_keyword_map(raw_b, jd_keyphrases)

        current_app.logger.info(
            f"Compare keyword maps: "
            f"CV A matched {kw_map_a['match_pct']}% of JD phrases, "
            f"CV B matched {kw_map_b['match_pct']}% of JD phrases"
        )

        # ── STEP 8 — LLM Comparison ───────────────────────────────────────
        comparison_result, err = generate_comparison(
            sections_a      = sections_a,
            scoring_a       = scoring_a,
            sections_b      = sections_b,
            scoring_b       = scoring_b,
            job_description = jd,
            kw_map_a        = kw_map_a,
            kw_map_b        = kw_map_b,
            jd_keyphrases   = jd_keyphrases,
        )
        if err:
            current_app.logger.warning(f"LLM comparison failed: {err}")
            comparison_result = _algorithmic_fallback(scoring_a, scoring_b)

        # ── STEP 9 — Save to DB ───────────────────────────────────────────
        score_a = round(scoring_a["overall_score"], 1)
        score_b = round(scoring_b["overall_score"], 1)

        try:
            fname_a = file_a.filename or "CV A"
            fname_b = file_b.filename or "CV B"

            comparison = ResumeComparison(
                user_id         = user_id,
                comparison_name = f"{fname_a} vs {fname_b}"[:255],
                job_description = jd[:2000],
                winner          = comparison_result["winner"],
                score_a         = score_a,
                score_b         = score_b,
                verdict         = comparison_result.get("verdict", "")[:2000],
            )
            db.session.add(comparison)
            db.session.flush()

            db.session.add(ComparisonResume(
                comparison_id = comparison.id,
                resume_id     = None,
                resume_label  = "a",
                filename      = fname_a[:255],
                score         = score_a,
            ))
            db.session.add(ComparisonResume(
                comparison_id = comparison.id,
                resume_id     = None,
                resume_label  = "b",
                filename      = fname_b[:255],
                score         = score_b,
            ))
            db.session.commit()
            current_app.logger.info(
                f"Comparison {comparison.id} saved: "
                f"winner={comparison_result['winner']} "
                f"({score_a} vs {score_b})"
            )

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"DB save failed for comparison: {e}")

        # ── STEP 10 — Build response ──────────────────────────────────────
        return jsonify({
            "message":  "Comparison completed successfully.",
            "winner":   comparison_result["winner"],
            "summary":  comparison_result.get("summary", ""),
            "verdict":  comparison_result.get("verdict", ""),

            # Per-CV overall scores
            "score_a":  score_a,
            "score_b":  score_b,
            "band_a":   _band(score_a),
            "band_b":   _band(score_b),

            # JD keyword coverage per CV
            "jd_match_pct_a":   kw_map_a["match_pct"],
            "jd_match_pct_b":   kw_map_b["match_pct"],
            "jd_matched_a":     kw_map_a["matched"],
            "jd_matched_b":     kw_map_b["matched"],
            "jd_missing_a":     kw_map_a["missing"],
            "jd_missing_b":     kw_map_b["missing"],
            "jd_total_phrases": len(jd_keyphrases),

            # All 10 criterion scores for both CVs
            "scores_a": {
                "keyword_score":            scoring_a.get("keyword_score"),
                "keyword_placement_score":  scoring_a.get("keyword_placement_score"),
                "formatting_score":         scoring_a.get("formatting_score"),
                "structure_score":          scoring_a.get("structure_score"),
                "experience_recency_score": scoring_a.get("experience_recency_score"),
                "achievements_score":       scoring_a.get("achievements_score"),
                "job_title_score":          scoring_a.get("job_title_score"),
                "education_score":          scoring_a.get("education_score"),
                "resume_length_score":      scoring_a.get("resume_length_score"),
                "contact_info_score":       scoring_a.get("contact_info_score"),
            },
            "scores_b": {
                "keyword_score":            scoring_b.get("keyword_score"),
                "keyword_placement_score":  scoring_b.get("keyword_placement_score"),
                "formatting_score":         scoring_b.get("formatting_score"),
                "structure_score":          scoring_b.get("structure_score"),
                "experience_recency_score": scoring_b.get("experience_recency_score"),
                "achievements_score":       scoring_b.get("achievements_score"),
                "job_title_score":          scoring_b.get("job_title_score"),
                "education_score":          scoring_b.get("education_score"),
                "resume_length_score":      scoring_b.get("resume_length_score"),
                "contact_info_score":       scoring_b.get("contact_info_score"),
            },

            # Strengths & weaknesses per CV
            "strengths_a":  comparison_result.get("strengths_a", []),
            "weaknesses_a": comparison_result.get("weaknesses_a", []),
            "strengths_b":  comparison_result.get("strengths_b", []),
            "weaknesses_b": comparison_result.get("weaknesses_b", []),

            # Missing keywords from ATS scoring
            "missing_keywords_a": (scoring_a.get("missing_keywords") or [])[:10],
            "missing_keywords_b": (scoring_b.get("missing_keywords") or [])[:10],

            # CV Preview fields — raw text + sections for 3-column document rendering
            "raw_text_a":      raw_a,
            "raw_text_b":      raw_b,
            "sections_data_a": sections_a,
            "sections_data_b": sections_b,
            "filename_a":      file_a.filename or "CV A",
            "filename_b":      file_b.filename or "CV B",
        }), 200

    finally:
        _cleanup(path_a, path_b)

# ── Private helpers ───────────────────────────────────────────────────────────

def _infer_major(jd: str) -> str:
    """
    Infer the industry major from JD keywords.
    Defaults to 'technology' if no strong signal found.
    Used as fallback for scoring — JD keyphrases take priority.
    """
    jd_lower = jd.lower()

    signals = {
        "medical":     ["patient", "clinical", "hospital", "healthcare",
                        "medicine", "nursing", "pharmacist", "diagnosis"],
        "financial":   ["accounting", "finance", "audit", "tax", "banking",
                        "investment", "financial", "balance sheet", "cpa"],
        "engineering": ["mechanical", "civil", "electrical", "structural",
                        "cad", "autocad", "manufacturing", "piping"],
        "marketing":   ["marketing", "seo", "campaign", "brand", "social media",
                        "content", "digital marketing", "advertising"],
        "technology":  ["software", "developer", "python", "javascript", "api",
                        "backend", "frontend", "database", "cloud", "devops"],
    }

    scores = {major: 0 for major in signals}
    for major, keywords in signals.items():
        for kw in keywords:
            if kw in jd_lower:
                scores[major] += 1

    return max(scores, key=scores.get)


def _algorithmic_fallback(scoring_a: dict, scoring_b: dict) -> dict:
    """
    Generate a basic comparison result purely from algorithm scores.
    Used when the LLM call fails.
    """
    score_a = scoring_a.get("overall_score", 0)
    score_b = scoring_b.get("overall_score", 0)
    winner  = "a" if score_a >= score_b else "b"
    w_score = score_a if winner == "a" else score_b
    l_score = score_b if winner == "a" else score_a
    diff    = round(abs(score_a - score_b), 1)

    verdict = (
        f"CV {winner.upper()} scored {w_score}/100 compared to "
        f"CV {'B' if winner == 'a' else 'A'}'s {l_score}/100 — "
        f"a difference of {diff} points. "
        f"This comparison is based on the 10-criteria ATS algorithm. "
        f"The AI detailed verdict could not be generated at this time."
    )

    return {
        "winner":       winner,
        "summary":      f"CV {winner.upper()} is the stronger match "
                        f"({w_score} vs {l_score}).",
        "verdict":      verdict,
        "strengths_a":  [],
        "weaknesses_a": [],
        "strengths_b":  [],
        "weaknesses_b": [],
    }