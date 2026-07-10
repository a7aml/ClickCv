"""
services/cv_builder_service.py

Business logic for the CV Builder module.

Functions:
    build_draft_response    — serialize a CvDraft + sections to dict
    get_ai_hint_for_section — call LLM to generate field hints (Mode 2)
    score_draft             — convert draft sections to raw_text and score it
    export_draft            — render draft to PDF or DOCX file
"""

import os
import uuid
from datetime import datetime
from flask import current_app

from app.models.cv_draft import CvDraft
from app.models.cv_draft_section import CvDraftSection


# ─────────────────────────────────────────────────────────────────────────────
def build_draft_response(draft: CvDraft) -> dict:
    """
    Serialize a CvDraft and all its sections into a JSON-safe dict.
    Used by GET /draft/<id>.
    """
    sections = (
        CvDraftSection.query
        .filter_by(draft_id=draft.id)
        .order_by(CvDraftSection.position)
        .all()
    )

    return {
        "draft_id":            draft.id,
        "mode":                draft.mode,
        "template_id":         draft.template_id,
        "status":              draft.status,
        "job_description_id":  draft.job_description_id,
        "created_at":          draft.created_at.isoformat() if draft.created_at else None,
        "updated_at":          draft.updated_at.isoformat() if draft.updated_at else None,
        "sections": [
            {
                "section_type": s.section_type,
                "position":     s.position,
                "content_json": s.content_json,
                "ai_hint_json": s.ai_hint_json,
            }
            for s in sections
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
def get_ai_hint_for_section(
    section_type: str,
    current_content: dict,
    job_description: str,
) -> tuple[dict | None, str | None]:
    """
    Call the LLM to generate per-field hints for one CV section.

    Returns:
        (hint_dict, None)  on success
        (None, error_str)  on failure

    hint_dict shape mirrors content_json — each field gets a suggested value.
    Example for 'summary':
        {"text": "Results-driven software engineer with 3+ years..."}
    """
    try:
        import openai
        client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        system_prompt = (
            "You are an expert CV writer and ATS optimization specialist. "
            "Given the user's current input for one CV section and a job description, "
            "return ONLY a JSON object with improved/suggested values for each field. "
            "Base suggestions strictly on the user's existing data — never invent "
            "companies, degrees, or experiences that the user has not provided. "
            "Improve wording, add relevant keywords from the JD, and quantify achievements where possible."
        )

        user_prompt = (
            f"Section: {section_type}\n\n"
            f"User's current input:\n{current_content}\n\n"
            f"Job Description:\n{job_description}\n\n"
            "Return a JSON object with improved field values for this section only. "
            "Match the exact same keys as the user's input."
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=800,
        )

        import json
        hint = json.loads(response.choices[0].message.content)
        return hint, None

    except Exception as e:
        current_app.logger.error(f"AI hint failed for section {section_type}: {e}")
        return None, str(e)




# ─────────────────────────────────────────────────────────────────────────────
def get_autocomplete_suggestion(
    field_name: str,
    current_value: str,
    section_context: dict,
    job_description: str,
) -> tuple[str | None, str | None]:
    """
    Generate a single inline autocomplete suggestion for one CV field.

    Fast and cheap — gpt-4o-mini with max_tokens=80.
    Returns a plain string ready to render as ghost text.

    Rules enforced via prompt:
    - Never invent companies, dates, degrees, or technologies
    - Only use facts from job_description and section_context
    - If current_value exists, continue it naturally
    - If empty, write the most suitable opening for that field type
    """
    try:
        import openai
        client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        context_parts = [
            f"{k}: {v}" for k, v in section_context.items() if v and k != field_name
        ]
        context_str = "\n".join(context_parts) if context_parts else "No other fields filled yet."
        jd_snippet  = (job_description[:600] + "...") if len(job_description) > 600 else job_description
        jd_str      = jd_snippet if jd_snippet else "No job description provided."

        system_prompt = (
            "You are an expert CV writer specializing in ATS optimization. "
            "Your ONLY job is to suggest a short completion for one specific CV field. "
            "STRICT RULES:\n"
            "1. NEVER invent facts — no fake companies, dates, technologies, or achievements\n"
            "2. Only use information from the job description and already-filled context fields\n"
            "3. If the user has started typing, continue their sentence naturally\n"
            "4. If the field is empty, write the most suitable value for that field type\n"
            "5. Maximum 1-2 sentences or a brief phrase\n"
            "6. Return ONLY the suggestion text — no quotes, no labels, no explanation\n"
            "7. Use ATS keywords from the job description"
        )

        user_prompt = (
            f"CV Field: {field_name}\n"
            f"User typed so far: \"{current_value}\"\n\n"
            f"Other filled fields:\n{context_str}\n\n"
            f"Job Description:\n{jd_str}\n\n"
            f"{'Continue from where the user left off.' if current_value else 'Write a suitable value for this empty field.'} "
            f"Return only the suggestion text, nothing else."
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=80,
        )

        suggestion = response.choices[0].message.content.strip()
        if len(suggestion) >= 2 and suggestion[0] in ('"', "'") and suggestion[-1] == suggestion[0]:
            suggestion = suggestion[1:-1]
        return suggestion, None

    except Exception as e:
        current_app.logger.error(f"Autocomplete failed for field {field_name}: {e}")
        return None, str(e)



# ─────────────────────────────────────────────────────────────────────────────
def get_autocomplete_suggestion(
    field_name: str,
    current_value: str,
    section_context: dict,
    job_description: str,
) -> tuple[str | None, str | None]:
    """
    Generate a single inline autocomplete suggestion for one CV field.
    Fast — gpt-4o-mini with max_tokens=80. Returns plain string for ghost text.
    """
    try:
        import openai
        client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        context_parts = [
            f"{k}: {v}" for k, v in section_context.items() if v and k != field_name
        ]
        context_str = "\n".join(context_parts) if context_parts else "No other fields filled yet."
        jd_snippet  = (job_description[:600] + "...") if len(job_description) > 600 else job_description
        jd_str      = jd_snippet if jd_snippet.strip() else "No job description provided."

        system_prompt = (
            "You are an expert CV writer specializing in ATS optimization. "
            "Suggest a short natural completion for one specific CV field. "
            "STRICT RULES: "
            "1) NEVER invent facts — no fake companies, dates, or achievements. "
            "2) Only use info from the job description and already-filled context. "
            "3) If user has started typing, continue their sentence. "
            "4) If field is empty, write the most suitable value. "
            "5) Max 1-2 sentences. "
            "6) Return ONLY the suggestion text, no quotes or labels."
        )

        user_prompt = (
            f"CV Field: {field_name}\n"
            f"User typed: {repr(current_value)}\n\n"
            f"Other filled fields:\n{context_str}\n\n"
            f"Job Description:\n{jd_str}\n\n"
            + ("Continue from where the user left off." if current_value
               else "Write a suitable value for this empty field.")
            + " Return only the suggestion text."
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=80,
        )

        suggestion = response.choices[0].message.content.strip()
        # Strip surrounding quotes model might add
        if len(suggestion) >= 2 and suggestion[0] in ('"', "'") and suggestion[-1] == suggestion[0]:
            suggestion = suggestion[1:-1]

        return suggestion, None

    except Exception as e:
        current_app.logger.error(f"Autocomplete failed for field {field_name}: {e}")
        return None, str(e)



# ─────────────────────────────────────────────────────────────────────────────
def get_autocomplete_suggestion(
    field_name: str,
    current_value: str,
    section_context: dict,
    job_description: str,
) -> tuple[str | None, str | None]:
    """
    Generate a single inline autocomplete suggestion for one CV field.
    Fast — gpt-4o-mini with max_tokens=80. Returns plain string for ghost text.
    Never invents facts — only uses job_description and section_context.
    """
    try:
        import openai
        client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        context_parts = [
            f"{k}: {v}" for k, v in section_context.items() if v and k != field_name
        ]
        context_str = "\n".join(context_parts) if context_parts else "No other fields filled yet."
        jd_snippet  = (job_description[:600] + "...") if len(job_description) > 600 else job_description
        jd_str      = jd_snippet if jd_snippet.strip() else "No job description provided."

        system_prompt = (
            "You are an expert CV writer specializing in ATS optimization. "
            "Suggest a short natural completion for one specific CV field. "
            "RULES: "
            "1) NEVER invent facts — no fake companies, dates, or achievements. "
            "2) Only use info from the job description and already-filled context fields. "
            "3) If user has started typing, continue their sentence naturally. "
            "4) If field is empty, write the most suitable opening value. "
            "5) Max 1-2 sentences or a brief phrase. "
            "6) Return ONLY the suggestion text — no quotes, no labels, no explanation."
        )

        user_prompt = (
            f"CV Field: {field_name}\n"
            f"User typed so far: {repr(current_value)}\n\n"
            f"Other filled fields in this section:\n{context_str}\n\n"
            f"Job Description:\n{jd_str}\n\n"
            + ("Continue from where the user left off." if current_value
               else "Write a suitable value for this empty field.")
            + " Return only the suggestion text."
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=80,
        )

        suggestion = response.choices[0].message.content.strip()
        if len(suggestion) >= 2 and suggestion[0] in ('"', "'") and suggestion[-1] == suggestion[0]:
            suggestion = suggestion[1:-1]

        return suggestion, None

    except Exception as e:
        current_app.logger.error(f"Autocomplete failed for field {field_name}: {e}")
        return None, str(e)


# ─────────────────────────────────────────────────────────────────────────────
def _draft_to_raw_text(draft: CvDraft) -> str:
    """
    Convert all draft sections into a single plain-text string
    suitable for feeding into the existing ATS scoring pipeline.

    Section order follows position field.
    """
    sections = (
        CvDraftSection.query
        .filter_by(draft_id=draft.id)
        .order_by(CvDraftSection.position)
        .all()
    )

    lines = []

    for section in sections:
        content = section.content_json
        stype   = section.section_type

        lines.append(stype.upper())  # Section header

        if stype == "contact":
            for field in ["name", "email", "phone", "location", "linkedin", "website"]:
                val = content.get(field, "")
                if val:
                    lines.append(val)

        elif stype == "summary":
            lines.append(content.get("text", ""))

        elif stype in ("experience", "projects", "certifications", "languages", "awards", "volunteer"):
            # List of entries
            entries = content if isinstance(content, list) else []
            for entry in entries:
                lines.append(" | ".join(str(v) for v in entry.values() if v))

        elif stype == "education":
            entries = content if isinstance(content, list) else []
            for entry in entries:
                parts = [
                    entry.get("degree", ""),
                    entry.get("field_of_study", ""),
                    entry.get("institution", ""),
                    entry.get("gpa", ""),
                ]
                lines.append(" | ".join(p for p in parts if p))

        elif stype == "skills":
            categories = content if isinstance(content, list) else []
            for cat in categories:
                skills = cat.get("skills", [])
                lines.append(f"{cat.get('category', '')}: {', '.join(skills)}")

        lines.append("")  # blank line between sections

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
def score_draft(
    draft: CvDraft,
    major: str,
    jd_text: str | None,
) -> tuple[dict | None, str | None]:
    """
    Run the existing ATS scoring pipeline on the draft content.

    Converts draft sections → raw_text → feeds into scoring_service.
    No file needed — draft content is already structured.

    Returns:
        (result_dict, None)  on success
        (None, error_str)    on failure
    """
    try:
        from app.services.nlp_service import detect_sections, extract_keywords_per_section
        from app.services.scoring_service import calculate_ats_score

        raw_text = _draft_to_raw_text(draft)

        if not raw_text.strip():
            return None, "Draft has no content to score."

        sections, error = detect_sections(raw_text)
        if error:
            return None, f"Section detection failed: {error}"

        keyword_placement, _ = extract_keywords_per_section(sections)
        keyword_placement    = keyword_placement or {}

        scoring_result, error = calculate_ats_score(
            raw_text          = raw_text,
            sections          = sections,
            keyword_placement = keyword_placement,
            major             = major,
            job_description   = jd_text,
            file_path         = None,   # no file for builder drafts
        )
        if error:
            return None, f"Scoring failed: {error}"

        return {
            "overall_score":  scoring_result["overall_score"],
            "score_band":     scoring_result["score_band"],
            "scores": {
                "keyword_score":            scoring_result["keyword_score"],
                "keyword_placement_score":  scoring_result["keyword_placement_score"],
                "formatting_score":         scoring_result["formatting_score"],
                "structure_score":          scoring_result["structure_score"],
                "experience_recency_score": scoring_result["experience_recency_score"],
                "achievements_score":       scoring_result["achievements_score"],
                "job_title_score":          scoring_result["job_title_score"],
                "education_score":          scoring_result["education_score"],
                "resume_length_score":      scoring_result["resume_length_score"],
                "contact_info_score":       scoring_result["contact_info_score"],
            },
            "missing_sections": scoring_result["missing_sections"],
            "missing_keywords": scoring_result["missing_keywords"],
        }, None

    except Exception as e:
        current_app.logger.error(f"score_draft failed: {e}")
        return None, str(e)


# ─────────────────────────────────────────────────────────────────────────────
def export_draft(
    draft: CvDraft,
    file_format: str,
) -> tuple[str | None, str | None]:
    """
    Render the draft to a PDF or DOCX file and return the file path.

    Returns:
        (file_path, None)   on success
        (None, error_str)   on failure

    Note: Full PDF/DOCX rendering implementation comes in Phase 4.
    This stub is wired up so routes work end-to-end now.
    """
    try:
        # Build absolute, OS-normalized export path
        root = current_app.root_path                      # e.g. C:\FYP\ClickCv\app
        export_folder = current_app.config.get(
            "EXPORT_FOLDER",
            os.path.abspath(os.path.join(root, "static", "exports"))
        )
        os.makedirs(export_folder, exist_ok=True)

        filename  = f"draft_{draft.id}_{uuid.uuid4().hex[:8]}.{file_format}"
        file_path = os.path.abspath(os.path.join(export_folder, filename))

        current_app.logger.info(f"Exporting draft {draft.id} to: {file_path}")

        raw_text = _draft_to_raw_text(draft)

        if file_format == "pdf":
            _export_pdf(raw_text, file_path, draft)
        else:
            _export_docx(raw_text, file_path, draft)

        # Verify file was actually created
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Export file was not created at: {file_path}")

        current_app.logger.info(f"Export success: {file_path} ({os.path.getsize(file_path)} bytes)")
        return file_path, None

    except Exception as e:
        import traceback
        current_app.logger.error(f"export_draft failed: {e}\n{traceback.format_exc()}")
        return None, str(e)

def _export_pdf(raw_text: str, file_path: str, draft: CvDraft):
    """Export draft to a clean styled PDF using reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer,
        HRFlowable, Table, TableStyle
    )

    # Load sections
    sections = (
        CvDraftSection.query
        .filter_by(draft_id=draft.id)
        .order_by(CvDraftSection.position)
        .all()
    )
    sm = {s.section_type: s.content_json for s in sections}

    W, H   = A4
    LM = RM = 18 * mm
    uw     = W - LM - RM   # usable width

    doc = SimpleDocTemplate(
        file_path, pagesize=A4,
        leftMargin=LM, rightMargin=RM,
        topMargin=16*mm, bottomMargin=16*mm,
    )

    BLACK      = colors.black
    DARK_GRAY  = colors.HexColor("#333333")
    LIGHT_GRAY = colors.HexColor("#555555")
    WHITE      = colors.white

    def ps(name, **kw):
        base = dict(fontName="Times-Roman", fontSize=10, textColor=BLACK, leading=14)
        base.update(kw)
        return ParagraphStyle(name, **base)

    # ATS-friendly: all black/grey, no colour
    sec_t  = ps("st", fontName="Times-Bold", fontSize=9,   textColor=BLACK,      spaceBefore=8, spaceAfter=2)
    ent_t  = ps("et", fontName="Times-Bold", fontSize=11,  textColor=BLACK,      spaceAfter=1)
    sub_t  = ps("sb", fontSize=9.5,              textColor=LIGHT_GRAY,               spaceAfter=2)
    body_t = ps("bt", fontSize=10,               textColor=DARK_GRAY,  leading=14,   spaceAfter=3)
    skl_t  = ps("sk", fontSize=10,               textColor=DARK_GRAY,                spaceAfter=2)
    hdr_n  = ps("hn", fontName="Times-Bold", fontSize=22,  textColor=BLACK,      leading=26)
    hdr_c  = ps("hc", fontSize=9,                textColor=DARK_GRAY,  leading=13)
    dt_t   = ps("dt", fontSize=9,                textColor=LIGHT_GRAY, alignment=2)

    story = []

    # Header — plain white background, name centred, contact below
    contact = sm.get("contact") or {}
    if not isinstance(contact, dict):
        contact = {}
    name_str = contact.get("name") or "Your Name"
    parts = [contact.get("email",""), contact.get("phone",""),
             contact.get("location",""), contact.get("linkedin","")]
    cline = "  •  ".join(p for p in parts if p)

    # Name row — full width, centred
    name_style = ps("nm", fontName="Times-Bold", fontSize=22,
                    textColor=BLACK, leading=26, alignment=1)  # alignment=1 → centre
    contact_style = ps("ct", fontSize=9, textColor=DARK_GRAY,
                       leading=13, alignment=1)

    story.append(Paragraph(name_str.upper(), name_style))
    if cline:
        story.append(Paragraph(cline, contact_style))
    # Black line below contact info removed

    def section(title, items):
        if not items:
            return
        story.append(Paragraph(title.upper(), sec_t))
        story.append(HRFlowable(width="100%", thickness=0.75,
                                color=BLACK, spaceAfter=4))
        for it in items:
            story.append(it)
        story.append(Spacer(1, 3*mm))

    # Summary
    summ = sm.get("summary") or {}
    if isinstance(summ, dict) and summ.get("text"):
        section("Professional Summary", [Paragraph(summ["text"], body_t)])

    # Experience
    exp = sm.get("experience") or []
    if isinstance(exp, list) and exp:
        items = []
        for e in exp:
            if not e.get("job_title"):
                continue
            date = " - ".join(filter(None, [e.get("start_date",""), e.get("end_date","")]))
            row  = Table(
                [[Paragraph(e["job_title"], ent_t), Paragraph(date, dt_t)]],
                colWidths=[uw*0.7, uw*0.3]
            )
            row.setStyle(TableStyle([
                ("VALIGN",       (0,0),(-1,-1),"TOP"),
                ("LEFTPADDING",  (0,0),(-1,-1), 0),
                ("RIGHTPADDING", (0,0),(-1,-1), 0),
                ("TOPPADDING",   (0,0),(-1,-1), 0),
                ("BOTTOMPADDING",(0,0),(-1,-1), 0),
            ]))
            items.append(row)
            if e.get("company"):
                items.append(Paragraph(e["company"], sub_t))
            if e.get("description"):
                desc = e["description"].replace("\n", "<br/>")
                items.append(Paragraph(desc, body_t))
            items.append(Spacer(1, 3*mm))
        section("Work Experience", items)

    # Education
    edu = sm.get("education") or []
    if isinstance(edu, list) and edu:
        items = []
        for e in edu:
            if not e.get("degree"):
                continue
            items.append(Paragraph(e["degree"], ent_t))
            sub = "  |  ".join(filter(None, [e.get("institution",""), e.get("field_of_study","")]))
            if sub:
                items.append(Paragraph(sub, sub_t))
            tail = "  |  ".join(filter(None, [
                e.get("end_date",""),
                ("GPA: " + e["gpa"]) if e.get("gpa") else ""
            ]))
            if tail:
                items.append(Paragraph(tail, sub_t))
            items.append(Spacer(1, 3*mm))
        section("Education", items)

    # Skills
    skills = sm.get("skills") or []
    if isinstance(skills, list) and skills:
        items = []
        for cat in skills:
            cat_skills = cat.get("skills") or []
            if not cat_skills:
                continue
            cat_name = cat.get("category","")
            prefix   = "<b>" + cat_name + ":  </b>" if cat_name else ""
            items.append(Paragraph(prefix + ",  ".join(cat_skills), skl_t))
        section("Skills", items)

    # Projects
    proj = sm.get("projects") or []
    if isinstance(proj, list) and proj:
        items = []
        for p in proj:
            if not p.get("title"):
                continue
            items.append(Paragraph(p["title"], ent_t))
            if p.get("tech_stack"):
                items.append(Paragraph(p["tech_stack"], sub_t))
            if p.get("description"):
                items.append(Paragraph(p["description"], body_t))
            items.append(Spacer(1, 3*mm))
        section("Projects", items)

    # Certifications
    certs = sm.get("certifications") or []
    if isinstance(certs, list) and certs:
        items = []
        for c in certs:
            if not c.get("name"):
                continue
            items.append(Paragraph(c["name"], ent_t))
            sub = "  |  ".join(filter(None, [c.get("issuer",""), c.get("date","")]))
            if sub:
                items.append(Paragraph(sub, sub_t))
            items.append(Spacer(1, 2*mm))
        section("Certifications", items)

    # Languages
    langs = sm.get("languages") or []
    if isinstance(langs, list) and langs:
        items = []
        for l in langs:
            if not l.get("language"):
                continue
            items.append(Paragraph(
                "<b>" + l["language"] + "</b>  -  " + l.get("proficiency",""),
                skl_t
            ))
        section("Languages", items)

    if len(story) <= 2:
        story.append(Paragraph("Please fill in your CV details.", body_t))

    doc.build(story)


def _export_docx(raw_text: str, file_path: str, draft: CvDraft):
    """
    Render draft to DOCX.
    Phase 4 will replace this with a full template-aware renderer.
    Currently produces a plain-text DOCX using python-docx.
    """
    try:
        from docx import Document

        doc = Document()
        for line in raw_text.split("\n"):
            doc.add_paragraph(line)
        doc.save(file_path)
    except ImportError:
        with open(file_path, "w") as f:
            f.write(raw_text)