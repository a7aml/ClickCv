"""
tests/test_nlp_service.py

Tests for services/nlp_service.py
Covers: section detection, missing sections, keyword extraction,
        per-section keyword extraction with weights.

Run from project root:
    python tests/test_nlp_service.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.nlp_service import (
    detect_sections,
    get_missing_sections,
    extract_keywords,
    extract_keywords_per_section,
)


# ── Sample resume texts ───────────────────────────────────────────────────────

FULL_CV = """John Smith
john@email.com | +1234567890 | LinkedIn: linkedin.com/in/johnsmith

SUMMARY
Experienced software engineer with 5 years building scalable web applications
using Python, Flask, and PostgreSQL. Passionate about clean code and testing.

EXPERIENCE
Software Engineer — Google
2020 - 2023
Developed microservices handling 10M daily requests.
Reduced API response time by 40% through caching optimization.
Led a team of 5 engineers on the payments platform.

Junior Developer — Startup XYZ
2018 - 2020
Built REST APIs using Flask and SQLAlchemy.
Deployed applications on AWS EC2 and S3.

EDUCATION
BSc Computer Science
MIT — 2018
GPA 3.8 / 4.0

SKILLS
Python, Flask, PostgreSQL, Docker, AWS, Redis, Git, REST APIs

CERTIFICATIONS
AWS Certified Solutions Architect — 2022
Google Cloud Professional — 2023

PROJECTS
ClickCV — AI Resume Analyzer
Built a full-stack web application using Flask and React.
Integrated OpenAI API for intelligent recommendations.

LANGUAGES
English (Native), Arabic (Fluent)

ACHIEVEMENTS
Dean's List — MIT 2017, 2018
Best Employee Award — Google 2022
"""

ALTERNATIVE_HEADERS_CV = """Jane Doe
jane@email.com

PROFESSIONAL PROFILE
Data scientist with expertise in machine learning and statistical analysis.

EMPLOYMENT HISTORY
Data Scientist — Amazon
2021 - Present
Built recommendation systems using collaborative filtering.

ACADEMIC BACKGROUND
MSc Data Science — Stanford University — 2021

CORE COMPETENCIES
Python, TensorFlow, PyTorch, SQL, Tableau, R

PROFESSIONAL CERTIFICATIONS
TensorFlow Developer Certificate — 2022
"""

MINIMAL_CV = """Alice Brown
alice@email.com

EXPERIENCE
Project Manager — Tech Corp 2019-2024
Managed cross-functional teams of 12 people.

EDUCATION
MBA — Harvard Business School — 2019

SKILLS
Project Management, Agile, Scrum, JIRA, Stakeholder Management
"""

INCOMPLETE_CV = """Bob Wilson
bob@email.com

EXPERIENCE
Developer at Some Company 2020-2023
Wrote code and fixed bugs.
"""

TOO_SHORT_TEXT = "John Smith\njohn@email.com"
EMPTY_TEXT = ""


# ── Test runner ───────────────────────────────────────────────────────────────

def run_tests():
    print("Running nlp_service tests...\n")
    passed = 0
    failed = 0

    def check(label, result, error, expected_success,
              expected_contains=None, expected_error_contains=None):
        nonlocal passed, failed

        if expected_success and result is None:
            print(f"  FAIL  {label}")
            print(f"        expected result, got error: {error}")
            failed += 1
            return

        if not expected_success and error is None:
            print(f"  FAIL  {label}")
            print(f"        expected error, got result")
            failed += 1
            return

        if expected_contains:
            result_str = str(result or "").lower()
            if expected_contains.lower() not in result_str:
                print(f"  FAIL  {label}")
                print(f"        expected '{expected_contains}' in result")
                print(f"        got: {str(result)[:120]}")
                failed += 1
                return

        if expected_error_contains:
            if expected_error_contains.lower() not in (error or "").lower():
                print(f"  FAIL  {label}")
                print(f"        expected error '{expected_error_contains}'")
                print(f"        got: {error}")
                failed += 1
                return

        print(f"  PASS  {label}")
        passed += 1

    # ════════════════════════════════════════════════════
    # SECTION DETECTION TESTS (same as before)
    # ════════════════════════════════════════════════════
    print("── Section detection ──────────────────────────────")

    s, e = detect_sections(EMPTY_TEXT)
    check("Empty text returns error", s, e, False, expected_error_contains="No text")

    s, e = detect_sections(TOO_SHORT_TEXT)
    check("Too short text returns error", s, e, False)

    s, e = detect_sections(FULL_CV)
    for section in ["summary", "experience", "education", "skills",
                    "certifications", "projects", "languages", "achievements"]:
        found = section in (s or {})
        if found:
            print(f"  PASS  Full CV — detects {section}")
            passed += 1
        else:
            print(f"  FAIL  Full CV — missing {section}")
            print(f"        detected: {list((s or {}).keys())}")
            failed += 1

    if s:
        # Content checks
        for label, section, expected_word in [
            ("Experience contains job title", "experience", "Google"),
            ("Skills contains keyword",       "skills",     "Python"),
            ("Education contains institution", "education", "MIT"),
        ]:
            content = s.get(section, "")
            if expected_word in content:
                print(f"  PASS  {label}")
                passed += 1
            else:
                print(f"  FAIL  {label} — got: {content[:80]}")
                failed += 1

    s, e = detect_sections(ALTERNATIVE_HEADERS_CV)
    for alias, expected_section in [
        ("PROFESSIONAL PROFILE", "summary"),
        ("EMPLOYMENT HISTORY",   "experience"),
        ("ACADEMIC BACKGROUND",  "education"),
        ("CORE COMPETENCIES",    "skills"),
        ("PROFESSIONAL CERTIFICATIONS", "certifications"),
    ]:
        found = expected_section in (s or {})
        if found:
            print(f"  PASS  '{alias}' maps to '{expected_section}'")
            passed += 1
        else:
            print(f"  FAIL  '{alias}' did not map to '{expected_section}'")
            print(f"        detected: {list((s or {}).keys())}")
            failed += 1

    s, e = detect_sections(INCOMPLETE_CV)
    if s is not None:
        missing = get_missing_sections(s)
        for section, should_be_missing in [
            ("summary",    True),
            ("skills",     True),
            ("experience", False),
        ]:
            is_missing = section in missing
            if is_missing == should_be_missing:
                status = "correctly missing" if should_be_missing else "correctly present"
                print(f"  PASS  Missing sections — '{section}' {status}")
                passed += 1
            else:
                print(f"  FAIL  Missing sections — '{section}' unexpected result")
                print(f"        missing list: {missing}")
                failed += 1

    # ════════════════════════════════════════════════════
    # KEYWORD EXTRACTION TESTS
    # ════════════════════════════════════════════════════
    print("\n── Keyword extraction ─────────────────────────────")

    # Failure cases
    kw, e = extract_keywords("")
    check("Empty text returns error", kw, e, False, expected_error_contains="No text")

    kw, e = extract_keywords("Hi there")
    check("Too short text returns error", kw, e, False)

    # Full CV keyword extraction
    print("  (Loading KeyBERT model — first run may take ~10 seconds...)")
    kw, e = extract_keywords(FULL_CV, top_n=20)
    check("Full CV — returns keywords list", kw, e, True)

    if kw:
        if len(kw) > 0:
            print(f"  PASS  Keyword extraction — returned {len(kw)} keywords")
            passed += 1
        else:
            print("  FAIL  Keyword extraction — empty list returned")
            failed += 1

        # Check that at least some expected tech keywords are found
        kw_lower = [k.lower() for k in kw]
        found_any_tech = any(
            tech in " ".join(kw_lower)
            for tech in ["python", "flask", "aws", "postgresql", "docker", "api"]
        )
        if found_any_tech:
            print(f"  PASS  Keyword extraction — contains relevant tech keywords")
            print(f"        sample: {kw[:8]}")
            passed += 1
        else:
            print(f"  FAIL  Keyword extraction — no expected tech keywords found")
            print(f"        got: {kw[:10]}")
            failed += 1

        # Keywords should be strings
        all_strings = all(isinstance(k, str) for k in kw)
        if all_strings:
            print("  PASS  Keyword extraction — all items are strings")
            passed += 1
        else:
            print("  FAIL  Keyword extraction — non-string items found")
            failed += 1

        # No duplicates
        if len(kw) == len(set(kw)):
            print("  PASS  Keyword extraction — no duplicate keywords")
            passed += 1
        else:
            print("  FAIL  Keyword extraction — duplicate keywords found")
            failed += 1

    # ════════════════════════════════════════════════════
    # PER-SECTION KEYWORD EXTRACTION TESTS
    # ════════════════════════════════════════════════════
    print("\n── Per-section keyword extraction ─────────────────")

    sections, _ = detect_sections(FULL_CV)
    if sections:
        placement, e = extract_keywords_per_section(sections, top_n_per_section=10)
        check("Per-section extraction — returns result", placement, e, True)

        if placement:
            # Each entry should have keywords and weight
            all_valid = all(
                "keywords" in v and "weight" in v
                for v in placement.values()
            )
            if all_valid:
                print("  PASS  Per-section — all entries have keywords + weight")
                passed += 1
            else:
                print("  FAIL  Per-section — missing keywords or weight keys")
                failed += 1

            # Skills section should have weight 0.9
            if "skills" in placement:
                w = placement["skills"]["weight"]
                if w == 0.9:
                    print(f"  PASS  Per-section — skills weight is 0.9")
                    passed += 1
                else:
                    print(f"  FAIL  Per-section — skills weight expected 0.9, got {w}")
                    failed += 1

            # Summary section should have weight 1.0
            if "summary" in placement:
                w = placement["summary"]["weight"]
                if w == 1.0:
                    print(f"  PASS  Per-section — summary weight is 1.0")
                    passed += 1
                else:
                    print(f"  FAIL  Per-section — summary weight expected 1.0, got {w}")
                    failed += 1

            # Experience should have weight 0.7
            if "experience" in placement:
                w = placement["experience"]["weight"]
                if w == 0.7:
                    print(f"  PASS  Per-section — experience weight is 0.7")
                    passed += 1
                else:
                    print(f"  FAIL  Per-section — experience weight expected 0.7, got {w}")
                    failed += 1

    # Failure case
    placement, e = extract_keywords_per_section({})
    check("Empty sections returns error", placement, e, False)

    # ════════════════════════════════════════════════════
    # SUMMARY
    # ════════════════════════════════════════════════════
    print(f"\n{passed} passed — {failed} failed")

    # Visual inspection
    print("\n── Extracted keywords from FULL_CV (visual check) ──")
    kw, _ = extract_keywords(FULL_CV, top_n=15)
    if kw:
        print(f"  Top keywords: {kw}")

    print("\n── Per-section keywords (visual check) ──")
    sections, _ = detect_sections(FULL_CV)
    placement, _ = extract_keywords_per_section(sections, top_n_per_section=5)
    if placement:
        for section, data in placement.items():
            print(f"  [{section}] (weight={data['weight']}) → {data['keywords']}")


if __name__ == "__main__":
    run_tests()