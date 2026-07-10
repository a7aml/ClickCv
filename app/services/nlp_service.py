"""
services/nlp_service.py  — v3

Section detection, keyword extraction, and keyword placement scoring.

FIX C — Fuzzy section header matching:
    The original _is_header_line() only matched exact keywords from
    SECTION_KEYWORDS. This penalised candidates who wrote:
        "PROFESSIONAL BACKGROUND"  instead of  "EXPERIENCE"
        "TECHNICAL EXPERTISE"      instead of  "SKILLS"
        "CAREER HISTORY"           instead of  "EXPERIENCE"
    
    The fix adds a two-tier matching strategy:
        Tier 1: exact match against SECTION_KEYWORDS (unchanged, fast)
        Tier 2: difflib.SequenceMatcher fuzzy ratio ≥ 0.72 against all
                canonical section names — catches creative header variants
                without needing a training model
    
    Why difflib not semantic similarity for headers:
        Section headers are short (1-4 words). Semantic models sometimes
        produce unexpected similarities between short phrases.
        difflib character-level similarity is more reliable for detecting
        near-synonym headers like "WORK HISTORY" → "work experience".
        Threshold 0.72 was chosen to accept clear synonyms while
        rejecting body-text lines that happen to contain section words.

    Additional header patterns added to SECTION_KEYWORDS to reduce
    reliance on fuzzy matching for the most common variants.
"""

import re
from difflib import SequenceMatcher
from keybert import KeyBERT


# ── Get shared KeyBERT model ──────────────────────────────────────────────────
from app.services.model_loader import get_keybert_model


def _get_kw_model() -> KeyBERT:
    """Get the shared KeyBERT model instance (pre-loaded at startup)."""
    return get_keybert_model()

# ── Section keyword map ───────────────────────────────────────────────────────
# Extended with additional common variants to reduce fuzzy matching load.

SECTION_KEYWORDS = {

    # Contact
    "contact":                      "contact",
    "contact information":          "contact",
    "contact details":              "contact",
    "personal information":         "contact",
    "personal details":             "contact",
    "personal data":                "contact",
    "find me":                      "contact",   # creative variant

    # Summary
    "summary":                      "summary",
    "professional summary":         "summary",
    "career summary":               "summary",
    "executive summary":            "summary",
    "profile":                      "summary",
    "professional profile":         "summary",
    "objective":                    "summary",
    "career objective":             "summary",
    "about me":                     "summary",
    "about":                        "summary",
    "overview":                     "summary",
    "personal statement":           "summary",
    "career statement":             "summary",

    # Experience
    "experience":                   "experience",
    "work experience":              "experience",
    "professional experience":      "experience",
    "employment history":           "experience",
    "employment":                   "experience",
    "work history":                 "experience",
    "career history":               "experience",
    "relevant experience":          "experience",
    "internship":                   "experience",
    "internships":                  "experience",
    "industrial training":          "experience",
    "professional background":      "experience",   # FIX C additions
    "career background":            "experience",
    "my journey":                   "experience",   # creative variant
    "my experience":                "experience",
    "work background":              "experience",
    "job history":                  "experience",
    "positions held":               "experience",
    "previous experience":          "experience",

    # Education
    "education":                    "education",
    "educational background":       "education",
    "academic background":          "education",
    "academic history":             "education",
    "qualifications":               "education",
    "academic qualifications":      "education",
    "degrees":                      "education",
    "training":                     "education",
    "training and education":       "education",
    "education and training":       "education",   # FIX: reversed variant
    "education & training":         "education",   # FIX: ampersand variant
    "education &amp; training":     "education",   # FIX: HTML entity variant
    "my story":                     "education",   # creative variant
    "educational qualifications":   "education",
    "academic record":              "education",
    "academic credentials":         "education",
    "formal education":             "education",
    "studies":                      "education",

    # Skills
    "skills":                       "skills",
    "technical skills":             "skills",
    "core skills":                  "skills",
    "key skills":                   "skills",
    "professional skills":          "skills",
    "competencies":                 "skills",
    "core competencies":            "skills",
    "expertise":                    "skills",
    "areas of expertise":           "skills",
    "technologies":                 "skills",
    "tools":                        "skills",
    "tools and technologies":       "skills",
    "programming languages":        "skills",
    "software":                     "skills",
    "technical expertise":          "skills",   # FIX C additions
    "my superpowers":               "skills",   # creative variant
    "my skills":                    "skills",
    "skill set":                    "skills",
    "capabilities":                 "skills",
    "technical capabilities":       "skills",
    "what i know":                  "skills",
    "proficiencies":                "skills",

    # Projects
    "projects":                     "projects",
    "personal projects":            "projects",
    "academic projects":            "projects",
    "relevant projects":            "projects",
    "key projects":                 "projects",
    "project experience":           "projects",
    "portfolio":                    "projects",
    "selected projects":            "projects",
    "notable projects":             "projects",

    # Certifications
    "certifications":               "certifications",
    "certification":                "certifications",
    "certificates":                 "certifications",
    "professional certifications":  "certifications",
    "licenses":                     "certifications",
    "licenses and certifications":  "certifications",
    "accreditations":               "certifications",
    "courses":                      "certifications",
    "professional development":     "certifications",

    # Achievements
    "achievements":                 "achievements",
    "accomplishments":              "achievements",
    "awards":                       "achievements",
    "honors":                       "achievements",
    "honours":                      "achievements",
    "awards and achievements":      "achievements",
    "recognition":                  "achievements",
    "my wins":                      "achievements",   # creative variant
    "milestones":                   "achievements",
    "highlights":                   "achievements",

    # Languages
    "languages":                    "languages",
    "language skills":              "languages",
    "spoken languages":             "languages",
    "language proficiency":         "languages",

    # Interests
    "interests":                    "interests",
    "hobbies":                      "interests",
    "hobbies and interests":        "interests",
    "activities":                   "interests",
    "extracurricular":              "interests",
    "extracurricular activities":   "interests",
    "things i love":                "interests",   # creative variant
    "passions":                     "interests",

    # References
    "references":                   "references",
    "referees":                     "references",
    "professional references":      "references",
}

SECTION_ORDER = [
    "contact", "summary", "experience", "education", "skills",
    "projects", "certifications", "achievements", "languages",
    "interests", "references",
]

SECTION_WEIGHTS = {
    "summary":        1.0,
    "skills":         0.9,
    "experience":     0.7,
    "education":      0.5,
    "certifications": 0.6,
    "projects":       0.4,
    "achievements":   0.4,
    "contact":        0.3,
    "languages":      0.2,
    "interests":      0.1,
    "other":          0.2,
}

# Fuzzy matching threshold for section header detection.
# 0.72 accepts clear synonyms ("professional background" → "experience")
# while rejecting body-text lines containing section-like words.
FUZZY_HEADER_THRESHOLD = 0.72

# Canonical section name → representative phrases for fuzzy comparison
# These are used in Tier 2 matching to compare unknown headers against
_CANONICAL_PHRASES = {
    "contact":        ["contact information", "personal details", "contact details"],
    "summary":        ["professional summary", "career objective", "personal statement"],
    "experience":     ["work experience", "professional experience", "employment history",
                       "career history", "professional background"],
    "education":      ["education", "academic background", "academic qualifications"],
    "skills":         ["technical skills", "core skills", "key competencies",
                       "areas of expertise", "technical expertise"],
    "projects":       ["projects", "project experience", "portfolio"],
    "certifications": ["certifications", "professional certifications", "licenses"],
    "achievements":   ["achievements", "accomplishments", "awards and recognition"],
    "languages":      ["languages", "language skills", "language proficiency"],
    "interests":      ["hobbies and interests", "extracurricular activities"],
    "references":     ["references", "professional references"],
}


# ── Public API ────────────────────────────────────────────────────────────────

def detect_sections(text: str) -> tuple:
    """
    Detect and extract resume sections from cleaned text.

    Args:
        text: cleaned resume text from extraction_service.py

    Returns:
        (sections_dict, None) or (None, error_string)
    """
    if not text or not text.strip():
        return None, "No text provided for section detection."

    lines = text.split("\n")
    if len(lines) < 3:
        return None, "Text is too short to detect resume sections."

    headers  = _find_headers(lines)

    if not headers:
        return {"other": text.strip()}, None

    sections = _slice_sections(lines, headers)
    sections = _clean_sections(sections)
    sections = {k: v for k, v in sections.items() if v and len(v) > 5}

    if not sections:
        return None, "Could not extract any section content from the CV."

    # ── FIX: Auto-detect contact info from first 5 lines ─────────────
    # Most professional CVs put name + contact on the first 2-3 lines
    # WITHOUT a "CONTACT" section header. The section detector never
    # finds a header so it reports contact as missing even though the
    # email/phone/name are clearly present at the top of the document.
    # This fix checks the first 5 lines for contact signals and injects
    # a contact section if found but not already detected.
    if "contact" not in sections:
        first_lines = "\n".join(lines[:6]).strip()
        has_email   = bool(re.search(
            r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
            first_lines
        ))
        has_phone   = bool(re.search(
            r'\+?\d[\d\s\-\(\)]{7,15}\d',
            first_lines
        ))
        has_linkedin = "linkedin" in first_lines.lower()
        # Inject contact section if at least 2 contact signals found
        if sum([has_email, has_phone, has_linkedin]) >= 2:
            sections["contact"] = first_lines

    return sections, None


def get_missing_sections(sections: dict) -> list:
    """Return required sections absent from detected sections."""
    required = {"contact", "summary", "experience", "education", "skills"}
    missing  = required - set(sections.keys())
    return [s for s in SECTION_ORDER if s in missing]


def extract_keywords(text: str, top_n: int = 30) -> tuple:
    """
    Extract keywords from text using KeyBERT semantic similarity.

    Args:
        text:  full resume text
        top_n: max keywords to return

    Returns:
        (keywords_list, None) or (None, error_string)
    """
    if not text or not text.strip():
        return None, "No text provided for keyword extraction."
    if len(text) < 50:
        return None, "Text is too short for keyword extraction."

    try:
        model       = _get_kw_model()
        raw_keywords = model.extract_keywords(
            text,
            keyphrase_ngram_range=(1, 2),
            stop_words="english",
            top_n=top_n,
            diversity=0.5,
            use_mmr=True,
        )
        keywords = [kw for kw, score in raw_keywords]
        if not keywords:
            return None, "No keywords could be extracted."
        return keywords, None
    except Exception as e:
        return None, f"Keyword extraction failed: {str(e)}"


def extract_keywords_per_section(sections: dict,
                                  top_n_per_section: int = 15) -> tuple:
    """
    Extract keywords per section with contextual weights.

    Returns:
        (keyword_placement_dict, None) or (None, error_string)
    """
    if not sections:
        return None, "No sections provided."

    result = {}
    for section_name, content in sections.items():
        if not content or len(content.strip()) < 20:
            continue
        keywords, error = extract_keywords(content, top_n=top_n_per_section)
        if keywords:
            result[section_name] = {
                "keywords": keywords,
                "weight":   SECTION_WEIGHTS.get(section_name, 0.2),
            }

    if not result:
        return None, "Could not extract keywords from any section."

    return result, None


# ── Private helpers ───────────────────────────────────────────────────────────

def _fuzzy_ratio(a: str, b: str) -> float:
    """
    Return difflib SequenceMatcher similarity ratio between two strings.
    Range: 0.0 (no similarity) to 1.0 (identical).

    Uses quick_ratio() first as a fast pre-filter — it returns an upper
    bound. Only compute the full ratio if quick_ratio passes the threshold.
    This avoids the O(n²) cost on lines that clearly won't match.
    """
    m = SequenceMatcher(None, a, b)
    if m.quick_ratio() < FUZZY_HEADER_THRESHOLD:
        return 0.0
    return m.ratio()


def _fuzzy_match_header(normalized: str) -> str | None:
    """
    FIX C — Tier 2 fuzzy matching for section headers.

    Compares a normalized header line against representative phrases
    for each canonical section name. Returns the canonical name of the
    best match if similarity ≥ FUZZY_HEADER_THRESHOLD, else None.

    Args:
        normalized: lowercased, punctuation-stripped header candidate

    Returns:
        canonical section name string or None
    """
    best_section = None
    best_ratio   = FUZZY_HEADER_THRESHOLD  # Must beat this to count

    for canonical_name, phrases in _CANONICAL_PHRASES.items():
        for phrase in phrases:
            ratio = _fuzzy_ratio(normalized, phrase)
            if ratio > best_ratio:
                best_ratio   = ratio
                best_section = canonical_name

    return best_section


def _is_header_line(line: str) -> str | None:
    """
    Check if a line is a section header and return its canonical name.

    FIX C — Two-tier matching:
        Tier 1: exact lookup in SECTION_KEYWORDS (fast, O(1))
        Tier 2: fuzzy SequenceMatcher ratio ≥ 0.72 (catches variants)

    Only lines ≤ 60 chars are considered as headers to avoid
    matching body-text sentences.

    Args:
        line: a single line from the resume text

    Returns:
        canonical section name string or None
    """
    stripped = line.strip()
    if not stripped or len(stripped) > 60:
        return None

    # Normalize: lowercase + remove common punctuation
    normalized = re.sub(r"[:\-_•|/\\]", "", stripped).strip().lower()

    if not normalized:
        return None

    # Tier 1 — exact lookup (handles 95%+ of real CVs)
    if normalized in SECTION_KEYWORDS:
        return SECTION_KEYWORDS[normalized]

    # Tier 2 — fuzzy matching for creative/unusual headers
    # Only attempt if line looks like a heading:
    #   - ALL CAPS, or Title Case, or short enough (≤ 5 words)
    word_count = len(normalized.split())
    looks_like_heading = (
        stripped == stripped.upper()       # ALL CAPS
        or stripped == stripped.title()    # Title Case
        or word_count <= 5                 # Short phrase
    )

    if looks_like_heading:
        fuzzy_result = _fuzzy_match_header(normalized)
        if fuzzy_result:
            return fuzzy_result

    return None


def _find_headers(lines: list) -> list:
    """
    Scan all lines and return (line_index, canonical_section_name)
    for every detected header. Deduplicates by canonical name.
    """
    headers      = []
    seen_sections = set()

    for i, line in enumerate(lines):
        section_name = _is_header_line(line)
        if section_name and section_name not in seen_sections:
            headers.append((i, section_name))
            seen_sections.add(section_name)

    return headers


def _slice_sections(lines: list, headers: list) -> dict:
    """Slice lines between header positions to extract section content."""
    sections = {}
    for i, (header_idx, section_name) in enumerate(headers):
        content_start = header_idx + 1
        content_end   = headers[i + 1][0] if i + 1 < len(headers) else len(lines)
        content       = "\n".join(lines[content_start:content_end])
        sections[section_name] = content
    return sections


def _clean_sections(sections: dict) -> dict:
    """Clean raw content of each detected section."""
    cleaned = {}
    for section_name, content in sections.items():
        content = re.sub(r"\n{3,}", "\n\n", content).strip()
        cleaned[section_name] = content
    return cleaned