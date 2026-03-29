"""
services/llm_service.py

Generates section-by-section CV improvement recommendations
using the OpenAI API (GPT-4o mini).

Receives structured scoring data from scoring_service.py and
builds a precise prompt so the LLM gives specific, actionable
advice — not generic tips.

Recommendation depth is calibrated to the score band:
    strong     (75+)  → polishing tips only
    good       (65-74) → keyword + section fixes
    borderline (50-64) → major section rewrites
    weak       (<50)   → full restructure guidance

Returns a consistent (result, error) tuple matching the
(user, error) pattern used across the codebase.

Dependencies:
    pip install openai python-dotenv
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


# ── OpenAI client ─────────────────────────────────────────────────────────────
# Initialised once at module level.
# Reads OPENAI_API_KEY from .env automatically.
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
MODEL        = "gpt-4o-mini"
MAX_TOKENS   = 1500


# ── Prompt templates per score band ──────────────────────────────────────────
# Each band gets a different instruction so the LLM calibrates
# how deeply it rewrites vs polishes.

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


# ── Public API ────────────────────────────────────────────────────────────────

def generate_recommendations(
    sections:       dict,
    scoring_result: dict,
    major:          str,
    job_description: str = None,
) -> tuple:
    """
    Generate section-by-section CV improvement recommendations.

    Builds a structured prompt from the scoring result and calls
    GPT-4o mini. Returns structured JSON recommendations that the
    frontend renders as a diff for the user to accept/reject.

    Args:
        sections:        dict from nlp_service.detect_sections()
        scoring_result:  dict from scoring_service.calculate_ats_score()
        major:           industry string e.g. 'technology'
        job_description: optional raw JD text

    Returns:
        (recommendations_dict, None)   — success
        (None, error_string)           — failure

    recommendations_dict structure:
        {
            "overall_score":   91.4,
            "score_band":      "strong",
            "summary":         "Your CV scores 91.4...",
            "llm_action":      "polishing",
            "sections": [
                {
                    "section":          "experience",
                    "current_score":    84.0,
                    "priority":         1,
                    "issue":            "Achievements lack quantification",
                    "recommendation":   "Add specific metrics...",
                    "rewrite_example":  "Led team of 6 engineers, reducing..."
                },
                ...
            ],
            "missing_keywords": ["ci/cd", "kubernetes"],
            "missing_sections": ["contact"]
        }
    """
    if not scoring_result:
        return None, "No scoring result provided for recommendations."

    if not sections:
        return None, "No sections provided for recommendations."

    # Build the prompt
    prompt = _build_prompt(sections, scoring_result, major, job_description)

    # Call the API
    raw_response, error = _call_openai(prompt)
    if error:
        return None, error

    # Parse the JSON response
    result, error = _parse_response(raw_response, scoring_result)
    if error:
        return None, error

    return result, None


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(
    sections:        dict,
    scoring_result:  dict,
    major:           str,
    job_description: str = None,
) -> str:
    """
    Build the structured prompt sent to GPT-4o mini.

    The prompt injects:
        - The actual ATS scores per criterion
        - The missing sections and keywords
        - The content of each detected section
        - The score band instruction (polishing vs restructure)
        - The industry and optional JD context

    This gives the LLM a precise brief so it generates specific,
    data-driven recommendations — not generic CV advice.

    Args:
        sections:       dict of section name → content
        scoring_result: dict from scoring_service
        major:          industry string
        job_description: optional JD text

    Returns:
        Prompt string ready to send to OpenAI
    """
    score        = scoring_result.get("overall_score", 0)
    band         = scoring_result.get("score_band", "weak")
    missing_sec  = scoring_result.get("missing_sections", [])
    missing_kw   = scoring_result.get("missing_keywords", [])[:15]
    band_instr   = BAND_INSTRUCTIONS.get(band, BAND_INSTRUCTIONS["weak"])

    # Build criterion scores block
    criteria_lines = []
    criteria_map = {
        "keyword_score":             "Keyword Matching (35%)",
        "keyword_placement_score":   "Keyword Placement (18%)",
        "formatting_score":          "Formatting Parsability (17%)",
        "structure_score":           "Section Completeness (12%)",
        "experience_recency_score":  "Experience Recency (10%)",
        "achievements_score":        "Quantifiable Achievements (10%)",
        "job_title_score":           "Job Title Matching (8%)",
        "education_score":           "Education & Certifications (7%)",
        "resume_length_score":       "Resume Length (4%)",
        "contact_info_score":        "Contact Information (3%)",
    }
    for key, label in criteria_map.items():
        val = scoring_result.get(key, 0)
        criteria_lines.append(f"  {label}: {val}/100")

    # Build section content block (truncated to save tokens)
    section_lines = []
    for name, content in sections.items():
        preview = content[:300].replace("\n", " ").strip()
        section_lines.append(f"  [{name.upper()}]\n  {preview}")

    # Build JD context if provided
    jd_block = ""
    if job_description and job_description.strip():
        jd_preview = job_description[:400].strip()
        jd_block = f"\nJOB DESCRIPTION (user is targeting this role):\n{jd_preview}\n"

    prompt = f"""You are an expert ATS resume analyst and career coach.
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

    return prompt


# ── OpenAI API call ───────────────────────────────────────────────────────────

def _call_openai(prompt: str) -> tuple:
    """
    Send the prompt to GPT-4o mini and return the raw response text.

    Uses temperature=0.3 for consistent, focused output.
    Lower temperature = less creative but more reliable JSON structure.

    Args:
        prompt: formatted prompt string from _build_prompt()

    Returns:
        (response_text, None) or (None, error_string)
    """
    try:
        client = _get_openai_client()
        response = client.chat.completions.create(

            model=MODEL,
            max_tokens=MAX_TOKENS,
            temperature=0.3,   # Low temperature = consistent structured output
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert ATS resume analyst. "
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

        # Give specific guidance for common errors
        if "authentication" in error_msg.lower() or "api key" in error_msg.lower():
            return None, (
                "OpenAI API key is invalid or missing. "
                "Check your OPENAI_API_KEY in the .env file."
            )
        if "rate limit" in error_msg.lower():
            return None, (
                "OpenAI rate limit reached. "
                "Please wait a moment and try again."
            )
        if "insufficient_quota" in error_msg.lower():
            return None, (
                "OpenAI account has insufficient credits. "
                "Please top up your OpenAI account."
            )

        return None, f"OpenAI API call failed: {error_msg}"


# ── Response parser ───────────────────────────────────────────────────────────

def _parse_response(raw_text: str, scoring_result: dict) -> tuple:
    """
    Parse the raw OpenAI response into a structured recommendations dict.

    Also merges scoring metadata (overall_score, score_band, missing_*)
    into the result so the caller gets everything in one place.

    Handles cases where the LLM accidentally wraps JSON in markdown
    backticks despite being told not to.

    Args:
        raw_text:       raw string from OpenAI response
        scoring_result: original scoring dict to merge metadata from

    Returns:
        (result_dict, None) or (None, error_string)
    """
    if not raw_text:
        return None, "Empty response received from OpenAI."

    # Strip accidental markdown code fences if present
    # e.g. ```json { ... } ``` → { ... }
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first line (```json or ```) and last line (```)
        cleaned = "\n".join(lines[1:-1]).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        return None, (
            f"Failed to parse OpenAI response as JSON: {str(e)}. "
            "The model returned malformed output — please try again."
        )

    # Validate required keys exist
    required_keys = ["summary_message", "sections"]
    for key in required_keys:
        if key not in parsed:
            return None, (
                f"OpenAI response missing required key '{key}'. "
                "Please try again."
            )

    # Merge scoring metadata into the result
    result = {
        "overall_score":    scoring_result.get("overall_score"),
        "score_band":       scoring_result.get("score_band"),
        "used_jd":          scoring_result.get("used_jd"),
        "missing_sections": scoring_result.get("missing_sections", []),
        "missing_keywords": scoring_result.get("missing_keywords", []),
        "summary_message":  parsed.get("summary_message", ""),
        "sections":         parsed.get("sections", []),
        "top_keywords_to_add": parsed.get("top_keywords_to_add", []),
        "quick_wins":       parsed.get("quick_wins", []),
    }

    return result, None