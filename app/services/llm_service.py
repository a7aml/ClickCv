"""
services/llm_service.py

Two public functions:

1. generate_recommendations()
   Section-by-section CV improvement recommendations.
   Called by analysis_routes.py after ATS scoring.

2. generate_rebuilt_cv()
   Full CV rebuild using original resume data + analysis gaps.
   Called by rebuild_routes.py for the rebuild feature.
   NEVER fabricates data — only restructures and enhances
   what the user already provided.

Both follow the same (result, error) tuple pattern.

──────────────────────────────────────────────────────────────────────────────
SPEED OPTIMISATIONS (recommendations path only):

  #3 — GPT no longer echoes score_band, used_jd, missing_sections,
       missing_keywords — merged from scoring_result in Python.
  #4 — Recommendations max_tokens lowered 1500 → 900.
  #5 — Prompt instructs GPT to return compact JSON.

REBUILD FIXES:
  #FIX1 — JSON schema built dynamically from detected sections so GPT
           always sees all sections it must return (including languages).
  #FIX2 — Explicit "YOU MUST RETURN ALL OF THESE" instruction.
  #FIX3 — Parser min-length lowered 20 → 10 chars.
  #FIX4 — Experience format instruction: each job separated by blank line.
  #FIX5 — Keyword injection instruction: less conservative, names specific
           JD keywords to insert where genuinely applicable.

COMPARE IMPROVEMENTS (generate_comparison only):
  #CMP1 — Accepts kw_map_a, kw_map_b, jd_keyphrases from compare_routes.
  #CMP2 — Full JD passed to prompt (1500 chars instead of 600).
  #CMP3 — Prompt shows exact JD phrases each CV matched/missed.
  #CMP4 — LLM instructed to ground verdict in specific JD terms, not scores.
  #CMP5 — max_tokens raised from 2000 → 2500 for richer comparison output.
──────────────────────────────────────────────────────────────────────────────
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


# ── OpenAI client ─────────────────────────────────────────────────────────────

def _get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        try:
            from flask import current_app
            api_key = current_app.config.get("OPENAI_API_KEY")
        except RuntimeError:
            pass
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY not found. "
            "Add it to your .env file: OPENAI_API_KEY=sk-..."
        )
    return OpenAI(api_key=api_key)


MODEL          = "gpt-4o-mini"
MAX_TOKENS     = 1500
REC_MAX_TOKENS = 900

ALL_SECTION_KEYS = [
    "contact", "summary", "experience", "education",
    "skills", "projects", "certifications", "achievements",
    "languages", "interests",
]

BAND_INSTRUCTIONS = {
    "strong": (
        "The resume is already strong. Focus on polishing language, "
        "making achievements more quantifiable, and tightening the summary. "
        "Give 2-3 small but high-impact improvements per section."
    ),
    "good": (
        "The resume is good but needs targeted fixes. Focus on adding "
        "missing keywords naturally, strengthening weak sections, and "
        "improving how achievements are presented. Be specific."
    ),
    "borderline": (
        "The resume needs significant improvement. Provide detailed rewrites "
        "for each weak section. Show exactly what to change and why. "
        "Focus on keyword gaps and missing sections first."
    ),
    "weak": (
        "The resume needs a complete overhaul. Guide the user through "
        "rebuilding each section from scratch. Be direct about what is "
        "missing and provide clear examples of what good content looks like."
    ),
}


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 1 — generate_recommendations  (UNCHANGED)
# ══════════════════════════════════════════════════════════════════════════════

def generate_recommendations(
    sections:        dict,
    scoring_result:  dict,
    major:           str,
    job_description: str = None,
) -> tuple:
    if not scoring_result:
        return None, "No scoring result provided for recommendations."
    if not sections:
        return None, "No sections provided for recommendations."

    prompt = _build_prompt(sections, scoring_result, major, job_description)
    raw_response, error = _call_openai(prompt, max_tokens=REC_MAX_TOKENS)
    if error:
        return None, error

    result, error = _parse_response(raw_response, scoring_result)
    if error:
        return None, error

    return result, None


def _build_prompt(
    sections:        dict,
    scoring_result:  dict,
    major:           str,
    job_description: str = None,
) -> str:
    score       = scoring_result.get("overall_score", 0)
    band        = scoring_result.get("score_band", "weak")
    missing_sec = scoring_result.get("missing_sections", [])
    missing_kw  = scoring_result.get("missing_keywords", [])[:15]
    band_instr  = BAND_INSTRUCTIONS.get(band, BAND_INSTRUCTIONS["weak"])

    criteria_lines = []
    criteria_map = {
        "keyword_score":            "Keyword Matching (35%)",
        "keyword_placement_score":  "Keyword Placement (18%)",
        "formatting_score":         "Formatting Parsability (17%)",
        "structure_score":          "Section Completeness (12%)",
        "experience_recency_score": "Experience Recency (10%)",
        "achievements_score":       "Quantifiable Achievements (10%)",
        "job_title_score":          "Job Title Matching (8%)",
        "education_score":          "Education & Certifications (7%)",
        "resume_length_score":      "Resume Length (4%)",
        "contact_info_score":       "Contact Information (3%)",
    }
    for key, label in criteria_map.items():
        val = scoring_result.get(key, 0)
        criteria_lines.append(f"  {label}: {val}/100")

    section_lines = []
    for name, content in sections.items():
        preview = content[:300].replace("\n", " ").strip()
        section_lines.append(f"  [{name.upper()}]\n  {preview}")

    jd_block = ""
    if job_description and job_description.strip():
        jd_preview = job_description[:400].strip()
        jd_block = f"\nJOB DESCRIPTION (user is targeting this role):\n{jd_preview}\n"

    return f"""You are an expert ATS resume analyst and career coach.
Analyse this resume and provide specific, actionable improvement recommendations.

INDUSTRY: {major.upper()}
OVERALL ATS SCORE: {score}/100 (Band: {band.upper()})

INSTRUCTION: {band_instr}

ATS CRITERION SCORES:
{chr(10).join(criteria_lines)}

MISSING SECTIONS: {', '.join(missing_sec) if missing_sec else 'None'}
MISSING KEYWORDS: {', '.join(missing_kw) if missing_kw else 'None'}
{jd_block}
RESUME SECTIONS CONTENT:
{chr(10).join(section_lines)}

Respond ONLY with a valid JSON object. No markdown, no backticks, no explanation outside the JSON.
Output COMPACT JSON — no spaces or newlines between keys and values. Minified.

JSON structure:
{{
  "summary_message": "2-3 sentence overall assessment of the resume",
  "sections": [
    {{
      "section": "section_name",
      "current_score": <criterion score 0-100>,
      "priority": <1=critical, 2=important, 3=minor>,
      "issue": "One sentence describing the specific problem",
      "recommendation": "Specific actionable advice in 2-3 sentences",
      "rewrite_example": "A concrete example of improved content (1-3 lines)"
    }}
  ],
  "top_keywords_to_add": ["keyword1", "keyword2", "keyword3"],
  "quick_wins": ["One line tip 1", "One line tip 2", "One line tip 3"]
}}

Rules:
- Include only sections that need improvement (score < 80 or missing)
- Order sections by priority (1 first)
- Keep rewrite_example realistic and specific to the resume content
- top_keywords_to_add should be from the missing keywords list
- quick_wins should be 3 immediate actions the user can take today
- Do not hallucinate content not present in the resume
"""


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 2 — generate_rebuilt_cv  (UNCHANGED)
# ══════════════════════════════════════════════════════════════════════════════

def generate_rebuilt_cv(
    raw_text:        str,
    sections:        dict,
    scoring_result:  dict,
    major:           str,
    job_description: str = None,
) -> tuple:
    """
    Rebuild the user's CV to maximise ATS score.
    Uses ONLY information present in the original resume.
    Never fabricates jobs, qualifications, or skills.
    """
    if not raw_text:
        return None, "Original resume text is required for rebuild."
    if not scoring_result:
        return None, "Scoring result is required for rebuild."

    prompt = _build_rebuild_prompt(
        raw_text, sections, scoring_result, major, job_description
    )

    raw_response, error = _call_openai(prompt, max_tokens=2500)
    if error:
        return None, error

    result, error = _parse_rebuild_response(raw_response)
    if error:
        return None, error

    return result, None


def _build_rebuild_prompt(
    raw_text:        str,
    sections:        dict,
    scoring_result:  dict,
    major:           str,
    job_description: str = None,
) -> str:
    score       = scoring_result.get("overall_score", 0)
    band        = scoring_result.get("score_band", "weak")
    missing_sec = scoring_result.get("missing_sections", [])
    missing_kw  = scoring_result.get("missing_keywords", [])[:20]

    criteria_lines = []
    criteria_map = {
        "keyword_score":            "Keyword Matching (35%)",
        "keyword_placement_score":  "Keyword Placement (18%)",
        "formatting_score":         "Formatting (17%)",
        "structure_score":          "Section Completeness (12%)",
        "experience_recency_score": "Experience Recency (10%)",
        "achievements_score":       "Achievements (10%)",
        "job_title_score":          "Job Title Match (8%)",
        "education_score":          "Education (7%)",
        "resume_length_score":      "Length (4%)",
        "contact_info_score":       "Contact Info (3%)",
    }
    for key, label in criteria_map.items():
        val = scoring_result.get(key, 0)
        criteria_lines.append(f"  {label}: {val}/100")

    existing_sections = list(sections.keys())
    existing_list_str = ", ".join(existing_sections)

    # Build schema dynamically — only sections that exist in this CV (#FIX1)
    schema_lines = []
    for key in ALL_SECTION_KEYS:
        if key not in existing_sections:
            continue
        if key == "contact":
            schema_lines.append(
                f'  "{key}": "Full name\\nPhone | Email | Location | LinkedIn"'
            )
        elif key == "summary":
            schema_lines.append(
                f'  "{key}": "Full rewritten professional summary (3-4 lines)"'
            )
        elif key == "experience":
            schema_lines.append(
                f'  "{key}": "Job Title\\nCompany | Start - End | Location\\n• Bullet 1\\n• Bullet 2\\n\\nJob Title 2\\nCompany | Start - End | Location\\n• Bullet 1"'
            )
        elif key == "education":
            schema_lines.append(
                f'  "{key}": "Degree, institution, graduation date, GPA if present"'
            )
        elif key == "skills":
            schema_lines.append(
                f'  "{key}": "Category: skill1, skill2\\nCategory2: skill3, skill4"'
            )
        elif key == "languages":
            schema_lines.append(
                f'  "{key}": "Language: Proficiency\\nLanguage2: Proficiency"'
            )
        else:
            schema_lines.append(
                f'  "{key}": "Full rewritten {key} section"'
            )
    schema_example = "{\n" + ",\n".join(schema_lines) + "\n}"

    jd_block = ""
    jd_keywords_instruction = ""
    if job_description and job_description.strip():
        jd_preview = job_description[:500].strip()
        jd_block = f"""
TARGET JOB DESCRIPTION:
{jd_preview}

Optimise the rebuilt CV specifically for this role.
"""
        if missing_kw:
            jd_keywords_instruction = f"""
KEYWORD INJECTION — insert these naturally into bullets where the candidate's work genuinely involved them:
  Missing keywords: {', '.join(missing_kw)}
  Examples of natural insertion:
  - If they deployed with Docker → add "containerized using Docker"
  - If they wrote tests → mention "unit tests" or "pytest"
  - If they used APIs → mention "REST API contracts" or "API documentation"
  Do NOT fabricate. Only insert where the original content implies the skill.
"""
        else:
            jd_keywords_instruction = """
Insert relevant keywords from the job description naturally into bullets
where the candidate's original content genuinely supports them.
"""

    raw_preview = raw_text[:3000].strip()

    section_lines = []
    for name, content in sections.items():
        preview = content[:400].replace("\n", " ").strip()
        section_lines.append(f"[{name.upper()}]\n{preview}")

    return f"""You are an expert ATS resume writer and career coach.
Your task is to REBUILD this resume to maximise its ATS score for the {major.upper()} industry.

CRITICAL RULES — YOU MUST FOLLOW ALL OF THESE:
1. NEVER invent, fabricate, or add ANY information not present in the original resume.
2. NEVER add jobs, skills, qualifications, or certifications the user did not mention.
3. You may REPHRASE, RESTRUCTURE, and REORDER existing content.
4. You may INSERT missing keywords ONLY if they naturally fit existing content.
5. Every rebuilt section must be based strictly on the original resume content below.
6. You MUST return ALL of the following sections — they ALL exist in the original CV:
   {existing_list_str}
   Omitting any of these sections is a failure.

ORIGINAL RESUME SCORE: {score}/100 (Band: {band.upper()})
INDUSTRY: {major.upper()}

CURRENT ATS CRITERION SCORES (what to improve):
{chr(10).join(criteria_lines)}

MISSING SECTIONS (create only if content exists in original):
{', '.join(missing_sec) if missing_sec else 'None'}
{jd_block}{jd_keywords_instruction}
ORIGINAL RESUME TEXT:
{raw_preview}

SECTION BREAKDOWN (rewrite each of these):
{chr(10).join(section_lines)}

REBUILD INSTRUCTIONS:

- contact:
  Format as: Full Name\\nPhone | Email | Location | LinkedIn/Website

- summary:
  Write 3-4 powerful lines. Put the top 3-4 ATS keywords in the FIRST 2 lines.
  Use the candidate's real background — no invented roles or skills.

- experience: (#FIX4 — critical formatting rule)
  Each job MUST follow this exact format:
    Job Title
    Company | Start Date - End Date | Location
    • Bullet point 1
    • Bullet point 2
    • Bullet point 3

  Separate each job with a BLANK LINE between them.
  NEVER merge two jobs into one block.
  NEVER make a job title a bullet point.
  Rewrite bullets with strong action verbs. Where the candidate's original
  work implies it, naturally add relevant keywords from the missing list.
  If they built APIs → mention "RESTful API" and "API contracts".
  If they worked with databases → mention "optimized PostgreSQL queries".
  If they used Docker in projects → you may mention "containerized" in
  experience only if the original text supports it.

- education:
  Format: Degree, Institution, Graduated: Month Year, CGPA: X.XX / 4.0

- skills:
  Format: Category: skill1, skill2, skill3 (one category per line).
  Add missing keywords that genuinely match the candidate's demonstrated skills.

- projects:
  Each project on its own block. Title - Tech Stack on first line, description below.
  Separate projects with a blank line.
  Strengthen descriptions with action verbs and outcomes.

- languages:
  One per line. Format: Language: Proficiency

- certifications, achievements, interests:
  Preserve real content, improve presentation only.

Respond ONLY with a valid JSON object. No markdown, no backticks, no extra text.
Return EXACTLY the following JSON — every key in rule 6 must be present:

{schema_example}

CRITICAL JSON RULES:
- Use \\n for newlines within string values.
- Separate each job in "experience" with \\n\\n (blank line) between them.
- Every key shown above MUST appear. Do not omit any.
- Never fabricate content not in the original resume.
"""


def _parse_rebuild_response(raw_text: str) -> tuple:
    if not raw_text:
        return None, "Empty response received from OpenAI during rebuild."

    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines   = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1]).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        return None, (
            f"Failed to parse rebuild response as JSON: {str(e)}. "
            "Please try again."
        )

    if not isinstance(parsed, dict):
        return None, "Rebuild response is not a JSON object."

    allowed_keys = set(ALL_SECTION_KEYS) | {"references"}

    result = {}
    for key, value in parsed.items():
        key_clean = key.strip().lower()
        if key_clean not in allowed_keys:
            continue
        if not isinstance(value, str) or not value.strip():
            continue
        if len(value.strip()) < 10:
            continue
        result[key_clean] = value.strip()

    if not result:
        return None, (
            "Rebuild produced no valid sections. "
            "The model response was empty or malformed. Please try again."
        )

    if "summary" not in result and "experience" not in result:
        return None, (
            "Rebuild is missing both summary and experience sections. "
            "Please try again."
        )

    return result, None


# ══════════════════════════════════════════════════════════════════════════════
# SHARED HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _call_openai(prompt: str, max_tokens: int = None) -> tuple:
    tokens = max_tokens or MAX_TOKENS
    try:
        client   = _get_openai_client()
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=tokens,
            temperature=0.3,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert ATS resume analyst and writer. "
                        "You always respond with valid JSON only. "
                        "Never include markdown, backticks, or text outside the JSON."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        raw_text = response.choices[0].message.content.strip()
        return raw_text, None

    except Exception as e:
        error_msg = str(e)
        if "authentication" in error_msg.lower() or "api key" in error_msg.lower():
            return None, (
                "OpenAI API key is invalid or missing. "
                "Check your OPENAI_API_KEY in the .env file."
            )
        if "rate limit" in error_msg.lower():
            return None, "OpenAI rate limit reached. Please wait and try again."
        if "insufficient_quota" in error_msg.lower():
            return None, "OpenAI account has insufficient credits."
        return None, f"OpenAI API call failed: {error_msg}"


def _parse_response(raw_text: str, scoring_result: dict) -> tuple:
    if not raw_text:
        return None, "Empty response received from OpenAI."

    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines   = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1]).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        return None, (
            f"Failed to parse OpenAI response as JSON: {str(e)}. "
            "Please try again."
        )

    for key in ["summary_message", "sections"]:
        if key not in parsed:
            return None, f"OpenAI response missing required key '{key}'."

    result = {
        "overall_score":       scoring_result.get("overall_score"),
        "score_band":          scoring_result.get("score_band"),
        "used_jd":             scoring_result.get("used_jd"),
        "missing_sections":    scoring_result.get("missing_sections", []),
        "missing_keywords":    scoring_result.get("missing_keywords", []),
        "summary_message":     parsed.get("summary_message", ""),
        "sections":            parsed.get("sections", []),
        "top_keywords_to_add": parsed.get("top_keywords_to_add", []),
        "quick_wins":          parsed.get("quick_wins", []),
    }
    return result, None


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 3 — generate_comparison
#
# COMPARE IMPROVEMENTS (#CMP1 — #CMP5):
#   - Accepts kw_map_a, kw_map_b, jd_keyphrases from compare_routes
#   - Passes full JD (1500 chars) to the LLM prompt
#   - Shows exact matched/missing JD phrases per CV in the prompt
#   - Instructs LLM to ground verdict in specific JD terms
#   - Raised max_tokens to 2500 for richer output
# ══════════════════════════════════════════════════════════════════════════════

def generate_comparison(
    sections_a:      dict,
    scoring_a:       dict,
    sections_b:      dict,
    scoring_b:       dict,
    job_description: str,
    kw_map_a:        dict = None,
    kw_map_b:        dict = None,
    jd_keyphrases:   list = None,
) -> tuple:
    """
    Generate a JD-grounded comparison between two CVs.

    Args:
        sections_a:      detected sections for CV A
        scoring_a:       ATS scoring result for CV A
        sections_b:      detected sections for CV B
        scoring_b:       ATS scoring result for CV B
        job_description: full JD text
        kw_map_a:        JD keyword hit/miss map for CV A (from compare_routes)
        kw_map_b:        JD keyword hit/miss map for CV B (from compare_routes)
        jd_keyphrases:   list of extracted JD key phrases (from compare_routes)

    Returns:
        (result_dict, None) or (None, error_string)
    """
    if not job_description or not job_description.strip():
        return None, "Job description is required for comparison."
    if not scoring_a or not scoring_b:
        return None, "Scoring results are required for both CVs."

    # Default empty maps if caller did not provide them
    kw_map_a      = kw_map_a      or {"matched": [], "missing": [], "match_pct": 0}
    kw_map_b      = kw_map_b      or {"matched": [], "missing": [], "match_pct": 0}
    jd_keyphrases = jd_keyphrases or []

    prompt = _build_comparison_prompt(
        sections_a, scoring_a, sections_b, scoring_b,
        job_description, kw_map_a, kw_map_b, jd_keyphrases,
    )

    # #CMP5 — raised max_tokens to 2500 for richer comparison verdict
    raw_response, error = _call_openai(prompt, max_tokens=2500)
    if error:
        return None, error

    result, error = _parse_comparison_response(raw_response, scoring_a, scoring_b)
    if error:
        return None, error

    return result, None


def _build_comparison_prompt(
    sections_a:      dict,
    scoring_a:       dict,
    sections_b:      dict,
    scoring_b:       dict,
    job_description: str,
    kw_map_a:        dict,
    kw_map_b:        dict,
    jd_keyphrases:   list,
) -> str:
    """
    Build a JD-grounded comparison prompt.

    COMPARE IMPROVEMENTS:
    #CMP2 — Full JD shown to LLM (1500 chars, was 600)
    #CMP3 — Explicit JD phrase hit/miss tables for each CV
    #CMP4 — LLM instructed to reference specific JD terms in verdict,
             not just aggregate scores
    """

    def _criteria_block(scoring: dict, label: str) -> str:
        criteria_map = {
            "keyword_score":            "Keyword Matching (35%)",
            "keyword_placement_score":  "Keyword Placement (18%)",
            "formatting_score":         "Formatting (17%)",
            "structure_score":          "Section Completeness (12%)",
            "experience_recency_score": "Experience Recency (10%)",
            "achievements_score":       "Achievements (10%)",
            "job_title_score":          "Job Title Match (8%)",
            "education_score":          "Education (7%)",
            "resume_length_score":      "Resume Length (4%)",
            "contact_info_score":       "Contact Info (3%)",
        }
        lines = [f"  {label} — Overall: {scoring.get('overall_score', 0)}/100"]
        for key, name in criteria_map.items():
            lines.append(f"    {name}: {scoring.get(key, 0)}/100")
        return "\n".join(lines)

    def _sections_preview(sections: dict, label: str) -> str:
        lines = [f"  {label} detected sections:"]
        for name, content in sections.items():
            preview = content[:250].replace("\n", " ").strip()
            lines.append(f"    [{name.upper()}]: {preview}")
        return "\n".join(lines)

    def _kw_table(kw_map: dict, label: str) -> str:
        """Format keyword hit/miss as a readable table for the LLM."""
        matched = kw_map.get("matched", [])
        missing = kw_map.get("missing", [])
        pct     = kw_map.get("match_pct", 0)
        lines   = [
            f"  {label} — JD Keyword Coverage: {pct}% "
            f"({len(matched)} matched, {len(missing)} missing)"
        ]
        if matched:
            lines.append(f"    ✓ Matched JD terms: {', '.join(matched[:20])}")
        if missing:
            lines.append(f"    ✗ Missing JD terms: {', '.join(missing[:20])}")
        return "\n".join(lines)

    score_a = scoring_a.get("overall_score", 0)
    score_b = scoring_b.get("overall_score", 0)

    # #CMP2 — Full JD up to 1500 chars (was 600)
    jd_full = job_description[:1500].strip()

    # Top JD phrases summary for the LLM context
    jd_phrases_summary = (
        ", ".join(jd_keyphrases[:30]) if jd_keyphrases
        else "see JD text above"
    )

    return f"""You are an expert ATS analyst and recruitment consultant.
You have scored two CVs against the same job description using a 10-criteria ATS algorithm.
Your task is to compare them and explain which candidate is the stronger fit FOR THIS SPECIFIC JOB.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
JOB DESCRIPTION (full text — read carefully):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{jd_full}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KEY JD REQUIREMENTS EXTRACTED:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{jd_phrases_summary}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
JD KEYWORD COVERAGE — WHAT EACH CV COVERS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{_kw_table(kw_map_a, "CV A")}

{_kw_table(kw_map_b, "CV B")}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ATS ALGORITHM SCORES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{_criteria_block(scoring_a, "CV A")}

{_criteria_block(scoring_b, "CV B")}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CV CONTENT SUMMARIES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{_sections_preview(sections_a, "CV A")}

{_sections_preview(sections_b, "CV B")}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MISSING SECTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CV A missing sections: {', '.join(scoring_a.get('missing_sections') or []) or 'None'}
  CV B missing sections: {', '.join(scoring_b.get('missing_sections') or []) or 'None'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR TASK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Write a detailed, JOB-SPECIFIC comparison. Your verdict must answer:
  1. Which candidate better matches THIS job's specific requirements?
  2. Which specific JD terms does CV A have that CV B lacks (or vice versa)?
  3. How do the CVs differ in covering the key skills this job needs?
  4. What concrete changes would make the losing CV competitive for THIS role?

CRITICAL RULES:
1. Winner MUST match the higher overall score ({score_a} for CV A, {score_b} for CV B).
   If scores are equal, pick the one with higher JD keyword coverage percentage.
2. Every strength and weakness MUST reference specific JD requirements or keywords.
   BAD example: "CV A has better keyword placement"
   GOOD example: "CV A explicitly mentions REST API and CI/CD which this role requires;
                  CV B does not mention either despite them being core JD requirements"
3. The verdict must reference the actual job title/role from the JD.
4. Do not give generic resume advice — focus only on fit for THIS specific job.
5. Do not fabricate content not present in the CV summaries or keyword maps.

Respond ONLY with valid JSON. No markdown, no backticks, no text outside the JSON.

JSON structure:
{{
  "winner": "a" or "b",
  "summary": "One sentence: which CV wins for THIS specific role, scores, and the single most JD-relevant reason",
  "verdict": "4 to 6 paragraphs. Paragraph 1: overall winner and why for this role. Paragraph 2: specific JD requirements CV A meets vs misses. Paragraph 3: specific JD requirements CV B meets vs misses. Paragraph 4: head-to-head on the most critical JD skills. Paragraph 5: what the losing CV must add/change to compete for this role. Each paragraph must reference specific keywords or requirements from the JD above.",
  "strengths_a": ["JD-specific strength 1 (name the JD requirement)", "strength 2", "strength 3"],
  "weaknesses_a": ["JD-specific gap 1 (name the missing JD requirement)", "gap 2"],
  "strengths_b": ["JD-specific strength 1 (name the JD requirement)", "strength 2", "strength 3"],
  "weaknesses_b": ["JD-specific gap 1 (name the missing JD requirement)", "gap 2"]
}}

Rules:
- winner must be exactly "a" or "b" (lowercase)
- summary must be one sentence only
- verdict must be plain text paragraphs separated by \\n\\n — no bullet points inside verdict
- each strengths/weaknesses list must have 2 to 4 items
- every item must name a specific JD requirement, keyword, or skill — never generic advice
"""


def _parse_comparison_response(
    raw_text:  str,
    scoring_a: dict,
    scoring_b: dict,
) -> tuple:
    if not raw_text:
        return None, "Empty response received from OpenAI."

    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines   = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1]).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        return None, f"Failed to parse comparison response as JSON: {str(e)}."

    if not isinstance(parsed, dict):
        return None, "Comparison response is not a JSON object."

    required = ["winner", "summary", "verdict", "strengths_a",
                "weaknesses_a", "strengths_b", "weaknesses_b"]
    for key in required:
        if key not in parsed:
            return None, f"Comparison response missing required key '{key}'."

    score_a       = scoring_a.get("overall_score", 0)
    score_b       = scoring_b.get("overall_score", 0)
    actual_winner = "a" if score_a >= score_b else "b"

    if parsed.get("winner") not in ("a", "b"):
        parsed["winner"] = actual_winner
    elif parsed["winner"] != actual_winner and abs(score_a - score_b) > 2:
        parsed["winner"] = actual_winner

    return {
        "winner":       parsed["winner"],
        "summary":      parsed.get("summary", ""),
        "verdict":      parsed.get("verdict", ""),
        "strengths_a":  parsed.get("strengths_a", []),
        "weaknesses_a": parsed.get("weaknesses_a", []),
        "strengths_b":  parsed.get("strengths_b", []),
        "weaknesses_b": parsed.get("weaknesses_b", []),
    }, None