"""
tests/test_llm_service.py

Tests for services/llm_service.py

Run from project root:
    python tests/test_llm_service.py

Requires OPENAI_API_KEY in .env file.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.nlp_service      import detect_sections, extract_keywords_per_section
from app.services.scoring_service  import calculate_ats_score
from app.services.llm_service      import generate_recommendations


# ── Sample CV ─────────────────────────────────────────────────────────────────

TECH_CV = """John Smith
john@email.com | +60123456789 | LinkedIn: linkedin.com/in/johnsmith

SUMMARY
Software engineer with 4 years experience building web applications
using Python and Flask.

EXPERIENCE
Software Engineer — Startup XYZ
2020 - 2023
Built REST APIs using Flask and SQLAlchemy.
Deployed applications on AWS.

EDUCATION
BSc Computer Science — MIT — 2020

SKILLS
Python, Flask, PostgreSQL, Git

CERTIFICATIONS
AWS Certified Developer — 2022
"""

TECH_JD = """
Senior Software Engineer role requiring:
Python, Flask, PostgreSQL, Docker, Kubernetes, AWS, Redis,
REST APIs, microservices, CI/CD, Git, Agile methodology.
Preferred: React, machine learning experience.
"""


# ── Test runner ───────────────────────────────────────────────────────────────

def run_tests():
    print("Running llm_service tests...\n")
    passed = 0
    failed = 0

    def check(label, condition, detail=""):
        nonlocal passed, failed
        if condition:
            print(f"  PASS  {label}")
            passed += 1
        else:
            print(f"  FAIL  {label}")
            if detail:
                print(f"        {detail}")
            failed += 1

    # ── Build pipeline inputs ─────────────────────────────────────────────────
    print("── Building pipeline inputs...")
    sections, _   = detect_sections(TECH_CV)
    placement, _  = extract_keywords_per_section(sections or {})
    scoring, _    = calculate_ats_score(
        TECH_CV, sections or {}, placement or {},
        "technology", job_description=TECH_JD
    )

    check("Pipeline inputs built successfully",
          sections is not None and scoring is not None)

    if not sections or not scoring:
        print("\nCannot proceed — pipeline input failed.")
        return

    print(f"  CV score: {scoring['overall_score']} ({scoring['score_band']})")

    # ── Input validation ──────────────────────────────────────────────────────
    print("\n── Input validation ───────────────────────────────")

    result, error = generate_recommendations(
        {}, scoring, "technology"
    )
    check("Empty sections returns error",
          result is None and error is not None)

    result, error = generate_recommendations(
        sections, None, "technology"
    )
    check("Empty scoring returns error",
          result is None and error is not None)

    # ── Real API call — without JD ────────────────────────────────────────────
    print("\n── Real API call without JD ───────────────────────")
    print("  (Calling OpenAI API...)")

    result, error = generate_recommendations(
        sections, scoring, "technology"
    )

    check("API call returns result",
          result is not None, f"error: {error}")

    if result:
        # Structure checks
        check("Result has overall_score",
              "overall_score" in result)

        check("Result has score_band",
              "score_band" in result and
              result["score_band"] in ["strong","good","borderline","weak"])

        check("Result has summary_message",
              "summary_message" in result and
              len(result.get("summary_message","")) > 10)

        check("Result has sections list",
              "sections" in result and
              isinstance(result["sections"], list))

        check("Result has quick_wins",
              "quick_wins" in result and
              isinstance(result["quick_wins"], list))

        check("Result has top_keywords_to_add",
              "top_keywords_to_add" in result and
              isinstance(result["top_keywords_to_add"], list))

        # Section recommendation structure
        if result["sections"]:
            first = result["sections"][0]
            check("Section has 'section' key",
                  "section" in first)
            check("Section has 'issue' key",
                  "issue" in first)
            check("Section has 'recommendation' key",
                  "recommendation" in first)
            check("Section has 'priority' key",
                  "priority" in first and first["priority"] in [1, 2, 3])
            check("Section has 'rewrite_example' key",
                  "rewrite_example" in first)

        # Print full result for visual inspection
        print(f"\n  Summary: {result['summary_message'][:120]}...")
        print(f"\n  Recommendations ({len(result['sections'])} sections):")
        for s in result["sections"]:
            print(f"    [{s.get('section')}] P{s.get('priority')} — {s.get('issue','')[:60]}")
        print(f"\n  Quick wins:")
        for qw in result.get("quick_wins", []):
            print(f"    • {qw}")
        print(f"\n  Keywords to add: {result.get('top_keywords_to_add', [])}")

    # ── Real API call — with JD ───────────────────────────────────────────────
    print("\n── Real API call with JD ──────────────────────────")
    print("  (Calling OpenAI API with job description...)")

    scoring_jd, _ = calculate_ats_score(
        TECH_CV, sections, placement or {},
        "technology", job_description=TECH_JD
    )

    result_jd, error = generate_recommendations(
        sections, scoring_jd, "technology",
        job_description=TECH_JD
    )

    check("API call with JD returns result",
          result_jd is not None, f"error: {error}")

    if result_jd:
        check("With JD — used_jd is True",
              result_jd.get("used_jd") == True)

        check("With JD — has missing keywords",
              len(result_jd.get("missing_keywords", [])) > 0)

        print(f"\n  With JD summary: {result_jd.get('summary_message','')[:120]}...")
        print(f"  Missing keywords: {result_jd.get('missing_keywords', [])[:6]}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{passed} passed — {failed} failed")


if __name__ == "__main__":
    run_tests()