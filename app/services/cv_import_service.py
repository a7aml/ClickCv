"""
services/cv_import_service.py

Parses an uploaded CV file into structured JSON that matches the
CV builder's content_json schemas — ready to pre-fill all form fields.

Flow:
    1. extract_text_from_file()  — get raw text (reuses extraction_service)
    2. detect_sections()         — split into named sections (reuses nlp_service)
    3. _structure_with_llm()     — GPT maps each section to builder schema
    4. Return structured dict    — frontend fills all fields from this

The LLM call is the only new logic here. Everything else reuses
your existing pipeline — no duplication.

Schema returned:
    {
      "contact":        {"name","email","phone","location","linkedin","website"},
      "summary":        {"text"},
      "experience":     [{"job_title","company","start_date","end_date","description"}],
      "education":      [{"degree","institution","field_of_study","end_date","gpa"}],
      "skills":         [{"category","skills":[]}],
      "projects":       [{"title","tech_stack","description","url"}],
      "certifications": [{"name","issuer","date"}],
      "languages":      [{"language","proficiency"}]
    }
"""

import os
import json
import tempfile
import re
from flask import current_app

from app.services.extraction_service import extract_text_from_file
from app.services.nlp_service import detect_sections


# ─────────────────────────────────────────────────────────────────────────────
def import_cv_from_file(file_storage) -> tuple[dict | None, str | None]:
    """
    Main entry point. Accepts a Werkzeug FileStorage object (from request.files).

    Steps:
        1. Save file to temp path
        2. Extract text
        3. Detect sections
        4. Structure with LLM
        5. Clean up temp file

    Returns:
        (structured_dict, None)  on success
        (None, error_string)     on failure
    """
    filename = file_storage.filename or ""
    ext      = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in ("pdf", "docx"):
        return None, "Only PDF and DOCX files are supported."

    # Save to a temp file so extraction_service can read it by path
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=f".{ext}",
            dir=tempfile.gettempdir()
        ) as tmp:
            file_storage.save(tmp)
            tmp_path = tmp.name

        # Step 1: extract raw text
        raw_text, error = extract_text_from_file(tmp_path)
        if error:
            return None, f"Could not read file: {error}"

        # Step 2: detect sections
        sections, error = detect_sections(raw_text)
        if error or not sections:
            return None, f"Could not parse CV structure: {error or 'No sections found'}"

        # Step 3: structure with LLM
        structured, error = _structure_with_llm(sections, raw_text)
        if error:
            return None, f"Could not structure CV data: {error}"

        return structured, None

    except Exception as e:
        current_app.logger.error(f"import_cv_from_file failed: {e}")
        return None, "An unexpected error occurred while importing your CV."

    finally:
        # Always clean up the temp file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
def _structure_with_llm(sections: dict, raw_text: str) -> tuple[dict | None, str | None]:
    """
    Use GPT to convert detected section text into the builder's exact schema.

    Why LLM here instead of regex:
        - Experience entries vary wildly in format across CVs
        - Dates appear in many formats (Jan 2022, 01/2022, 2022-01)
        - Skills may be comma-separated, bulleted, or in tables
        - GPT handles all these variations reliably in one call

    Prompt strategy:
        - Pass each section's raw text
        - Ask for ONLY JSON output matching our exact schema
        - Temperature 0.1 — we want structured extraction, not creativity
        - max_tokens 2000 — enough for a full CV

    Returns:
        (structured_dict, None)  on success
        (None, error_string)     on failure
    """
    try:
        import openai
        client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        # Build the sections summary to send to GPT
        # Cap each section at 800 chars to avoid token overflow
        sections_text = ""
        for section_name, content in sections.items():
            capped = content[:800] + ("..." if len(content) > 800 else "")
            sections_text += f"\n\n=== {section_name.upper()} ===\n{capped}"

        system_prompt = """You are a CV parser. Extract structured data from CV sections and return ONLY valid JSON.
No explanation, no markdown, no code blocks — raw JSON only.

Return this exact structure:
{
  "contact": {
    "name": "",
    "email": "",
    "phone": "",
    "location": "",
    "linkedin": "",
    "website": ""
  },
  "summary": {
    "text": ""
  },
  "experience": [
    {
      "job_title": "",
      "company": "",
      "start_date": "",
      "end_date": "",
      "description": ""
    }
  ],
  "education": [
    {
      "degree": "",
      "institution": "",
      "field_of_study": "",
      "end_date": "",
      "gpa": ""
    }
  ],
  "skills": [
    {
      "category": "",
      "skills": []
    }
  ],
  "projects": [
    {
      "title": "",
      "tech_stack": "",
      "description": "",
      "url": ""
    }
  ],
  "certifications": [
    {
      "name": "",
      "issuer": "",
      "date": ""
    }
  ],
  "languages": [
    {
      "language": "",
      "proficiency": ""
    }
  ]
}

Rules:
- Extract ONLY what is explicitly stated — never invent or assume data
- For skills: group into logical categories if possible (e.g. "Languages", "Frameworks", "Tools")
  If no categories exist, use one entry with category="" and all skills in the array
- For experience descriptions: preserve bullet points, join with newline \\n
- For dates: keep as written in the CV (e.g. "Jan 2022", "2021", "Present")
- For empty fields: use empty string "" or empty array []
- Remove entries that have no meaningful data (e.g. experience entry with no job_title)
- LinkedIn: extract URL or username. Website: extract GitHub or personal site URL
"""

        user_prompt = f"Parse this CV into the JSON structure:\n{sections_text}"

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=2000,
        )

        raw_response = response.choices[0].message.content.strip()

        # Strip any accidental markdown fences
        raw_response = re.sub(r"^```json\s*", "", raw_response)
        raw_response = re.sub(r"^```\s*",     "", raw_response)
        raw_response = re.sub(r"\s*```$",      "", raw_response)

        structured = json.loads(raw_response)

        # Validate and sanitize the response
        structured = _sanitize_structure(structured)

        return structured, None

    except json.JSONDecodeError as e:
        current_app.logger.error(f"LLM returned invalid JSON: {e}")
        return None, "CV parser returned unexpected data. Please try again."
    except Exception as e:
        current_app.logger.error(f"_structure_with_llm failed: {e}")
        return None, str(e)


# ─────────────────────────────────────────────────────────────────────────────
def _sanitize_structure(data: dict) -> dict:
    """
    Ensure the LLM response matches our exact schema.
    Fills in missing keys with safe defaults so the frontend
    never crashes on a missing field.
    """
    def safe_str(v):
        return str(v).strip() if v else ""

    def safe_list(v):
        return v if isinstance(v, list) else []

    # Contact
    contact = data.get("contact") or {}
    data["contact"] = {
        "name":     safe_str(contact.get("name")),
        "email":    safe_str(contact.get("email")),
        "phone":    safe_str(contact.get("phone")),
        "location": safe_str(contact.get("location")),
        "linkedin": safe_str(contact.get("linkedin")),
        "website":  safe_str(contact.get("website")),
    }

    # Summary
    summary = data.get("summary") or {}
    if isinstance(summary, str):
        data["summary"] = {"text": summary}
    else:
        data["summary"] = {"text": safe_str(summary.get("text"))}

    # Experience
    exp_list = safe_list(data.get("experience"))
    data["experience"] = [
        {
            "job_title":   safe_str(e.get("job_title")),
            "company":     safe_str(e.get("company")),
            "start_date":  safe_str(e.get("start_date")),
            "end_date":    safe_str(e.get("end_date")),
            "description": safe_str(e.get("description")),
        }
        for e in exp_list
        if isinstance(e, dict) and e.get("job_title")
    ]

    # Education
    edu_list = safe_list(data.get("education"))
    data["education"] = [
        {
            "degree":         safe_str(e.get("degree")),
            "institution":    safe_str(e.get("institution")),
            "field_of_study": safe_str(e.get("field_of_study")),
            "end_date":       safe_str(e.get("end_date")),
            "gpa":            safe_str(e.get("gpa")),
        }
        for e in edu_list
        if isinstance(e, dict) and e.get("degree")
    ]

    # Skills
    skills_list = safe_list(data.get("skills"))
    data["skills"] = [
        {
            "category": safe_str(s.get("category")),
            "skills":   [safe_str(sk) for sk in safe_list(s.get("skills")) if sk],
        }
        for s in skills_list
        if isinstance(s, dict) and s.get("skills")
    ]

    # Projects
    proj_list = safe_list(data.get("projects"))
    data["projects"] = [
        {
            "title":       safe_str(p.get("title")),
            "tech_stack":  safe_str(p.get("tech_stack")),
            "description": safe_str(p.get("description")),
            "url":         safe_str(p.get("url")),
        }
        for p in proj_list
        if isinstance(p, dict) and p.get("title")
    ]

    # Certifications
    cert_list = safe_list(data.get("certifications"))
    data["certifications"] = [
        {
            "name":   safe_str(c.get("name")),
            "issuer": safe_str(c.get("issuer")),
            "date":   safe_str(c.get("date")),
        }
        for c in cert_list
        if isinstance(c, dict) and c.get("name")
    ]

    # Languages
    lang_list = safe_list(data.get("languages"))
    data["languages"] = [
        {
            "language":    safe_str(l.get("language")),
            "proficiency": safe_str(l.get("proficiency")),
        }
        for l in lang_list
        if isinstance(l, dict) and l.get("language")
    ]

    return data