"""
tests/test_analysis_pipeline.py

End-to-end integration test for the full analysis pipeline.
Tests the complete flow: upload → run → retrieve → history

Run from project root:
    python tests/test_analysis_pipeline.py

Requirements:
    - Flask server running on localhost:5000
    - A valid user account (set EMAIL + PASSWORD below)
    - A real PDF or DOCX CV file (set CV_FILE_PATH below)
"""

import sys
import os
import json
import requests

# ── Configuration — edit these before running ─────────────────────────────────
BASE_URL     = "http://localhost:5000"
EMAIL        = "your@email.com"       # ← your registered account email
PASSWORD     = "yourpassword"         # ← your password
CV_FILE_PATH = "tests/sample_cv.pdf"  # ← path to a real PDF or DOCX CV file
MAJOR        = "technology"
JOB_DESCRIPTION = """
We are looking for a Software Engineer with experience in:
- Python and Flask framework
- PostgreSQL database
- AWS cloud services
- Docker and Kubernetes
- REST API development
- Git version control
- Agile methodology
"""


# ── Test runner ───────────────────────────────────────────────────────────────

def run_tests():
    print("Running analysis pipeline integration tests...\n")
    passed = 0
    failed = 0
    token     = None
    resume_id = None
    analysis_id = None

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

    # ── Step 0 — Login to get JWT token ───────────────────────────────────────
    print("── Step 0: Authentication ─────────────────────────")

    try:
        login_resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": EMAIL, "password": PASSWORD},
            timeout=10
        )
    except requests.exceptions.ConnectionError:
        print(f"  FAIL  Cannot connect to Flask server at {BASE_URL}")
        print(f"        Make sure your Flask app is running: flask run")
        return

    check("Login returns 200",
          login_resp.status_code == 200,
          f"got {login_resp.status_code}: {login_resp.text[:100]}")

    if login_resp.status_code != 200:
        print("\n  Cannot continue without a valid token.")
        return

    token = login_resp.json().get("access_token")
    check("Login returns JWT token",
          token is not None,
          f"response: {login_resp.json()}")

    headers = {"Authorization": f"Bearer {token}"}
    print(f"  Token: {token[:30]}...")

    # ── Step 1 — Upload CV ────────────────────────────────────────────────────
    print("\n── Step 1: Upload CV ──────────────────────────────")

    # Check CV file exists
    if not os.path.exists(CV_FILE_PATH):
        print(f"  FAIL  CV file not found at: {CV_FILE_PATH}")
        print(f"        Create a sample CV file at that path and try again.")
        print(f"        You can use any real PDF or DOCX resume.")
        failed += 1
    else:
        with open(CV_FILE_PATH, "rb") as f:
            ext = CV_FILE_PATH.rsplit(".", 1)[-1].lower()
            mime = "application/pdf" if ext == "pdf" \
                   else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

            upload_resp = requests.post(
                f"{BASE_URL}/analysis/upload",
                headers=headers,
                files={"file": (os.path.basename(CV_FILE_PATH), f, mime)},
                data={
                    "major": MAJOR,
                    "job_description": JOB_DESCRIPTION
                },
                timeout=30
            )

        check("Upload returns 201",
              upload_resp.status_code == 201,
              f"got {upload_resp.status_code}: {upload_resp.text[:200]}")

        if upload_resp.status_code == 201:
            upload_data = upload_resp.json()
            resume_id   = upload_data.get("resume_id")

            check("Upload returns resume_id",
                  resume_id is not None,
                  f"response: {upload_data}")

            check("Upload returns original filename",
                  "original_filename" in upload_data)

            check("Upload returns major",
                  upload_data.get("major") == MAJOR)

            print(f"  resume_id: {resume_id}")
            print(f"  filename:  {upload_data.get('original_filename')}")

    # ── Step 1b — Upload validation tests ─────────────────────────────────────
    print("\n── Step 1b: Upload validation ─────────────────────")

    # Test: no file
    resp = requests.post(
        f"{BASE_URL}/analysis/upload",
        headers=headers,
        data={"major": MAJOR},
        timeout=10
    )
    check("Upload without file returns 400",
          resp.status_code == 400,
          f"got {resp.status_code}")

    # Test: no major
    if os.path.exists(CV_FILE_PATH):
        with open(CV_FILE_PATH, "rb") as f:
            resp = requests.post(
                f"{BASE_URL}/analysis/upload",
                headers=headers,
                files={"file": (os.path.basename(CV_FILE_PATH), f, "application/pdf")},
                timeout=10
            )
        check("Upload without major returns 400",
              resp.status_code == 400,
              f"got {resp.status_code}")

    # Test: no auth
    resp = requests.post(f"{BASE_URL}/analysis/upload", timeout=10)
    check("Upload without token returns 401",
          resp.status_code == 401,
          f"got {resp.status_code}")

    # Test: wrong file type
    resp = requests.post(
        f"{BASE_URL}/analysis/upload",
        headers=headers,
        files={"file": ("resume.txt", b"fake content", "text/plain")},
        data={"major": MAJOR},
        timeout=10
    )
    check("Upload with .txt file returns 400",
          resp.status_code == 400,
          f"got {resp.status_code}")

    # ── Step 2 — Run analysis ─────────────────────────────────────────────────
    print("\n── Step 2: Run analysis ───────────────────────────")

    if resume_id is None:
        print("  SKIP  resume_id not available — skipping run tests")
    else:
        print("  (Running full pipeline: extract → NLP → score → LLM...)")
        print("  (This may take 15-30 seconds...)\n")

        run_resp = requests.post(
            f"{BASE_URL}/analysis/run",
            headers=headers,
            json={
                "resume_id":       resume_id,
                "major":           MAJOR,
                "job_description": JOB_DESCRIPTION
            },
            timeout=120    # Long timeout — LLM call can take time
        )

        check("Run returns 200",
              run_resp.status_code == 200,
              f"got {run_resp.status_code}: {run_resp.text[:300]}")

        if run_resp.status_code == 200:
            result = run_resp.json()
            analysis_id = result.get("analysis_id")

            # ── Score checks ──────────────────────────────────────────────────
            check("Result has analysis_id",
                  analysis_id is not None)

            check("Result has overall_score",
                  "overall_score" in result,
                  f"keys: {list(result.keys())}")

            overall = result.get("overall_score", 0)
            check("Overall score is between 0 and 100",
                  0 <= overall <= 100,
                  f"got: {overall}")

            check("Result has score_band",
                  result.get("score_band") in ["strong", "good", "borderline", "weak"],
                  f"got: {result.get('score_band')}")

            # ── Individual criterion scores ───────────────────────────────────
            scores = result.get("scores", {})
            expected_criteria = [
                "keyword_score", "keyword_placement_score",
                "formatting_score", "structure_score",
                "experience_recency_score", "achievements_score",
                "job_title_score", "education_score",
                "resume_length_score", "contact_info_score"
            ]
            check("Result has all 10 criterion scores",
                  all(k in scores for k in expected_criteria),
                  f"missing: {[k for k in expected_criteria if k not in scores]}")

            all_valid_scores = all(
                isinstance(scores.get(k), (int, float)) and 0 <= scores.get(k, -1) <= 100
                for k in expected_criteria
            )
            check("All criterion scores are 0-100",
                  all_valid_scores,
                  f"scores: {scores}")

            # ── Gaps ──────────────────────────────────────────────────────────
            check("Result has missing_sections list",
                  isinstance(result.get("missing_sections"), list))

            check("Result has missing_keywords list",
                  isinstance(result.get("missing_keywords"), list))

            check("Result has detected_sections list",
                  isinstance(result.get("detected_sections"), list) and
                  len(result.get("detected_sections", [])) > 0,
                  f"got: {result.get('detected_sections')}")

            # ── LLM recommendations ───────────────────────────────────────────
            recs = result.get("recommendations")
            check("Result has recommendations",
                  recs is not None)

            if recs and "sections" in recs:
                check("Recommendations has sections list",
                      isinstance(recs["sections"], list) and
                      len(recs["sections"]) > 0)

                check("Recommendations has summary_message",
                      isinstance(recs.get("summary_message"), str) and
                      len(recs.get("summary_message", "")) > 10)

                check("Recommendations has quick_wins",
                      isinstance(recs.get("quick_wins"), list))

                if recs["sections"]:
                    first = recs["sections"][0]
                    check("First recommendation has required fields",
                          all(k in first for k in
                              ["section", "priority", "issue",
                               "recommendation", "rewrite_example"]),
                          f"got keys: {list(first.keys())}")

            # ── Print summary ─────────────────────────────────────────────────
            print(f"\n  Overall Score:    {overall} / 100  ({result.get('score_band').upper()})")
            print(f"  Used JD:          {result.get('used_jd')}")
            print(f"  Detected Sections: {result.get('detected_sections')}")
            print(f"  Missing Sections: {result.get('missing_sections')}")
            print(f"  Missing Keywords: {result.get('missing_keywords', [])[:5]}")
            if recs:
                print(f"  LLM Summary:      {recs.get('summary_message', '')[:100]}...")
                print(f"  Recommendations:  {len(recs.get('sections', []))} sections")
                print(f"  Quick Wins:")
                for qw in recs.get("quick_wins", []):
                    print(f"    • {qw}")

    # ── Step 3 — Get analysis by ID ───────────────────────────────────────────
    print("\n── Step 3: Get analysis by ID ─────────────────────")

    if analysis_id is None:
        print("  SKIP  analysis_id not available")
    else:
        get_resp = requests.get(
            f"{BASE_URL}/analysis/{analysis_id}",
            headers=headers,
            timeout=10
        )

        check("GET /analysis/<id> returns 200",
              get_resp.status_code == 200,
              f"got {get_resp.status_code}: {get_resp.text[:100]}")

        if get_resp.status_code == 200:
            data = get_resp.json()

            check("GET response has analysis_id",
                  data.get("analysis_id") == analysis_id)

            check("GET response has scores dict",
                  isinstance(data.get("scores"), dict))

            check("GET response has sections list",
                  isinstance(data.get("sections"), list))

            check("GET response has recommendations list",
                  isinstance(data.get("recommendations"), list))

        # Test: wrong user cannot access another user's analysis
        resp = requests.get(
            f"{BASE_URL}/analysis/99999",
            headers=headers,
            timeout=10
        )
        check("GET non-existent analysis returns 404",
              resp.status_code == 404,
              f"got {resp.status_code}")

    # ── Step 4 — Get history ──────────────────────────────────────────────────
    print("\n── Step 4: Get history ────────────────────────────")

    hist_resp = requests.get(
        f"{BASE_URL}/analysis/history",
        headers=headers,
        timeout=10
    )

    check("GET /analysis/history returns 200",
          hist_resp.status_code == 200,
          f"got {hist_resp.status_code}")

    if hist_resp.status_code == 200:
        hist = hist_resp.json()

        check("History has analyses list",
              isinstance(hist.get("analyses"), list))

        check("History has total count",
              isinstance(hist.get("total"), int))

        if hist.get("analyses"):
            first = hist["analyses"][0]
            check("History item has required fields",
                  all(k in first for k in
                      ["analysis_id", "resume_id", "major",
                       "overall_score", "created_at"]))

        print(f"  Total analyses in history: {hist.get('total')}")

    # ── Step 5 — DB verification reminder ────────────────────────────────────
    print("\n── Step 5: Database verification (manual) ─────────")
    if analysis_id:
        print(f"  Check pgAdmin for analysis_id = {analysis_id}:")
        print(f"  ✓ resume_analyses  — should have 1 row with overall_score")
        print(f"  ✓ ats_results      — should have 10 criterion scores")
        print(f"  ✓ resume_sections  — should have 1 row per detected section")
        print(f"  ✓ recommendations  — should have rows from LLM output")
        print(f"  ✓ resumes          — raw_text should be populated")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'─' * 50}")
    print(f"{passed} passed — {failed} failed")

    if failed == 0:
        print("\n  Full pipeline is working end-to-end.")
    else:
        print("\n  Some tests failed — check the details above.")


if __name__ == "__main__":
    run_tests()