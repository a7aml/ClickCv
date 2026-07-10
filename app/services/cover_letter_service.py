"""
services/cover_letter_service.py

Generates tailored cover letters using OpenAI's GPT model.
Takes resume text + job description → produces professional cover letter.

Public function:
    generate_cover_letter() — Main entry point for cover letter generation

Follows same pattern as llm_service.py for consistency.
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


# ── OpenAI client ─────────────────────────────────────────────────────────────

def _get_openai_client():
    """
    Get OpenAI client with API key from environment.
    
    Returns:
        OpenAI: Configured client instance
        
    Raises:
        EnvironmentError: If OPENAI_API_KEY not found
    """
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


MODEL = "gpt-4o-mini"  # Fast and cost-effective for cover letters
MAX_TOKENS = 800       # Cover letters are typically 300-500 words


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API — generate_cover_letter
# ══════════════════════════════════════════════════════════════════════════════

def generate_cover_letter(
    resume_text: str,
    job_description: str,
    company_name: str = None,
    position_title: str = None,
) -> tuple:
    """
    Generate a tailored cover letter using AI.

    Takes the user's resume text and job description, then produces
    a professional, personalized cover letter that:
    - Highlights relevant experience from the resume
    - Addresses key requirements from the job description
    - Uses professional tone and structure
    - Includes company name and position if provided

    Args:
        resume_text:      Full extracted text from user's CV
        job_description:  Job description text
        company_name:     Company name (optional, for personalization)
        position_title:   Position title (optional, for personalization)

    Returns:
        (cover_letter_text, None)  — success
        (None, error_string)       — failure

    Example:
        >>> letter, error = generate_cover_letter(
        ...     resume_text="I am a software engineer with 5 years...",
        ...     job_description="We are looking for a Senior SWE...",
        ...     company_name="Google Malaysia",
        ...     position_title="Senior Software Engineer"
        ... )
        >>> if not error:
        ...     print(letter)
    """
    if not resume_text or not resume_text.strip():
        return None, "Resume text is required."
    
    if not job_description or not job_description.strip():
        return None, "Job description is required."
    
    # Build the prompt
    prompt = _build_cover_letter_prompt(
        resume_text=resume_text,
        job_description=job_description,
        company_name=company_name,
        position_title=position_title
    )
    
    # Call OpenAI
    cover_letter, error = _call_openai(prompt)
    if error:
        return None, error
    
    # Clean up the response
    cover_letter = _clean_cover_letter(cover_letter)
    
    if not cover_letter or len(cover_letter.strip()) < 100:
        return None, "Generated cover letter is too short. Please try again."
    
    return cover_letter, None


# ══════════════════════════════════════════════════════════════════════════════
# PROMPT BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def _build_cover_letter_prompt(
    resume_text: str,
    job_description: str,
    company_name: str = None,
    position_title: str = None,
) -> str:
    """
    Build the GPT prompt for cover letter generation.

    Creates a structured prompt that instructs GPT to:
    1. Analyze the resume and extract key qualifications
    2. Identify requirements from the job description
    3. Match resume experience to JD requirements
    4. Write a professional, tailored cover letter

    Args:
        resume_text:      User's CV text
        job_description:  Target job description
        company_name:     Company name (optional)
        position_title:   Position title (optional)

    Returns:
        str: Formatted prompt for GPT
    """
    # Truncate resume and JD to avoid token limits
    resume_preview = resume_text[:3000].strip()
    jd_preview = job_description[:2000].strip()
    
    # Handle company/position placeholders
    company = company_name if company_name else "[Company Name]"
    position = position_title if position_title else "[Position Title]"
    
    return f"""You are an expert career coach and professional cover letter writer.

Your task is to write a tailored, professional cover letter for a job application.

**JOB DETAILS:**
Company: {company}
Position: {position}

**JOB DESCRIPTION:**
{jd_preview}

**CANDIDATE'S RESUME:**
{resume_preview}

**INSTRUCTIONS:**
Write a professional cover letter that:

1. **Opening Paragraph:**
   - Express genuine interest in the specific role and company
   - Briefly mention 1-2 key qualifications that make you a strong fit
   - Be engaging and confident, not generic

2. **Body Paragraphs (2-3 paragraphs):**
   - Highlight relevant experience from the resume that matches job requirements
   - Use specific examples and achievements from the resume
   - Show how your skills address the company's needs mentioned in the JD
   - Demonstrate understanding of the role and company
   - Use quantifiable achievements where available in the resume

3. **Closing Paragraph:**
   - Express enthusiasm about the opportunity
   - Mention willingness to discuss qualifications further
   - Professional call to action

**CRITICAL REQUIREMENTS:**
- Use ONLY information present in the candidate's resume — NEVER fabricate experience
- Match the tone to the industry (professional but not overly formal)
- Keep it concise: 3-4 paragraphs, approximately 250-350 words
- Use active voice and strong action verbs
- Avoid clichés like "I am writing to apply" or "To whom it may concern"
- DO NOT include placeholder brackets like [Company Name] — use the actual company name provided
- If company name is "[Company Name]", use "your esteemed organization" or "your company"
- End with "Sincerely," or "Best regards," followed by a blank line for signature

**OUTPUT FORMAT:**
Write ONLY the cover letter text. Do not include:
- Subject lines
- "Dear [Name]:" at the top (start directly with the salutation)
- Your name/address header
- Any meta-commentary or explanations

Start with the salutation and end with the closing.
"""


# ══════════════════════════════════════════════════════════════════════════════
# OPENAI CALLER
# ══════════════════════════════════════════════════════════════════════════════

def _call_openai(prompt: str) -> tuple:
    """
    Call OpenAI API to generate cover letter.

    Args:
        prompt: Formatted prompt with resume + JD + instructions

    Returns:
        (cover_letter_text, None) or (None, error_string)
    """
    try:
        client = _get_openai_client()
        
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            temperature=0.7,  # Balanced creativity and consistency
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert career coach and cover letter writer. "
                        "You write professional, tailored cover letters that highlight "
                        "the candidate's relevant experience and match job requirements. "
                        "You NEVER fabricate information not present in the resume."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        cover_letter = response.choices[0].message.content.strip()
        return cover_letter, None

    except Exception as e:
        error_msg = str(e)
        
        # Handle specific OpenAI errors
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


# ══════════════════════════════════════════════════════════════════════════════
# RESPONSE CLEANER
# ══════════════════════════════════════════════════════════════════════════════

def _clean_cover_letter(text: str) -> str:
    """
    Clean up the generated cover letter.

    Removes:
    - Markdown formatting (```text, **bold**, etc.)
    - Extra whitespace and blank lines
    - Meta-commentary that GPT sometimes adds

    Args:
        text: Raw GPT response

    Returns:
        str: Cleaned cover letter text
    """
    if not text:
        return ""
    
    # Remove markdown code blocks
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last line (backticks)
        text = "\n".join(lines[1:-1]).strip()
    
    # Remove markdown bold/italic
    text = text.replace("**", "")
    text = text.replace("__", "")
    text = text.replace("*", "")
    text = text.replace("_", "")
    
    # Remove excessive blank lines (max 1 blank line between paragraphs)
    lines = text.split("\n")
    cleaned_lines = []
    blank_count = 0
    
    for line in lines:
        if not line.strip():
            blank_count += 1
            if blank_count <= 1:
                cleaned_lines.append(line)
        else:
            blank_count = 0
            cleaned_lines.append(line)
    
    text = "\n".join(cleaned_lines)
    
    # Remove any leading/trailing whitespace
    text = text.strip()
    
    return text