"""
services/job_matching_service.py

Matches user's CV against fetched jobs using the existing
ATS keyword scoring logic. No new ML models needed.

For low matches (<50%), calls LLM to generate a specific
improvement plan for that job.
"""

import re
import logging
from openai import OpenAI
import os

logger = logging.getLogger(__name__)

MATCH_THRESHOLD_GOOD = 65    # above this = good match
MATCH_THRESHOLD_LOW  = 40    # below this = generate improvement plan


def match_cv_to_jobs(
    analysis_result: dict,
    jobs: list,
) -> list:
    """
    Score each job against the user's existing CV analysis.

    Reuses the already-computed analysis data from the DB
    (missing_keywords, scores, sections) — no re-processing needed.

    Args:
        analysis_result: dict with keys: missing_keywords, missing_sections,
                         scores, overall_score, detected_sections
        jobs:            list of normalized job dicts from job_service

    Returns:
        list of job dicts with added match_score, match_label,
        matched_keywords, missing_job_keywords — sorted best first
    """
    if not jobs or not analysis_result:
        return []

    # Keywords the user already has (not missing)
    all_missing = set(k.lower() for k in (analysis_result.get("missing_keywords") or []))
    overall     = analysis_result.get("overall_score", 0)
    sections    = analysis_result.get("detected_sections") or []

    # Build user's keyword profile from their CV score context
    # We approximate "keywords they have" from overall score + sections
    results = []

    for job in jobs:
        match = _score_job_match(job, all_missing, overall, sections)
        results.append({**job, **match})

    # Sort by match score descending
    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results


def _score_job_match(
    job: dict,
    user_missing_keywords: set,
    user_overall_score: float,
    user_sections: list,
) -> dict:
    """
    Score how well user's CV matches a specific job.

    Strategy:
    1. Extract keywords from the job description
    2. Count how many are NOT in the user's missing keywords
       (meaning user likely HAS them)
    3. Penalize for missing required sections
    4. Blend with user's overall ATS score

    Returns match dict with score, label, matched/missing keywords.
    """
    jd_text    = (job.get("description") or "").lower()
    jd_keywords = _extract_jd_keywords(jd_text)

    if not jd_keywords:
        # No keywords extracted — use overall score as fallback
        match_score = round(user_overall_score * 0.7, 1)
        return _build_match_result(match_score, [], [])

    matched = []
    missing = []

    for kw in jd_keywords:
        if kw in user_missing_keywords:
            missing.append(kw)
        else:
            matched.append(kw)

    # Base score: ratio of matched to total JD keywords
    keyword_ratio = len(matched) / len(jd_keywords) if jd_keywords else 0
    keyword_score = keyword_ratio * 100

    # Blend: 60% keyword match + 40% overall ATS score
    blended = (keyword_score * 0.60) + (user_overall_score * 0.40)

    # Bonus: user has all required sections
    required = {"experience", "skills", "education"}
    has_all_required = required.issubset(set(user_sections))
    if has_all_required:
        blended = min(blended + 5, 100)

    match_score = round(min(max(blended, 0), 100), 1)
    return _build_match_result(match_score, matched[:10], missing[:10])


def _build_match_result(score: float, matched: list, missing: list) -> dict:
    if score >= MATCH_THRESHOLD_GOOD:
        label = "good"
        color = "#059669"
    elif score >= MATCH_THRESHOLD_LOW:
        label = "fair"
        color = "#D97706"
    else:
        label = "low"
        color = "#DC2626"

    return {
        "match_score":           score,
        "match_label":           label,
        "match_color":           color,
        "matched_keywords":      matched,
        "missing_job_keywords":  missing,
    }


def _extract_jd_keywords(jd_text: str) -> list:
    """
    Extract meaningful keywords from a job description.
    Reuses the same stop word logic as scoring_service.
    """
    from app.services.scoring_service import JD_STOP_WORDS

    words = re.findall(r'\b[a-z][a-z0-9+#\./\-]{1,30}\b', jd_text)
    unigrams = list({
        w for w in words
        if w not in JD_STOP_WORDS and len(w) > 2
    })[:30]

    tokens = re.findall(r'\b[a-z][a-z0-9+#/\-]{1,20}\b', jd_text)
    bigrams = [
        f"{tokens[i]} {tokens[i+1]}"
        for i in range(len(tokens) - 1)
        if tokens[i] not in JD_STOP_WORDS
        and tokens[i+1] not in JD_STOP_WORDS
        and len(tokens[i]) > 2
        and len(tokens[i+1]) > 2
    ][:15]

    return unigrams + bigrams


def generate_job_improvement_plan(
    job: dict,
    analysis_result: dict,
    major: str,
) -> tuple:
    """
    Generate a specific improvement plan for a low-matching job using GPT.

    Only called when match_score < MATCH_THRESHOLD_LOW (40%).

    Args:
        job:             normalized job dict with title, company, description
        analysis_result: user's existing analysis with scores and missing items
        major:           user's industry major

    Returns:
        (plan_dict, None) or (None, error_string)
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None, "OpenAI API key not configured."

    missing_keywords = (analysis_result.get("missing_keywords") or [])[:15]
    missing_sections = analysis_result.get("missing_sections") or []
    overall_score    = analysis_result.get("overall_score", 0)
    scores           = analysis_result.get("scores") or {}

    # Find weakest criteria
    weak_criteria = [
        k.replace("_score", "").replace("_", " ")
        for k, v in scores.items()
        if isinstance(v, (int, float)) and v < 50
    ]

    jd_preview = (job.get("description") or "")[:600]

    prompt = f"""You are an expert career coach. A job seeker's CV scored {overall_score}/100
and matched poorly against this job. Generate a specific, actionable improvement plan.

JOB TITLE: {job.get('title', '')}
COMPANY: {job.get('company', '')}
JOB DESCRIPTION (excerpt):
{jd_preview}

CV WEAKNESSES:
- Overall ATS score: {overall_score}/100
- Missing sections: {', '.join(missing_sections) if missing_sections else 'None'}
- Missing keywords for this job: {', '.join(job.get('missing_job_keywords', []))}
- Weak ATS criteria: {', '.join(weak_criteria) if weak_criteria else 'None'}
- General missing keywords: {', '.join(missing_keywords)}

Respond ONLY with valid JSON. No markdown, no backticks.

{{
  "summary": "2 sentence honest assessment of why the CV doesn't match this job",
  "estimated_weeks": <integer 1-12 — realistic time to become competitive>,
  "steps": [
    {{
      "week": "Week 1-2",
      "action": "Specific action title",
      "detail": "Exactly what to do and why it helps for this specific job",
      "priority": <1=critical, 2=important, 3=nice-to-have>
    }}
  ],
  "keywords_to_add": ["keyword1", "keyword2", "keyword3"],
  "quick_wins": ["One thing you can do today", "Another quick win"]
}}

Rules:
- steps must be specific to THIS job and THIS company, not generic advice
- keywords_to_add should be from the job description keywords the user is missing
- quick_wins are things achievable in under 1 hour
- Be honest but encouraging
- Maximum 5 steps
"""

    try:
        client   = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model       = "gpt-4o-mini",
            max_tokens  = 800,
            temperature = 0.3,
            messages=[
                {"role": "system", "content": "You are an expert career coach. Respond only with valid JSON."},
                {"role": "user",   "content": prompt},
            ]
        )

        raw  = response.choices[0].message.content.strip()
        raw  = raw.replace("```json", "").replace("```", "").strip()

        import json
        plan = json.loads(raw)
        return plan, None

    except json.JSONDecodeError:
        return None, "Failed to parse improvement plan response."
    except Exception as e:
        logger.error(f"Improvement plan generation failed: {e}")
        return None, f"Failed to generate plan: {str(e)}"