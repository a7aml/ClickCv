"""
services/job_service.py

Fetches jobs from JSearch API (RapidAPI) based on user's industry major
and selected country. Caches results in Redis for 1 hour per major+country+page
combination so different country selections are cached independently.

Change from original:
  - fetch_jobs() now accepts an optional country parameter
  - country is appended to the JSearch query for location filtering
  - cache key includes country so results are cached per country
"""

import os
import json
import logging
import requests

logger = logging.getLogger(__name__)

JSEARCH_HOST = "jsearch.p.rapidapi.com"
JSEARCH_URL  = "https://jsearch.p.rapidapi.com/search"
CACHE_TTL    = 3600   # 1 hour

# Map ClickCV majors to JSearch query terms
MAJOR_QUERIES = {
    "technology":  "software engineer developer",
    "medical":     "doctor nurse medical healthcare",
    "engineering": "civil mechanical electrical engineer",
    "financial":   "finance accounting analyst banker",
    "marketing":   "marketing digital media brand manager",
}

# Supported countries — matches the frontend dropdown
# Value is the string passed to JSearch location param
SUPPORTED_COUNTRIES = {
    "any":          None,
    "malaysia":     "Malaysia",
    "singapore":    "Singapore",
    "united_states":"United States",
    "united_kingdom":"United Kingdom",
    "australia":    "Australia",
    "canada":       "Canada",
    "uae":          "United Arab Emirates",
    "germany":      "Germany",
    "netherlands":  "Netherlands",
    "sweden":       "Sweden",
    "switzerland":  "Switzerland",
    "france":       "France",
    "india":        "India",
    "japan":        "Japan",
    "south_korea":  "South Korea",
    "saudi_arabia": "Saudi Arabia",
    "qatar":        "Qatar",
    "new_zealand":  "New Zealand",
    "ireland":      "Ireland",
    "denmark":      "Denmark",
}


def fetch_jobs(
    major:    str,
    page:     int = 1,
    num_pages:int = 1,
    country:  str = "any",
) -> tuple:
    """
    Fetch jobs from JSearch API for a given major and country.

    Args:
        major:     industry major string e.g. 'technology'
        page:      page number (default 1)
        num_pages: number of pages to fetch (default 1 = ~10 jobs)
        country:   country key from SUPPORTED_COUNTRIES (default 'any')

    Returns:
        (jobs_list, None) or ([], error_string)
    """
    api_key = os.environ.get("JSEARCH_API_KEY")
    if not api_key:
        return [], "JSearch API key not configured."

    # Normalise country key
    country_key      = (country or "any").lower().strip().replace(" ", "_")
    country_location = SUPPORTED_COUNTRIES.get(country_key)  # None = no filter

    # Base query from major
    base_query = MAJOR_QUERIES.get(major.lower(), major)

    # Append country to query string for stronger location signal
    # JSearch uses both query text and location param together
    if country_location:
        query = f"{base_query} in {country_location}"
    else:
        query = base_query

    # Check cache first
    cached = _get_cached_jobs(major, country_key, page)
    if cached:
        logger.info(f"Jobs cache HIT major={major} country={country_key} page={page}")
        return cached, None

    try:
        params = {
            "query":     query,
            "page":      page,
            "num_pages": num_pages,
            "date_posted": "all",
        }

        # Add location filter if a specific country was selected
        if country_location:
            params["location"] = country_location

        response = requests.get(
            JSEARCH_URL,
            headers={
                "X-RapidAPI-Key":  api_key,
                "X-RapidAPI-Host": JSEARCH_HOST,
                "Content-Type":    "application/json",
            },
            params=params,
            timeout=10,
        )

        if response.status_code != 200:
            logger.error(f"JSearch API error: {response.status_code} {response.text}")
            return [], f"Jobs API returned status {response.status_code}."

        data = response.json()
        raw  = data.get("data", [])
        jobs = [_normalize_job(j) for j in raw]
        jobs = [j for j in jobs if j]   # filter None

        # Cache results
        _cache_jobs(major, country_key, page, jobs)

        logger.info(
            f"Fetched {len(jobs)} jobs "
            f"major={major} country={country_key} page={page}"
        )
        return jobs, None

    except requests.Timeout:
        return [], "Jobs API timed out. Please try again."
    except Exception as e:
        logger.error(f"JSearch fetch error: {e}")
        return [], "Failed to fetch jobs. Please try again."


def _normalize_job(raw: dict) -> dict | None:
    """
    Normalize a JSearch job object into a consistent structure.
    Returns None if essential fields are missing.
    """
    if not raw:
        return None

    title       = raw.get("job_title", "")
    company     = raw.get("employer_name", "")
    description = raw.get("job_description", "")
    location    = raw.get("job_city") or raw.get("job_country") or "Remote"
    url         = raw.get("job_apply_link") or raw.get("job_google_link", "")
    salary_min  = raw.get("job_min_salary")
    salary_max  = raw.get("job_max_salary")
    salary_curr = raw.get("job_salary_currency", "USD")
    posted_at   = raw.get("job_posted_at_datetime_utc", "")
    job_type    = raw.get("job_employment_type", "")
    is_remote   = raw.get("job_is_remote", False)
    job_id      = raw.get("job_id", "")

    if not title or not description:
        return None

    salary = None
    if salary_min and salary_max:
        salary = f"{salary_curr} {salary_min:,.0f} – {salary_max:,.0f}"
    elif salary_min:
        salary = f"{salary_curr} {salary_min:,.0f}+"

    return {
        "job_id":           job_id,
        "title":            title,
        "company":          company,
        "location":         "Remote" if is_remote else location,
        "description":      description[:3000],
        "full_description": description,
        "url":              url,
        "salary":           salary,
        "job_type":         job_type,
        "posted_at":        posted_at[:10] if posted_at else "",
        "is_remote":        is_remote,
    }


# ── Cache helpers ─────────────────────────────────────────────────────────────

def _get_cached_jobs(major: str, country: str, page: int) -> list | None:
    """Try to get cached job results from Redis."""
    try:
        from app.services.analysis_cache import _get_redis
        r = _get_redis()
        if not r:
            return None
        key  = f"jobs:{major}:{country}:{page}"
        data = r.get(key)
        return json.loads(data) if data else None
    except Exception:
        return None


def _cache_jobs(major: str, country: str, page: int, jobs: list):
    """Cache job results in Redis for 1 hour."""
    try:
        from app.services.analysis_cache import _get_redis
        r = _get_redis()
        if not r:
            return
        key = f"jobs:{major}:{country}:{page}"
        r.setex(key, CACHE_TTL, json.dumps(jobs))
    except Exception:
        pass