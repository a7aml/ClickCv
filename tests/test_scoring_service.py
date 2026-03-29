"""
tests/test_scoring_service.py

Tests for services/scoring_service.py

Run from project root:
    python tests/test_scoring_service.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.nlp_service import detect_sections, extract_keywords_per_section
from app.services.scoring_service import calculate_ats_score, get_score_interpretation


# ── Sample resumes ────────────────────────────────────────────────────────────

STRONG_CV = """John Smith
john@email.com | +60123456789 | LinkedIn: linkedin.com/in/johnsmith
Kuala Lumpur, Malaysia

SUMMARY
Senior software engineer with 6 years building scalable web applications
using Python, Flask, PostgreSQL and AWS. Led teams of 5+ engineers.

EXPERIENCE
Senior Software Engineer — Google
2021 - Present
Developed microservices handling 10M daily requests using Python and Docker.
Reduced API response time by 40% through Redis caching optimization.
Led team of 6 engineers on the payments platform saving $2M annually.
Deployed 15+ services on AWS EC2, S3, and Lambda.

Software Engineer — Microsoft
2018 - 2021
Built REST APIs using Flask and SQLAlchemy serving 500K users.
Improved database query performance by 60% through PostgreSQL indexing.
Mentored team of 3 junior developers.

EDUCATION
BSc Computer Science
MIT — 2018
GPA 3.9 / 4.0

SKILLS
Python, Flask, PostgreSQL, Docker, AWS, Redis, Git, REST APIs, Kubernetes

CERTIFICATIONS
AWS Certified Solutions Architect — 2022
Google Cloud Professional Developer — 2023

PROJECTS
ClickCV — AI Resume Analyzer
Built full-stack web application using Flask and React.
Integrated OpenAI API serving 10,000 users monthly.

LANGUAGES
English (Native), Arabic (Fluent)

ACHIEVEMENTS
Dean's List — MIT 2017, 2018
Best Employee Award — Google 2022
Top 1% engineer ranking — 2023
"""

WEAK_CV = """bob wilson
bob@email.com

EXPERIENCE
Developer somewhere
Did some coding stuff.

EDUCATION
Some degree
"""

MEDIUM_CV = """Alice Brown
alice@email.com | +60198765432

SUMMARY
Project manager with 4 years experience managing software teams.

EXPERIENCE
Project Manager — Tech Corp
2020 - 2023
Managed projects and teams.
Delivered 5 projects on time.

EDUCATION
MBA — University of Malaya — 2020

SKILLS
Project Management, Agile, Scrum, JIRA

CERTIFICATIONS
PMP Certified — 2021
"""

TECH_JD = """
We are looking for a Senior Software Engineer with experience in:
- Python and Flask framework
- PostgreSQL database design
- AWS cloud services (EC2, S3, Lambda)
- Docker and Kubernetes
- REST API development
- Redis caching
- Git version control
- Agile development methodology
Preferred: React, microservices, CI/CD pipelines
"""


# ── Test runner ───────────────────────────────────────────────────────────────

def run_tests():
    print("Running scoring_service tests...\n")
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

    # ── Helper: build scoring inputs ──────────────────────────────────────────
    def build_inputs(cv_text):
        sections, _ = detect_sections(cv_text)
        placement, _ = extract_keywords_per_section(sections or {})
        return sections or {}, placement or {}

    # ── Failure cases ─────────────────────────────────────────────────────────
    print("── Input validation ───────────────────────────────")

    result, error = calculate_ats_score("", {}, {}, "technology")
    check("Empty text returns error", result is None and error is not None)

    result, error = calculate_ats_score("some text", {}, {}, "technology")
    check("Empty sections returns error", result is None and error is not None)

    # ── Strong CV — no JD ─────────────────────────────────────────────────────
    print("\n── Strong CV without JD ───────────────────────────")
    print("  (Running KeyBERT — may take a few seconds...)")

    sections, placement = build_inputs(STRONG_CV)
    result, error = calculate_ats_score(
        STRONG_CV, sections, placement, "technology"
    )

    check("Strong CV returns result", result is not None,
          f"error: {error}")

    if result:
        check("Strong CV — overall score is float",
              isinstance(result["overall_score"], float))

        check("Strong CV — score in 0-100 range",
              0 <= result["overall_score"] <= 100,
              f"got: {result['overall_score']}")

        check("Strong CV — scores above weak threshold (>50)",
              result["overall_score"] > 50,
              f"got: {result['overall_score']}")

        check("Strong CV — has all 10 criterion scores",
              all(k in result for k in [
                  "keyword_score", "keyword_placement_score",
                  "formatting_score", "structure_score",
                  "experience_recency_score", "achievements_score",
                  "job_title_score", "education_score",
                  "resume_length_score", "contact_info_score"
              ]))

        check("Strong CV — has missing_sections list",
              "missing_sections" in result and isinstance(result["missing_sections"], list))

        check("Strong CV — has missing_keywords list",
              "missing_keywords" in result and isinstance(result["missing_keywords"], list))

        check("Strong CV — has score_band",
              result.get("score_band") in ["strong", "good", "borderline", "weak"],
              f"got: {result.get('score_band')}")

        check("Strong CV — used_jd is False (no JD provided)",
              result.get("used_jd") == False)

        # Strong CV should score well on experience recency (Present role)
        check("Strong CV — recency score is 100 (current role)",
              result["experience_recency_score"] == 100.0,
              f"got: {result['experience_recency_score']}")

        # Strong CV should detect achievements
        check("Strong CV — achievements score > 20 (has metrics)",
              result["achievements_score"] > 20,
              f"got: {result['achievements_score']}")

        # Strong CV should score well on structure
        check("Strong CV — structure score > 50 (has all sections)",
              result["structure_score"] > 50,
              f"got: {result['structure_score']}")

        print(f"\n  Strong CV scores:")
        for k, v in result.items():
            if isinstance(v, float):
                print(f"    {k}: {v}")
        print(f"    band: {result['score_band']}")
        print(f"    missing_sections: {result['missing_sections']}")

    # ── Weak CV ───────────────────────────────────────────────────────────────
    print("\n── Weak CV without JD ─────────────────────────────")

    sections, placement = build_inputs(WEAK_CV)
    result, error = calculate_ats_score(
        WEAK_CV, sections, placement, "technology"
    )

    check("Weak CV returns result", result is not None)

    if result:
        check("Weak CV — scores lower than strong CV",
              result["overall_score"] < 70,
              f"got: {result['overall_score']}")

        check("Weak CV — has missing sections detected",
              len(result["missing_sections"]) > 0,
              f"missing: {result['missing_sections']}")

        print(f"\n  Weak CV overall score: {result['overall_score']}")
        print(f"  Missing sections: {result['missing_sections']}")

    # ── Strong CV WITH job description ────────────────────────────────────────
    print("\n── Strong CV with JD ──────────────────────────────")

    sections, placement = build_inputs(STRONG_CV)
    result_with_jd, error = calculate_ats_score(
        STRONG_CV, sections, placement, "technology",
        job_description=TECH_JD
    )

    check("Strong CV with JD returns result",
          result_with_jd is not None, f"error: {error}")

    if result_with_jd:
        check("With JD — used_jd is True",
              result_with_jd.get("used_jd") == True)

        check("With JD — keyword score > 0",
              result_with_jd["keyword_score"] > 0,
              f"got: {result_with_jd['keyword_score']}")

        print(f"\n  With JD — keyword score: {result_with_jd['keyword_score']}")
        print(f"  With JD — overall score: {result_with_jd['overall_score']}")
        print(f"  Missing keywords: {result_with_jd['missing_keywords'][:5]}")

    # ── Score interpretation ──────────────────────────────────────────────────
    print("\n── Score interpretation ───────────────────────────")

    for score, expected_band in [(80, "strong"), (70, "good"),
                                  (55, "borderline"), (30, "weak")]:
        interp = get_score_interpretation(score)
        check(f"Score {score} → band '{expected_band}'",
              interp["band"] == expected_band,
              f"got: {interp['band']}")

    for score in [80, 70, 55, 30]:
        interp = get_score_interpretation(score)
        check(f"Score {score} → has llm_action",
              "llm_action" in interp and interp["llm_action"] in [
                  "polishing", "targeted_fixes",
                  "major_rewrites", "full_restructure"
              ])

    # ── Invalid major falls back to technology ────────────────────────────────
    print("\n── Edge cases ─────────────────────────────────────")

    sections, placement = build_inputs(MEDIUM_CV)
    result, error = calculate_ats_score(
        MEDIUM_CV, sections, placement, "invalid_major"
    )
    check("Invalid major falls back gracefully",
          result is not None, f"error: {error}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{passed} passed — {failed} failed")


if __name__ == "__main__":
    run_tests()