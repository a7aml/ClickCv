"""
services/scoring_service.py  — v4

ATS scoring algorithm — enhanced with three additional fixes:

Fix A — Semantic keyword matching (Criterion 1 & 2):
    Replaces exact string matching with two-tier matching:
    Tier 1: exact/substring match → full points
    Tier 2: semantic cosine similarity ≥ 0.72 → partial points (70%)
    This means "software developer" matches "software engineer",
    "ML" matches "machine learning", "led a team" matches "team leadership".
    sentence-transformers model is lazy-loaded and shared with KeyBERT
    to avoid double-loading the same underlying BERT model.

Fix B — DOCX structural formatting detection (Criterion 3):
    Uses python-docx to inspect tables, inline shapes (images),
    and text box presence in DOCX files — same penalties as PDF.
    Previously DOCX files always passed formatting with no structural check.

Fix C — Section header fuzzy matching (nlp_service.py companion):
    This file's _score_section_completeness() now receives the raw
    detected section names and does not penalise headers that were
    close matches but not exact. The fuzzy matching itself is in
    nlp_service.py — see that file's _is_header_line() function.

Unchanged from v2:
    - All 10 criteria weights
    - Score bands
    - Keyword placement scoring
    - Experience recency
    - Achievements patterns
    - Job title matching
    - Education scoring
    - Resume length
    - Contact info
"""

import re
import os
from datetime import datetime


# ── Semantic similarity model — lazy loaded ───────────────────────────────────
# Shared with KeyBERT — both use 'all-MiniLM-L6-v2' under the hood.
# We use the SentenceTransformer directly so we can encode batches
# efficiently rather than calling KeyBERT one phrase at a time.
_sem_model = None
_sem_model_available = None   # None = untested, True/False after first attempt


def _get_sem_model():
    """
    Return the shared SentenceTransformer model, or None if unavailable.
    Caches the availability result so we only try to load once.
    Sets _sem_model_available flag so callers can fall back gracefully.
    """
    global _sem_model, _sem_model_available

    if _sem_model_available is True:
        return _sem_model

    if _sem_model_available is False:
        return None   # Already failed — don't retry every call

    try:
        from sentence_transformers import SentenceTransformer
        _sem_model = SentenceTransformer("all-MiniLM-L6-v2")
        _sem_model_available = True
        return _sem_model
    except Exception:
        _sem_model_available = False
        return None


# ── Industry keyword databases ────────────────────────────────────────────────
# ── Industry keyword databases — loaded from JSON files ──────────────────────
# Keywords live in app/data/keywords/*.json — edit those files to add terms.
# Never hardcode keywords here. See keywords_loader.py for the loading logic.
from app.data.keywords.keywords_loader import get_keywords as _get_industry_keywords


# ── Weights ───────────────────────────────────────────────────────────────────
WEIGHTS = {
    "keyword_score":             0.35,
    "keyword_placement_score":   0.18,
    "formatting_score":          0.17,
    "structure_score":           0.12,
    "experience_recency_score":  0.10,
    "achievements_score":        0.10,
    "job_title_score":           0.08,
    "education_score":           0.07,
    "resume_length_score":       0.04,
    "contact_info_score":        0.03,
}

SCORE_BANDS = {
    "strong":     (75.0, 100.0),
    "good":       (65.0,  74.9),   # FIX: 74→74.9 closes float gap
    "borderline": (50.0,  64.9),   # FIX: 64→64.9 closes float gap
    "weak":       (0.0,   49.9),   # FIX: 49→49.9 closes float gap
}

# Semantic similarity threshold for partial keyword match credit
# 0.72 = "software engineer" ↔ "software developer" (close synonyms pass)
# 0.72 = "machine learning" ↔ "ml" (acronym/expansion pairs pass)
# 0.72 excludes irrelevant words — tested against common false positives
SEMANTIC_THRESHOLD = 0.62  # Lowered from 0.72 after live testing

# Partial credit multiplier when semantic (not exact) match is found
SEMANTIC_CREDIT = 0.70   # 70% of full points — exact match still wins

# JD stop words — excluded so max_points stays proportional to real skills
JD_STOP_WORDS = {
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
    "other", "more", "than", "such", "each", "get", "set",
    # Extra stops added after live testing — these appeared in JD pool as garbage
    "paste", "here", "alongside", "similar", "exposure", "pull", "write",
    "assist", "maintain", "optimize", "deploy", "monitor", "document",
    "participate", "collaborate", "understand", "familiarity", "proficiency",
    "powering", "testable", "scalable", "relevant", "motivated", "intern",
    "above", "below", "follow", "following", "across", "within", "between",
    "request", "requests", "workflows", "ceremonies", "coverage", "schemas",
    "specifications", "queries", "saas", "users", "platform", "services",
    "endpoints", "standards", "concepts", "practices", "processes",
}



# ── Public API ────────────────────────────────────────────────────────────────

def calculate_ats_score(
    raw_text:           str,
    sections:           dict,
    keyword_placement:  dict,
    major:              str,
    job_description:    str = None,
    file_path:          str = None,
) -> tuple:
    """
    Run all 10 ATS criteria and return the composite score with breakdown.

    Args:
        raw_text:          full cleaned resume text
        sections:          dict from nlp_service.detect_sections()
        keyword_placement: dict from nlp_service.extract_keywords_per_section()
        major:             industry string e.g. 'technology'
        job_description:   optional raw JD text
        file_path:         path to uploaded PDF/DOCX for structural check

    Returns:
        (result_dict, None) or (None, error_string)
    """
    if not raw_text or not sections:
        return None, "No resume data provided for scoring."

    major = (major or "technology").lower()
    if major not in {"technology", "medical", "engineering", "financial", "marketing"}:
        major = "technology"

    jd_required, jd_preferred = (
        _parse_jd_keywords(job_description)
        if job_description and job_description.strip()
        else ([], [])
    )
    used_jd = bool(jd_required or jd_preferred)

    if not used_jd:
        jd_required, jd_preferred = _get_industry_keywords(major)

    resume_lower = raw_text.lower()

    # ── Pre-compute resume sentence embeddings once ───────────────────────────
    # We split the resume into sentences and encode them all in one batch.
    # Each keyword is then compared against all sentence embeddings.
    # This is far more efficient than encoding the whole resume as one string
    # (which truncates at 512 tokens for BERT-based models).
    resume_embeddings = _encode_resume_sentences(resume_lower)

    c1, missing_kw  = _score_keyword_matching(
                            resume_lower, jd_required, jd_preferred,
                            resume_embeddings)
    c2              = _score_keyword_placement(
                            keyword_placement, jd_required, jd_preferred,
                            resume_embeddings)
    c3              = _score_formatting(raw_text, file_path)
    c4, missing_sec = _score_section_completeness(sections)
    c5              = _score_experience_recency(sections)
    c6              = _score_achievements(sections)
    c7              = _score_job_title_matching(sections, jd_required)
    c8              = _score_education(sections)
    c9              = _score_resume_length(raw_text)
    c10             = _score_contact_info(sections, raw_text)

    overall = (
        c1  * WEIGHTS["keyword_score"]            +
        c2  * WEIGHTS["keyword_placement_score"]  +
        c3  * WEIGHTS["formatting_score"]         +
        c4  * WEIGHTS["structure_score"]          +
        c5  * WEIGHTS["experience_recency_score"] +
        c6  * WEIGHTS["achievements_score"]       +
        c7  * WEIGHTS["job_title_score"]          +
        c8  * WEIGHTS["education_score"]          +
        c9  * WEIGHTS["resume_length_score"]      +
        c10 * WEIGHTS["contact_info_score"]
    )
    overall = round(min(max(overall, 0), 100), 1)

    band = "weak"
    for band_name, (low, high) in SCORE_BANDS.items():
        if low <= overall <= high:
            band = band_name
            break

    return {
        "overall_score":            overall,
        "keyword_score":            round(c1,  1),
        "keyword_placement_score":  round(c2,  1),
        "formatting_score":         round(c3,  1),
        "structure_score":          round(c4,  1),
        "experience_recency_score": round(c5,  1),
        "achievements_score":       round(c6,  1),
        "job_title_score":          round(c7,  1),
        "education_score":          round(c8,  1),
        "resume_length_score":      round(c9,  1),
        "contact_info_score":       round(c10, 1),
        "missing_sections":         missing_sec,
        "missing_keywords":         missing_kw,
        "score_band":               band,
        "used_jd":                  used_jd,
    }, None


def get_score_interpretation(score: float) -> dict:
    """Return human-readable interpretation of an ATS score."""
    if score >= 75:
        return {"band": "strong",     "label": "Strong Match",
                "interview_probability": "High — Very likely to get interview",
                "llm_action": "polishing"}
    elif score >= 65:
        return {"band": "good",       "label": "Good Match",
                "interview_probability": "Moderate — Possible interview",
                "llm_action": "targeted_fixes"}
    elif score >= 50:
        return {"band": "borderline", "label": "Borderline",
                "interview_probability": "Low — Needs improvement",
                "llm_action": "major_rewrites"}
    else:
        return {"band": "weak",       "label": "Weak Match",
                "interview_probability": "Very Low — Significant improvements needed",
                "llm_action": "full_restructure"}


# ══════════════════════════════════════════════════════════════════════
# FIX A — Semantic helpers
# ══════════════════════════════════════════════════════════════════════

def _encode_resume_sentences(resume_lower: str):
    """
    Split the resume into sentences and encode them all in one batch.

    Returns a tuple (sentences_list, embeddings_tensor) or None if
    the semantic model is unavailable.

    Why sentences not the whole text:
        BERT-based models truncate input at 512 tokens (~380 words).
        A full resume is 300-900 words — it would be truncated.
        Encoding sentence-by-sentence then searching across all
        sentences captures keywords anywhere in the document.

    Args:
        resume_lower: full lowercased resume text

    Returns:
        (sentences, embeddings) tuple or None
    """
    model = _get_sem_model()
    if model is None:
        return None   # Semantic model not available — callers fall back to exact

    # Split on newlines and semicolons only — NOT on periods
    # Splitting on "." breaks emails (daniel.lim@...), URLs, and abbreviations
    # Use newlines as the primary sentence boundary for resumes
    raw_chunks = re.split(r'\n+', resume_lower)
    sentences = []
    for chunk in raw_chunks:
        chunk = chunk.strip().lstrip('•-*> ')
        if chunk and len(chunk) > 8:
            sentences.append(chunk)

    if not sentences:
        return None

    try:
        embeddings = model.encode(sentences, convert_to_tensor=True,
                                  show_progress_bar=False)
        return (sentences, embeddings)
    except Exception:
        return None


def _keyword_matches(
    kw: str,
    resume_lower: str,
    resume_embeddings,
) -> tuple:
    """
    Two-tier keyword matching:
        Tier 1 — Exact/substring: kw in resume_lower → returns (True, 1.0)
        Tier 2 — Semantic: cosine similarity ≥ SEMANTIC_THRESHOLD
                           → returns (True, SEMANTIC_CREDIT)
        No match → returns (False, 0.0)

    The credit multiplier allows callers to award full points for exact
    matches and partial points for semantic matches.

    Args:
        kw:               keyword to search for (already lowercased)
        resume_lower:     full lowercased resume text
        resume_embeddings: (sentences, embeddings) tuple or None

    Returns:
        (matched: bool, credit: float)
    """
    # Tier 1 — exact substring match (fast, no model needed)
    if kw in resume_lower:
        return True, 1.0

    # Tier 2 — semantic similarity (only if model available)
    if resume_embeddings is None:
        return False, 0.0

    model = _get_sem_model()
    if model is None:
        return False, 0.0

    try:
        from sentence_transformers import util

        sentences, embeddings = resume_embeddings
        kw_embedding = model.encode(kw, convert_to_tensor=True,
                                    show_progress_bar=False)

        # Compare keyword against all sentence embeddings — take the max
        similarities = util.cos_sim(kw_embedding, embeddings)[0]
        max_sim = float(similarities.max())

        if max_sim >= SEMANTIC_THRESHOLD:
            return True, SEMANTIC_CREDIT

        return False, 0.0

    except Exception:
        return False, 0.0


# ══════════════════════════════════════════════════════════════════════
# CRITERION 1 — Keyword Matching (35%)
# ══════════════════════════════════════════════════════════════════════

def _parse_jd_keywords(jd_text: str) -> tuple:
    """
    Extract meaningful required keywords from a JD text.
    Filters stop words and caps the pool to keep scoring fair.
    """
    if not jd_text:
        return [], []

    jd_lower = jd_text.lower()

    words = re.findall(r'\b[a-z][a-z0-9+#\./\-]{1,30}\b', jd_lower)
    required = list({
        w for w in words
        if w not in JD_STOP_WORDS and len(w) > 2
    })[:40]

    tokens = re.findall(r'\b[a-z][a-z0-9+#/\-]{1,20}\b', jd_lower)
    bigrams = [
        f"{tokens[i]} {tokens[i+1]}"
        for i in range(len(tokens) - 1)
        if tokens[i] not in JD_STOP_WORDS
        and tokens[i+1] not in JD_STOP_WORDS
        and len(tokens[i]) > 2
        and len(tokens[i+1]) > 2
    ]
    required.extend(list(set(bigrams))[:20])

    # Cap total pool — prevents very long JDs from diluting scores
    # and ensures consistent scoring regardless of JD verbosity
    required = required[:50]

    return required, []


def _score_keyword_matching(
    resume_lower:      str,
    jd_required:       list,
    jd_preferred:      list,
    resume_embeddings,
) -> tuple:
    """
    Criterion 1 — Keyword Matching (35%)

    Two-tier matching:
        Exact match:    full points  (10 req / 5 pref)
        Semantic ≥0.62: 70% points   (7 req / 3.5 pref)
        No match:       0 → added to missing list

    Normalisation fix for large databases (200+ keywords):
        Divides by a REALISTIC CEILING instead of the theoretical max.
        Ceiling = what a near-expert CV can achieve:
            85% of required at full points
            50% of preferred at full points

        This prevents the pool-size dilution problem where a strong CV
        matching 80 of 242 keywords scores only 28% because max_points
        is 1585. With ceiling normalisation the same CV scores 80-90%.

        When a JD is provided the pool is small (~50 terms) so the
        ceiling adjustment is minimal — JD mode is self-normalising.
    """
    if not jd_required and not jd_preferred:
        return 50.0, []

    points  = 0.0
    missing = []

    for kw in jd_required:
        matched, credit = _keyword_matches(kw.lower(), resume_lower, resume_embeddings)
        if matched:
            points += 10 * credit
        else:
            missing.append(kw)

    for kw in jd_preferred:
        matched, credit = _keyword_matches(kw.lower(), resume_lower, resume_embeddings)
        if matched:
            points += 5 * credit

    # ── Normalisation ────────────────────────────────────────────────
    n_req  = len(jd_required)
    n_pref = len(jd_preferred)

    if n_req == 0 and n_pref == 0:
        return 50.0, []

    # For large industry databases (no JD): use realistic ceiling
    # For small JD pools (<60 total): use standard max_points
    total_pool = n_req + n_pref
    if total_pool >= 60:
        # Ceiling = near-expert CV benchmark
        ceiling = (n_req * 0.85 * 10) + (n_pref * 0.50 * 5)
    else:
        # JD mode — small pool, standard normalisation
        ceiling = (n_req * 10) + (n_pref * 5)

    if ceiling == 0:
        return 50.0, []

    score = (points / ceiling) * 100
    return round(min(score, 100), 1), missing[:20]


# ══════════════════════════════════════════════════════════════════════
# CRITERION 2 — Keyword Placement (18%)
# ══════════════════════════════════════════════════════════════════════

def _score_keyword_placement(
    keyword_placement: dict,
    jd_required:       list,
    jd_preferred:      list,
    resume_embeddings,                # NEW — for semantic section matching
) -> float:
    """
    Criterion 2 — Keyword Placement (18%)

    FIX A — Now uses two-tier matching when checking if a keyword
    appears in a section. The section content is checked with both
    exact match and semantic similarity so synonyms still contribute.

    The section weight hierarchy is unchanged:
        Summary=1.0, Skills=0.9, Experience=0.7, Education=0.5 ...

    Args:
        keyword_placement: dict from nlp_service.extract_keywords_per_section()
        jd_required:       required keyword list
        jd_preferred:      preferred keyword list
        resume_embeddings: pre-computed (sentences, embeddings) or None

    Returns:
        score 0-100
    """
    if not keyword_placement or (not jd_required and not jd_preferred):
        return 50.0

    all_targets = [kw.lower() for kw in (jd_required + jd_preferred)]
    if not all_targets:
        return 50.0

    # Pre-encode section contents for semantic search
    # We encode each section's text separately so we can search within sections
    section_data = {}
    model = _get_sem_model()

    for section_name, data in keyword_placement.items():
        section_kws = [k.lower() for k in data.get("keywords", [])]
        section_text = " ".join(section_kws)
        section_emb  = None

        if model and section_text.strip():
            try:
                section_emb = model.encode(
                    section_text, convert_to_tensor=True,
                    show_progress_bar=False
                )
            except Exception:
                pass

        section_data[section_name] = {
            "keywords": section_kws,
            "weight":   data.get("weight", 0.1),
            "embedding": section_emb,
        }

    total_weighted = 0.0
    max_weighted   = 0.0

    for kw in all_targets:
        max_weighted += 1.0
        best_weight   = 0.0

        for section_name, sdata in section_data.items():
            section_kws = sdata["keywords"]
            weight      = sdata["weight"]
            sec_emb     = sdata["embedding"]

            # Tier 1 — exact substring in section keywords
            exact_match = any(kw in sk or sk in kw for sk in section_kws)

            if exact_match:
                if weight > best_weight:
                    best_weight = weight
                continue

            # Tier 2 — semantic similarity against section keyword text
            if model is not None and sec_emb is not None:
                try:
                    from sentence_transformers import util
                    kw_emb = model.encode(kw, convert_to_tensor=True,
                                          show_progress_bar=False)
                    sim = float(util.cos_sim(kw_emb, sec_emb).item())
                    if sim >= SEMANTIC_THRESHOLD:
                        # Partial weight credit for semantic placement match
                        effective_weight = weight * SEMANTIC_CREDIT
                        if effective_weight > best_weight:
                            best_weight = effective_weight
                except Exception:
                    pass

        total_weighted += best_weight

    if max_weighted == 0:
        return 50.0

    # Apply same ceiling normalisation as keyword matching
    # For large pools (≥60 terms), use realistic ceiling so scores
    # are proportional — strong CVs score 75-90, not 25-35
    total_pool = len(all_targets)
    if total_pool >= 60:
        # KeyBERT extracts ~15 keywords per section × ~5 sections = ~75 total
        # Only ~35% of the full database pool gets matched via section keywords
        # Ceiling reflects this realistic extraction limit
        ceiling = max_weighted * 0.35
    else:
        ceiling = max_weighted          # JD mode — standard normalisation

    if ceiling == 0:
        return 50.0

    return round(min((total_weighted / ceiling) * 100, 100), 1)


# ══════════════════════════════════════════════════════════════════════
# CRITERION 3 — Formatting / Parsability (17%)
# ══════════════════════════════════════════════════════════════════════

def _score_formatting(raw_text: str, file_path: str = None) -> float:
    """
    Criterion 3 — Resume Parsability / Formatting (17%)

    PDF structural penalties (via PyMuPDF):
        Images/graphics detected:           -20
        Table rectangles (>4 filled rects): -15
        Table rectangles (2-4):             -8
        Multi-column layout detected:       -15
        Content in header zone (top 8%):    -15
        Content in footer zone (bot 8%):    -10
        More than 4 font families:          -10
        3-4 font families:                  -5

    FIX B — DOCX structural penalties (NEW, via python-docx):
        Tables detected in DOCX:            -15
        Inline images/shapes in DOCX:       -20
        Text boxes (via XML check):         -15
        More than 3 paragraph styles:       -5

    Text-based penalties (always applied):
        Excessive decorative special chars: -15
        High non-ASCII symbol ratio >3%:    -15
        High non-ASCII symbol ratio >1%:    -8
        No standard date format found:      -5

    Text-based bonus:
        High alphabetic ratio (>70%):       +5
    """
    score = 100.0

    if file_path and os.path.exists(file_path):
        ext = os.path.splitext(file_path)[1].lower()

        # ── PDF inspection ────────────────────────────────────────────
        if ext == ".pdf":
            try:
                import fitz
                doc  = fitz.open(file_path)
                page = doc[0]
                pw   = page.rect.width
                ph   = page.rect.height

                # 1. Images / graphics
                images = page.get_images(full=True)
                if images:
                    score -= 20

                # 2. Table detection via filled rectangle drawings
                drawings     = page.get_drawings()
                filled_rects = [
                    d for d in drawings
                    if d.get("type") == "re" and d.get("fill") is not None
                ]
                if len(filled_rects) > 4:
                    score -= 15
                elif len(filled_rects) > 1:
                    score -= 8

                # 3. Multi-column detection via text block x-positions
                blocks = page.get_text("blocks")
                if blocks:
                    x_buckets = {}
                    for b in blocks:
                        bucket = int(b[0] / 100) * 100
                        x_buckets[bucket] = x_buckets.get(bucket, 0) + 1
                    col_zones = [k for k, v in x_buckets.items() if v >= 3]
                    if len(col_zones) >= 2:
                        score -= 15

                # 4. Header zone — top 8% of page
                header_rect = fitz.Rect(0, 0, pw, ph * 0.08)
                header_text = page.get_text("text", clip=header_rect).strip()
                if len(header_text) > 30:
                    score -= 15

                # 5. Footer zone — bottom 8% of page
                footer_rect = fitz.Rect(0, ph * 0.92, pw, ph)
                footer_text = page.get_text("text", clip=footer_rect).strip()
                if len(footer_text) > 30:
                    score -= 10

                # 6. Too many font families
                fonts        = page.get_fonts()
                unique_fonts = len(set(f[3] for f in fonts))
                if unique_fonts > 4:
                    score -= 10
                elif unique_fonts > 3:
                    score -= 5

                doc.close()

            except Exception:
                pass   # Fall through to text-based checks

        # ── DOCX inspection (FIX B) ───────────────────────────────────
        elif ext in (".docx", ".doc"):
            try:
                from docx import Document
                from docx.oxml.ns import qn

                doc = Document(file_path)

                # 1. Tables — each table is a layout failure for ATS
                if doc.tables:
                    # More tables = worse penalty
                    if len(doc.tables) > 2:
                        score -= 15
                    else:
                        score -= 8

                # 2. Inline images — ATS cannot parse embedded images
                inline_shapes = doc.inline_shapes
                if len(inline_shapes) > 0:
                    score -= 20

                # 3. Text boxes — stored as drawing canvas in OOXML
                # Check for txbxContent elements in the XML
                body_xml = doc.element.body.xml
                text_box_count = body_xml.count("txbxContent")
                if text_box_count > 0:
                    score -= 15

                # 4. Excessive paragraph styles = inconsistent/complex layout
                # Count unique named styles used (ignore default Normal/Body)
                used_styles = set()
                for para in doc.paragraphs:
                    if para.style and para.style.name:
                        style_name = para.style.name.lower()
                        # Ignore base styles that are always present
                        if style_name not in ("normal", "default paragraph font",
                                               "body text", "no spacing", "list paragraph"):
                            used_styles.add(style_name)
                if len(used_styles) > 5:
                    score -= 5

            except Exception:
                pass   # Fall through to text-based checks

    # ── Text-based checks (always run for both PDF and DOCX) ─────────
    # Decorative special characters — box drawing, symbols, emoji
    special_ratio = (
        len(re.findall(r'[│┃▪▸►●◆■□★☆✦❋⬡]', raw_text))
        / max(len(raw_text), 1)
    )
    if special_ratio > 0.005:
        score -= 15

    # High non-ASCII ratio — suggests emoji, symbols, or extraction artifacts
    non_ascii_ratio = (
        len(re.findall(r'[^\x20-\x7E\n]', raw_text))
        / max(len(raw_text), 1)
    )
    if non_ascii_ratio > 0.03:
        score -= 15
    elif non_ascii_ratio > 0.01:
        score -= 8

    # No standard date formats — ATS cannot parse experience timeline
    date_pattern = re.compile(
        r'\b(19|20)\d{2}\b|'
        r'\b\d{1,2}/\d{4}\b|'
        r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)'
        r'[a-z]*[\s\-,]+(19|20)\d{2}\b',
        re.IGNORECASE
    )
    if not date_pattern.search(raw_text):
        score -= 5

    # Bonus: clean high-alpha text is ATS-friendly
    alpha_ratio = len(re.findall(r'[a-zA-Z]', raw_text)) / max(len(raw_text), 1)
    if alpha_ratio > 0.70:
        score = min(score + 5, 100)

    return round(max(score, 0), 1)


# ══════════════════════════════════════════════════════════════════════
# CRITERION 4 — Section Completeness (12%)
# ══════════════════════════════════════════════════════════════════════

def _score_section_completeness(sections: dict) -> tuple:
    """
    Criterion 4 — Section Completeness (12%)

    Starts at 0 — no free points.
    Required section present: +18 pts (5 × 18 = 90 max)
    Bonus section present:    +2.5 pts (4 × 2.5 = 10 max)
    Total possible: 100

    NOTE: The fuzzy section header matching (Fix C) is implemented in
    nlp_service._is_header_line() using difflib.SequenceMatcher.
    By the time sections reach this function, non-standard headers
    like "PROFESSIONAL BACKGROUND" are already mapped to "experience".
    This function does not need to change — the fix is upstream.
    """
    required = ["contact", "summary", "experience", "education", "skills"]
    bonus    = ["certifications", "projects", "achievements", "languages"]

    score   = 0.0
    missing = []

    for section in required:
        if section in sections:
            score += 18.0
        else:
            missing.append(section)

    for section in bonus:
        if section in sections:
            score += 2.5

    return round(min(score, 100), 1), missing


# ══════════════════════════════════════════════════════════════════════
# CRITERION 5 — Experience Recency (10%)
# ══════════════════════════════════════════════════════════════════════

def _score_experience_recency(sections: dict) -> float:
    """Criterion 5 — Experience Recency (10%) — unchanged from v2."""
    experience_text = sections.get("experience", "")
    if not experience_text:
        return 30.0

    current_year = datetime.now().year
    years_found  = re.findall(r'\b(19|20)(\d{2})\b', experience_text)
    if not years_found:
        return 50.0

    years = [int(f"{y[0]}{y[1]}") for y in years_found]

    if re.search(r'\b(present|current|now|ongoing)\b',
                 experience_text, re.IGNORECASE):
        return 100.0

    years_ago = current_year - max(years)
    if years_ago <= 3:    return 100.0   # FIX: 2→3 years boundary
    elif years_ago <= 6:  return 75.0    # FIX: 5→6 years boundary
    elif years_ago <= 12: return 50.0    # FIX: 10→12 years boundary
    else:                 return 25.0


# ══════════════════════════════════════════════════════════════════════
# CRITERION 6 — Quantifiable Achievements (10%)
# ══════════════════════════════════════════════════════════════════════

def _score_achievements(sections: dict) -> float:
    """Criterion 6 — Quantifiable Achievements (10%) — unchanged from v2."""
    target_sections = ["experience", "achievements", "projects", "summary"]
    combined = " ".join(sections.get(s, "") for s in target_sections).lower()

    if not combined.strip():
        return 20.0

    achievement_patterns = [
        r'\d+\s*%',
        r'\$\s*[\d,]+[kmb]?',
        r'rm\s*[\d,\.]+\s*[kmb]?',       # catches RM 4.2B, RM2.4M, RM 1.1B
        r'[\d,]+\s*(users|customers|clients|students)',
        r'\d+\s*(engineers|developers|people|members|employees|staff)',
        r'(reduced|increased|improved|decreased|grew|saved|generated|cut|'
        r'boosted|accelerated)\s+\w+\s+by\s+\d+',
        r'(led|managed|supervised|oversaw|headed)\s+\w*\s*(team|group|department|squad)',
        r'\d+[kmb]\+?\s*(revenue|sales|downloads|requests|transactions)',
        r'(top|ranked|award|recognition|honour|best|winner|first)',
        r'(delivered|launched|deployed|shipped|released)\s+\d+',
        r'\d+\s*(projects|products|systems|applications|features)',
        r'(served|handled|processed|supported)\s+\d+',
        r'(within|ahead of|under)\s+(budget|schedule|deadline)',
        r'\d+(\.\d+)?\s*(billion|million|thousand)',          # 1.2 billion, 4.2 million
        r'(annualised|annual|quarterly|monthly)\s+return',       # investment returns
        r'basis\s+point',                                         # finance: bps
        r'\d+\s*(publication|paper|journal|study|trial)',        # medical/research
        r'(outperform|outperformed|exceed|exceeded)\s',           # exceeded targets
        r'(patient|client|customer)\s+satisfaction',              # service quality
        r'(zero|no)\s+(defect|incident|accident|failure)',        # quality/safety
    ]

    weak_patterns = [
        r'responsible for', r'worked on', r'helped with',
        r'involved in', r'assisted with', r'participated in',
    ]

    found_count = sum(
        len(re.findall(p, combined, re.IGNORECASE))
        for p in achievement_patterns
    )
    weak_count = sum(
        len(re.findall(p, combined, re.IGNORECASE))
        for p in weak_patterns
    )

    score = 20.0 + (found_count * 5) - (weak_count * 3)
    return round(min(max(score, 0), 100), 1)


# ══════════════════════════════════════════════════════════════════════
# CRITERION 7 — Job Title Matching (8%)
# ══════════════════════════════════════════════════════════════════════

def _score_job_title_matching(sections: dict, jd_keywords: list) -> float:
    """Criterion 7 — Job Title Matching (8%) — unchanged from v2."""
    experience_text = sections.get("experience", "").lower()
    summary_text    = sections.get("summary",    "").lower()
    combined        = experience_text + " " + summary_text

    if not combined.strip():
        return 30.0

    score = 30.0
    title_patterns = re.findall(
        r'(?:engineer|developer|analyst|manager|designer|scientist|'
        r'architect|consultant|specialist|director|lead|officer|'
        r'coordinator|administrator|executive|associate)',
        combined, re.IGNORECASE
    )
    if title_patterns:
        score += min(len(set(title_patterns)) * 15, 40)

    seniority_words = ["senior", "lead", "principal", "staff", "junior",
                       "mid", "manager", "head", "chief", "vp", "director"]
    if any(sw in combined for sw in seniority_words):
        score += 10

    jd_in_experience = sum(
        1 for kw in jd_keywords if kw.lower() in experience_text
    )
    score += min(jd_in_experience * 2, 20)

    return round(min(score, 100), 1)


# ══════════════════════════════════════════════════════════════════════
# CRITERION 8 — Education & Certifications (7%)
# ══════════════════════════════════════════════════════════════════════

def _score_education(sections: dict) -> float:
    """Criterion 8 — Education & Certifications (7%) — unchanged from v2."""
    education_text = sections.get("education", "").lower()
    certs_text     = sections.get("certifications", "").lower()
    combined       = education_text + " " + certs_text

    if not combined.strip():
        return 0.0

    score = 0.0

    degree_patterns = [
        r'\b(bsc|b\.sc|bachelor|ba|b\.a|beng|b\.eng)\b',
        r'\b(msc|m\.sc|master|ma|m\.a|mba|m\.b\.a|meng)\b',
        r'\b(phd|ph\.d|doctorate|doctor)\b',
        r'\b(diploma|certificate|associate|hnd|foundation)\b',
    ]
    for pattern in degree_patterns:
        if re.search(pattern, education_text, re.IGNORECASE):
            score += 25
            break

    field_keywords = [
        "computer science", "software engineering", "information technology",
        "computing", "computing and information", "information systems",
        "computer studies", "engineering", "civil engineering",
        "mechanical engineering", "electrical engineering",
        "structural engineering", "chemical engineering",
        "medicine", "mbbs", "medical", "surgery", "clinical",
        "finance", "accounting", "accountancy", "financial",
        "commerce", "business administration",
        "marketing", "mass communication", "communications",
        "business", "data science", "mathematics", "physics", "chemistry",
        "biology", "economics", "management", "nursing", "pharmacy",
        "cardiology", "internal medicine", "biomedical",
        "investment", "cfa", "acca", "mba",
    ]
    for field in field_keywords:
        if field in education_text:
            score += 20
            break

    cert_keywords = [
        "certified", "certification", "certificate", "aws", "google",
        "microsoft", "cisco", "pmp", "cpa", "cfa", "comptia",
        "professional", "associate", "expert", "specialist"
    ]
    cert_count = sum(1 for ck in cert_keywords if ck in certs_text)
    score += min(cert_count * 10, 30)

    org_names = ["amazon", "google", "microsoft", "cisco", "pmi",
                 "aicpa", "cfa institute", "isaca", "ec-council"]
    if any(org in certs_text for org in org_names):
        score += 5

    return round(min(score, 100), 1)


# ══════════════════════════════════════════════════════════════════════
# CRITERION 9 — Resume Length (4%)
# ══════════════════════════════════════════════════════════════════════

def _score_resume_length(raw_text: str) -> float:
    """
    Criterion 9 — Resume Length (4%)

    FIX: Expanded upper bands for senior professional CVs.
    A 16-year career professional SHOULD have more than 900 words.
    Old bands penalised strong CVs for being detailed and complete.

    Bands:
        300–1200 words  → 100  (optimal: entry to senior)
        200–299 words   → 80   (slightly short)
        1200–1600 words → 85   (senior CV — long but acceptable)
        1600–2000 words → 70   (very detailed — minor penalty)
        150–199 words   → 60   (too short)
        100–149 words   → 40   (much too short)
        >2000 words     → 55   (significantly over)
        <100 words      → 20   (barely a CV)
    """
    wc = len(raw_text.split())
    if   300  <= wc <= 1200:  return 100.0
    elif 200  <= wc <  300:   return 80.0
    elif 1200 <  wc <= 1600:  return 85.0
    elif 1600 <  wc <= 2000:  return 70.0
    elif 150  <= wc <  200:   return 60.0
    elif 100  <= wc <  150:   return 40.0
    elif wc   >  2000:        return 55.0
    else:                     return 20.0


# ══════════════════════════════════════════════════════════════════════
# CRITERION 10 — Contact Information (3%)
# ══════════════════════════════════════════════════════════════════════

def _score_contact_info(sections: dict, raw_text: str) -> float:
    """Criterion 10 — Contact Information Readability (3%) — unchanged."""
    search_text  = sections.get("contact", "") or raw_text
    search_lower = search_text.lower()
    score        = 0.0

    if re.search(r'\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b',
                 raw_text):
        score += 30
    if re.search(r'(\+?\d[\d\s\-\(\)]{7,15}\d)', raw_text):
        score += 20
    if "linkedin.com" in search_lower or "linkedin" in search_lower:
        score += 15

    location_keywords = [
        "kuala lumpur", "malaysia", "singapore", "london", "new york",
        "dubai", "remote", "city", "state", "country", "location",
        "address", "based in", "residing"
    ]
    if any(loc in search_lower for loc in location_keywords):
        score += 15

    first_lines = [l.strip() for l in raw_text.split("\n") if l.strip()][:3]
    for line in first_lines:
        if re.match(r'^[A-Z][a-z]+([\s\-][A-Z][a-z]+){1,3}$', line):
            score += 20
            break

    return round(min(score, 100), 1)