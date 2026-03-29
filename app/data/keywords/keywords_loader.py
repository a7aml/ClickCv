"""
data/keywords/keywords_loader.py

Loads ATS keyword databases from JSON files and provides
a clean interface for the scoring service.

Design decisions:
    - JSON files are the single source of truth for keywords
    - Loader validates structure on first load and raises clearly
    - In-memory cache avoids re-reading files on every API call
    - Fallback to empty lists (not crash) if a file is missing
    - Adding a new industry = drop a new JSON file, zero code change
    - Adding keywords = edit JSON only, never touch scoring logic

Usage:
    from app.data.keywords.keywords_loader import get_keywords

    required, preferred = get_keywords("technology")
    required, preferred = get_keywords("medical")
"""

import os
import json
import logging

logger = logging.getLogger(__name__)

# ── Path to the JSON keyword files ───────────────────────────────────
# __file__ = app/data/keywords/keywords_loader.py
# KEYWORDS_DIR = app/data/keywords/
KEYWORDS_DIR = os.path.dirname(os.path.abspath(__file__))

# ── In-memory cache — populated on first call per industry ───────────
_cache: dict = {}

# ── Valid industries ─────────────────────────────────────────────────
SUPPORTED_INDUSTRIES = {
    "technology", "medical", "engineering", "financial", "marketing"
}


def get_keywords(industry: str) -> tuple:
    """
    Return (required_keywords, preferred_keywords) for the given industry.

    Loads from JSON on first call, then serves from memory cache.
    Falls back to empty lists if the file is missing or malformed —
    the scoring algorithm will use neutral scores rather than crashing.

    Args:
        industry: lowercase industry string e.g. 'technology'

    Returns:
        (required: list[str], preferred: list[str])
    """
    industry = (industry or "technology").lower().strip()

    if industry not in SUPPORTED_INDUSTRIES:
        logger.warning(f"Unknown industry '{industry}' — falling back to 'technology'")
        industry = "technology"

    # Serve from cache if already loaded
    if industry in _cache:
        data = _cache[industry]
        return data["required"], data["preferred"]

    # Load from JSON file
    json_path = os.path.join(KEYWORDS_DIR, f"{industry}.json")

    if not os.path.exists(json_path):
        logger.error(f"Keyword file not found: {json_path}")
        return [], []

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Validate structure
        required  = _validate_list(data.get("required",  []), industry, "required")
        preferred = _validate_list(data.get("preferred", []), industry, "preferred")

        # Store in cache
        _cache[industry] = {"required": required, "preferred": preferred}

        logger.info(
            f"Loaded {industry} keywords: "
            f"{len(required)} required, {len(preferred)} preferred"
        )
        return required, preferred

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {json_path}: {e}")
        return [], []
    except Exception as e:
        logger.error(f"Failed to load {json_path}: {e}")
        return [], []


def get_all_industries() -> list:
    """Return list of all supported industry names."""
    return sorted(SUPPORTED_INDUSTRIES)


def reload_cache() -> None:
    """
    Clear the in-memory cache so next call re-reads from disk.
    Useful in development when you edit JSON files without restarting.
    """
    global _cache
    _cache = {}
    logger.info("Keyword cache cleared — will reload from disk on next call.")


def validate_all() -> dict:
    """
    Load and validate all industry keyword files.
    Returns a report dict — useful for startup health checks.

    Returns:
        {
            "technology": {"required": 75, "preferred": 167, "status": "ok"},
            "medical":    {"required": 55, "preferred": 119, "status": "ok"},
            ...
        }
    """
    report = {}
    for industry in SUPPORTED_INDUSTRIES:
        required, preferred = get_keywords(industry)
        report[industry] = {
            "required":  len(required),
            "preferred": len(preferred),
            "status":    "ok" if required else "missing",
        }
    return report


# ── Private helpers ───────────────────────────────────────────────────

def _validate_list(items, industry: str, list_name: str) -> list:
    """
    Ensure keyword list contains only non-empty strings.
    Logs warnings for bad entries and filters them out.
    """
    if not isinstance(items, list):
        logger.warning(f"{industry}/{list_name} is not a list — using empty list")
        return []

    clean = []
    for item in items:
        if not isinstance(item, str):
            logger.warning(f"{industry}/{list_name}: non-string entry skipped: {item!r}")
            continue
        stripped = item.strip().lower()
        if not stripped:
            continue
        clean.append(stripped)

    return clean