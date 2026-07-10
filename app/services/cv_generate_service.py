"""
services/cv_generate_service.py

"Generate Full Resume with AI" — Mode 2 of the CV Builder.

The user fills a short wizard with FACTS ONLY (job titles, companies,
dates, degrees, institutions, raw skill names, brief notes) and pastes
a job description. This module turns those facts into a complete,
ATS-optimized, JD-tailored resume — one section at a time.

STRICT ANTI-HALLUCINATION CONTRACT (same spirit as get_ai_hint_for_section):
    - Job titles, company names, dates, degrees, institutions, GPAs,
      and raw skill/tech names are NEVER invented or changed by the AI.
      They are either passed through verbatim (contact, education) or
      echoed back exactly inside AI-generated sections (experience,
      projects) — only the *prose* (descriptions, bullets, summary,
      skill categorization) is AI-generated.
    - If the AI call fails for any section, a non-AI fallback formatter
      is used so the draft is still usable (degraded, not broken).

Functions:
    format_contact_section       — facts → content_json (no AI)
    format_education_section     — facts → content_json (no AI)
    generate_experience_section  — AI bullets for each job (1 call)
    generate_skills_section      — AI categorization of raw skills (1 call)
    generate_projects_section    — AI descriptions for each project (1 call)
    generate_summary_section     — AI professional summary (1 call, last —
                                    uses the generated experience/skills)

    format_experience_fallback / format_skills_fallback /
    format_projects_fallback     — non-AI fallbacks if a call fails
"""

import json
import os

from flask import current_app


# ─────────────────────────────────────────────────────────────────────────────
# NON-AI FORMATTERS — facts only, no LLM call needed
# ─────────────────────────────────────────────────────────────────────────────

def format_contact_section(contact: dict) -> dict:
    """
    Map wizard contact fields straight into the builder's content_json
    schema for the 'contact' section. No AI — pure facts.
    """
    return {
        "name":     (contact.get("name") or "").strip(),
        "email":    (contact.get("email") or "").strip(),
        "phone":    (contact.get("phone") or "").strip(),
        "location": (contact.get("location") or "").strip(),
        "linkedin": (contact.get("linkedin") or "").strip(),
        "website":  (contact.get("website") or "").strip(),
    }


def format_education_section(education: list) -> list:
    """
    Map wizard education entries straight into the builder's
    content_json schema for the 'education' section. No AI.
    """
    result = []
    for item in education or []:
        if not (item.get("degree") or "").strip():
            continue
        result.append({
            "degree":         (item.get("degree") or "").strip(),
            "institution":    (item.get("institution") or "").strip(),
            "field_of_study": (item.get("field_of_study") or "").strip(),
            "end_date":       (item.get("end_date") or "").strip(),
            "gpa":            (item.get("gpa") or "").strip(),
        })
    return result


# ─────────────────────────────────────────────────────────────────────────────
# FALLBACKS — used only if the corresponding AI call fails
# ─────────────────────────────────────────────────────────────────────────────

def format_experience_fallback(experience: list) -> list:
    """
    If AI generation fails, fall back to the user's raw notes as the
    description (or empty) — facts are preserved either way.
    """
    result = []
    for item in experience or []:
        if not (item.get("job_title") or "").strip():
            continue
        result.append({
            "job_title":   (item.get("job_title") or "").strip(),
            "company":     (item.get("company") or "").strip(),
            "start_date":  (item.get("start_date") or "").strip(),
            "end_date":    (item.get("end_date") or "").strip(),
            "description": (item.get("notes") or "").strip(),
        })
    return result


def format_skills_fallback(skills: list) -> list:
    """If AI categorization fails, put everything in one 'Skills' category."""
    flat = [s.strip() for s in (skills or []) if s and s.strip()]
    if not flat:
        return []
    return [{"category": "Skills", "skills": flat}]


def format_projects_fallback(projects: list) -> list:
    """If AI generation fails, use the user's raw notes as the description."""
    result = []
    for item in projects or []:
        if not (item.get("title") or "").strip():
            continue
        result.append({
            "title":       (item.get("title") or "").strip(),
            "tech_stack":  (item.get("tech_stack") or "").strip(),
            "description": (item.get("notes") or "").strip(),
            "url":         (item.get("url") or "").strip(),
        })
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Shared OpenAI client helper
# ─────────────────────────────────────────────────────────────────────────────

def _client():
    import openai
    return openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def _jd_snippet(jd_text: str, limit: int = 1200) -> str:
    jd_text = (jd_text or "").strip()
    if not jd_text:
        return "No job description provided."
    return jd_text[:limit] + ("..." if len(jd_text) > limit else "")


# ─────────────────────────────────────────────────────────────────────────────
# EXPERIENCE — AI writes bullets for each job, facts preserved
# ─────────────────────────────────────────────────────────────────────────────

def generate_experience_section(
    experience: list,
    jd_text: str,
    target_title: str,
) -> tuple[list | None, str | None]:
    """
    Generate ATS-optimized bullet descriptions for each work experience
    entry, tailored to the job description.

    Input entries: [{job_title, company, start_date, end_date, notes}]
    Output entries: same job_title/company/dates (UNCHANGED), with a new
    'description' field containing 3-4 bullet points (newline-separated).

    If `experience` is empty, returns ([], None) — not an error.
    """
    clean = [e for e in (experience or []) if (e.get("job_title") or "").strip()]
    if not clean:
        return [], None

    try:
        client = _client()

        system_prompt = (
            "You are an expert resume writer specializing in ATS optimization. "
            "You will be given a list of work experience entries (job title, "
            "company, dates, and the candidate's brief notes about what they did), "
            "plus a target job description.\n\n"
            "For EACH entry, write a 'description' field containing 3-4 "
            "achievement-oriented bullet points (each starting with a strong "
            "action verb, newline-separated within the string).\n\n"
            "STRICT RULES:\n"
            "1. NEVER change job_title, company, start_date, or end_date — "
            "echo them back EXACTLY as given, in the same order.\n"
            "2. NEVER invent employers, titles, dates, tools, or achievements "
            "the candidate did not mention in their notes.\n"
            "3. You MAY rephrase the candidate's notes into stronger, more "
            "specific, quantifiable-sounding language, and naturally weave in "
            "relevant keywords from the job description WHERE THEY GENUINELY "
            "APPLY to what the candidate described.\n"
            "4. If notes are sparse, write fewer but still honest bullets — "
            "do not pad with fabricated specifics.\n"
            "5. Return ONLY a JSON object: "
            '{"experience": [{"job_title": "...", "company": "...", '
            '"start_date": "...", "end_date": "...", "description": "..."}]}'
        )

        user_prompt = (
            f"Target role: {target_title or 'Not specified'}\n\n"
            f"Job Description:\n{_jd_snippet(jd_text)}\n\n"
            f"Experience entries (JSON):\n{json.dumps(clean, ensure_ascii=False)}\n\n"
            "Return the JSON object described in the instructions, with one "
            "entry per input entry, in the same order."
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=900,
        )

        result = json.loads(response.choices[0].message.content)
        experience_out = result.get("experience")

        if not isinstance(experience_out, list) or not experience_out:
            raise ValueError("AI returned no experience entries.")

        return experience_out, None

    except Exception as e:
        current_app.logger.error(f"generate_experience_section failed: {e}")
        return None, str(e)


# ─────────────────────────────────────────────────────────────────────────────
# SKILLS — AI organizes raw skills into categories
# ─────────────────────────────────────────────────────────────────────────────

def generate_skills_section(
    skills: list,
    jd_text: str,
) -> tuple[list | None, str | None]:
    """
    Organize a flat list of raw skill names into 2-5 sensible categories
    (e.g. "Programming Languages", "Frameworks & Libraries", "Tools & Platforms",
    "Soft Skills"), ordered so categories most relevant to the job
    description appear first.

    Input: ["Python", "Flask", "Docker", "Leadership", ...]
    Output: [{"category": "...", "skills": [...]}]

    STRICT: the set of skills returned must be EXACTLY the input skills
    (same strings, possibly re-cased/trimmed) — no additions, no removals.
    If `skills` is empty, returns ([], None) — not an error.
    """
    clean = [s.strip() for s in (skills or []) if s and s.strip()]
    if not clean:
        return [], None

    try:
        client = _client()

        system_prompt = (
            "You are an expert resume writer. You will be given a flat list "
            "of a candidate's raw skill names and a target job description.\n\n"
            "Organize these skills into 2-5 well-named categories suitable for "
            "a resume's Skills section (e.g. 'Programming Languages', "
            "'Frameworks & Libraries', 'Tools & Platforms', 'Soft Skills', "
            "'Databases'). Order the categories so the ones most relevant to "
            "the job description appear first.\n\n"
            "STRICT RULES:\n"
            "1. The union of all skills across all categories MUST exactly "
            "match the input list — same items, no additions, no removals, "
            "no duplicates. You may fix obvious capitalization (e.g. "
            "'python' -> 'Python', 'AWS' stays 'AWS').\n"
            "2. Every input skill must appear in exactly one category.\n"
            "3. Return ONLY a JSON object: "
            '{"skills": [{"category": "...", "skills": ["...", "..."]}]}'
        )

        user_prompt = (
            f"Job Description:\n{_jd_snippet(jd_text)}\n\n"
            f"Raw skills (JSON array):\n{json.dumps(clean, ensure_ascii=False)}\n\n"
            "Return the JSON object described in the instructions."
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=500,
        )

        result = json.loads(response.choices[0].message.content)
        skills_out = result.get("skills")

        if not isinstance(skills_out, list) or not skills_out:
            raise ValueError("AI returned no skill categories.")

        return skills_out, None

    except Exception as e:
        current_app.logger.error(f"generate_skills_section failed: {e}")
        return None, str(e)


# ─────────────────────────────────────────────────────────────────────────────
# PROJECTS — AI writes descriptions for each project, facts preserved
# ─────────────────────────────────────────────────────────────────────────────

def generate_projects_section(
    projects: list,
    jd_text: str,
) -> tuple[list | None, str | None]:
    """
    Generate ATS-optimized descriptions for each project entry, tailored
    to the job description.

    Input entries: [{title, tech_stack, notes, url}]
    Output entries: same title/tech_stack/url (UNCHANGED), with a new
    'description' field (1-2 sentences, or 2-3 bullet points).

    If `projects` is empty, returns ([], None) — not an error.
    """
    clean = [p for p in (projects or []) if (p.get("title") or "").strip()]
    if not clean:
        return [], None

    try:
        client = _client()

        system_prompt = (
            "You are an expert resume writer specializing in ATS optimization. "
            "You will be given a list of project entries (title, tech stack, "
            "URL, and the candidate's brief notes), plus a target job description.\n\n"
            "For EACH entry, write a 'description' field (1-2 concise sentences, "
            "or up to 3 short bullet points newline-separated) describing what "
            "was built and its impact, naturally incorporating relevant "
            "keywords from the job description WHERE THEY GENUINELY APPLY.\n\n"
            "STRICT RULES:\n"
            "1. NEVER change title, tech_stack, or url — echo them back "
            "EXACTLY as given, in the same order.\n"
            "2. NEVER invent technologies, metrics, or outcomes the candidate "
            "did not mention in their notes.\n"
            "3. You MAY rephrase the candidate's notes into stronger language.\n"
            "4. Return ONLY a JSON object: "
            '{"projects": [{"title": "...", "tech_stack": "...", '
            '"description": "...", "url": "..."}]}'
        )

        user_prompt = (
            f"Job Description:\n{_jd_snippet(jd_text)}\n\n"
            f"Project entries (JSON):\n{json.dumps(clean, ensure_ascii=False)}\n\n"
            "Return the JSON object described in the instructions, with one "
            "entry per input entry, in the same order."
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=700,
        )

        result = json.loads(response.choices[0].message.content)
        projects_out = result.get("projects")

        if not isinstance(projects_out, list) or not projects_out:
            raise ValueError("AI returned no project entries.")

        return projects_out, None

    except Exception as e:
        current_app.logger.error(f"generate_projects_section failed: {e}")
        return None, str(e)


# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY — AI writes the professional summary LAST, using everything else
# ─────────────────────────────────────────────────────────────────────────────

def generate_summary_section(
    contact: dict,
    target_title: str,
    experience: list,
    education: list,
    skills: list,
    jd_text: str,
) -> tuple[dict | None, str | None]:
    """
    Generate a 2-3 sentence professional summary tailored to the job
    description, based on the (already-generated) experience, education,
    and skills.

    Output: {"text": "..."}
    """
    try:
        client = _client()

        # Build a compact context string — avoid sending huge payloads
        exp_lines = []
        for e in (experience or [])[:5]:
            title = e.get("job_title", "")
            company = e.get("company", "")
            if title:
                exp_lines.append(f"- {title}" + (f" at {company}" if company else ""))

        edu_lines = []
        for ed in (education or [])[:3]:
            degree = ed.get("degree", "")
            field = ed.get("field_of_study", "")
            if degree:
                edu_lines.append(f"- {degree}" + (f" in {field}" if field else ""))

        skill_names = []
        for cat in (skills or []):
            skill_names.extend(cat.get("skills", []))
        skill_str = ", ".join(skill_names[:20])

        system_prompt = (
            "You are an expert resume writer specializing in ATS optimization. "
            "Write a professional summary (2-3 sentences, no more) for the top "
            "of a resume, tailored to the target job description.\n\n"
            "STRICT RULES:\n"
            "1. Base the summary ONLY on the candidate's actual experience, "
            "education, and skills provided below — never invent years of "
            "experience, job titles, employers, or credentials not given.\n"
            "2. Naturally incorporate 2-4 keywords from the job description "
            "that genuinely match the candidate's background.\n"
            "3. Write in third-person-omitted style typical of resumes "
            "(e.g. 'Results-driven software engineer with experience in...').\n"
            "4. Return ONLY a JSON object: {\"text\": \"...\"}"
        )

        user_prompt = (
            f"Target role: {target_title or 'Not specified'}\n\n"
            f"Job Description:\n{_jd_snippet(jd_text)}\n\n"
            f"Experience:\n" + ("\n".join(exp_lines) if exp_lines else "None provided") + "\n\n"
            f"Education:\n" + ("\n".join(edu_lines) if edu_lines else "None provided") + "\n\n"
            f"Skills: {skill_str or 'None provided'}\n\n"
            "Return the JSON object described in the instructions."
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.4,
            max_tokens=250,
        )

        result = json.loads(response.choices[0].message.content)
        text = (result.get("text") or "").strip()

        if not text:
            raise ValueError("AI returned an empty summary.")

        return {"text": text}, None

    except Exception as e:
        current_app.logger.error(f"generate_summary_section failed: {e}")
        return None, str(e)