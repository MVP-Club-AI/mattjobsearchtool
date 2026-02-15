"""
ATS detection module - identifies which ATS platform a company uses
by probing Greenhouse, Lever, and Ashby public APIs.

Also extracts candidate companies from LinkedIn data exports
(Saved Jobs + Company Follows) for ATS expansion.
"""

import csv
import logging
import re
from pathlib import Path

import httpx
from thefuzz import fuzz

logger = logging.getLogger(__name__)

# Timeout for ATS API probes (seconds)
PROBE_TIMEOUT = 8

# ATS API endpoint templates
ATS_ENDPOINTS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    "lever": "https://api.lever.co/v0/postings/{slug}",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{slug}",
}


def _company_to_slugs(company_name: str) -> list[str]:
    """Generate candidate board token slugs from a company name.

    Most ATS boards use a lowercase slug derived from the company name.
    We try several common patterns to maximize detection.

    Args:
        company_name: Raw company name (e.g., "Khan Academy", "hims & hers")

    Returns:
        Deduplicated list of slug candidates to try.
    """
    name = company_name.strip()

    # Strip common corporate suffixes
    for suffix in [
        ", Inc.", ", Inc", " Inc.", " Inc", " Corporation", " Corp.",
        " Corp", " LLC", " Ltd.", " Ltd", " Co.", " Co",
    ]:
        if name.lower().endswith(suffix.lower()):
            name = name[: -len(suffix)]

    # Normalize to lowercase, strip non-alphanumeric (keep spaces and hyphens)
    cleaned = re.sub(r"[^a-z0-9\s\-]", "", name.lower()).strip()

    slugs = []

    # "khan academy" -> "khanacademy"
    no_spaces = re.sub(r"\s+", "", cleaned)
    if no_spaces:
        slugs.append(no_spaces)

    # "khan academy" -> "khan-academy"
    hyphenated = re.sub(r"\s+", "-", cleaned)
    if hyphenated and hyphenated != no_spaces:
        slugs.append(hyphenated)

    # "khan academy" -> "khan_academy"
    underscored = re.sub(r"\s+", "_", cleaned)
    if underscored not in slugs:
        slugs.append(underscored)

    return slugs


def _extract_board_name(data: dict | list, platform: str) -> str | None:
    """Extract the board/company name from an ATS API response for verification.

    Args:
        data: Parsed JSON response from the ATS API.
        platform: The ATS platform name.

    Returns:
        The board name string if found, None otherwise.
    """
    if platform == "greenhouse" and isinstance(data, dict):
        # Greenhouse wraps jobs in {"jobs": [...], "meta": {"total": N}}
        # but the board name isn't in the jobs endpoint directly.
        # However, job entries include "location.name" and "departments"
        # but not the board name. We'll rely on slug match quality instead.
        return None
    if platform == "ashby" and isinstance(data, dict):
        # Ashby returns {"jobs": [...]} with each job having "organizationName"
        jobs = data.get("jobs", [])
        if jobs and isinstance(jobs[0], dict):
            return jobs[0].get("organizationName")
    if platform == "lever" and isinstance(data, list):
        # Lever returns a list of postings, each with a "categories.team" and company in "text"
        # No direct company name field. Rely on slug match quality.
        return None
    return None


def _verify_board_matches_company(
    company_name: str, slug: str, data: dict | list, platform: str
) -> bool:
    """Verify that a detected ATS board actually belongs to the target company.

    This prevents false positives where a generic slug like "community"
    matches an unrelated company's board.

    Args:
        company_name: The company we're looking for.
        slug: The slug that got a 200 response.
        data: The parsed JSON response.
        platform: The ATS platform.

    Returns:
        True if we're confident this board belongs to the company.
    """
    normalized_company = _normalize_company(company_name)

    # If the slug is the full normalized company name (no spaces), high confidence
    full_slug = re.sub(r"[^a-z0-9]", "", normalized_company)
    if slug == full_slug:
        return True

    # Check if Ashby response has an org name we can verify
    board_name = _extract_board_name(data, platform)
    if board_name:
        board_normalized = _normalize_company(board_name)
        if (
            fuzz.ratio(normalized_company, board_normalized) >= 70
            or fuzz.partial_ratio(normalized_company, board_normalized) >= 85
        ):
            return True
        else:
            logger.debug(
                "Board name mismatch for '%s': board says '%s' (slug: %s)",
                company_name,
                board_name,
                slug,
            )
            return False

    # For Greenhouse/Lever where we can't extract a board name,
    # only trust slugs that contain most of the company name
    # (e.g., "khanacademy" for "Khan Academy" is fine,
    #  but "education" for "Education First Consulting" is not)
    slug_ratio = fuzz.ratio(full_slug, slug)
    if slug_ratio >= 80:
        return True

    # Check if slug is a substring match that's substantial enough
    if len(slug) >= 5 and slug in full_slug:
        return True

    logger.debug(
        "Low confidence slug match for '%s': slug='%s' vs full='%s' (ratio=%d)",
        company_name,
        slug,
        full_slug,
        slug_ratio,
    )
    return False


def _detect_workday(company_name: str, client: httpx.Client) -> dict | None:
    """Detect if a company uses Workday and discover their board configuration.

    Workday career sites live at:
      https://{subdomain}.wd{N}.myworkdayjobs.com/wday/cxs/{subdomain}/{board}/jobs

    The subdomain is derived from the company name, the wd number varies
    (wd1 and wd5 are most common), and the board path is unpredictable
    but follows common patterns we can try.

    Args:
        company_name: The company name to look up.
        client: httpx.Client instance to use for requests.

    Returns:
        Dict with {"ats": "workday", "board_token": "{subdomain}:{wd}:{board}"}
        if found, None otherwise. The board_token encodes all three parts
        needed to construct the API URL.
    """
    slugs = _company_to_slugs(company_name)
    wd_versions = ["wd5", "wd1"]

    # Common board path patterns (most to least common)
    for slug in slugs:
        # Workday subdomains must be valid hostnames (max 63 chars)
        if len(slug) > 40:
            continue

        board_candidates = [
            slug,                                          # "nvidia"
            f"{slug}ExternalCareerSite",                   # "nvidiaExternalCareerSite"
            f"{slug}-careers",                             # "zoom-careers"
            f"{slug}careers",                              # "zoomcareers"
            "External",                                    # Generic
            "Careers",                                     # Generic
            "external_experienced",                        # Adobe pattern
            f"{slug}_Careers",                             # "zoom_Careers"
        ]

        # Try each wd version x board combination directly.
        # The subdomain 406 check is unreliable (all wd versions return 406
        # for any company because they share infrastructure).
        for wd in wd_versions:
            for board in board_candidates:
                url = (
                    f"https://{slug}.{wd}.myworkdayjobs.com"
                    f"/wday/cxs/{slug}/{board}/jobs"
                )
                try:
                    resp = client.post(
                        url,
                        json={"limit": 1, "offset": 0, "appliedFacets": {}},
                        headers={"Content-Type": "application/json"},
                    )
                    if resp.status_code == 200:
                        try:
                            data = resp.json()
                        except Exception:
                            continue
                        if "jobPostings" in data or "total" in data:
                            token = f"{slug}:{wd}:{board}"
                            logger.info(
                                "Detected workday for '%s' (token: %s)",
                                company_name,
                                token,
                            )
                            return {"ats": "workday", "board_token": token}
                except (httpx.TimeoutException, httpx.HTTPError, UnicodeError):
                    continue

    return None


def detect_ats(company_name: str) -> dict | None:
    """Detect which ATS platform a company uses by probing public APIs.

    Tries Greenhouse, Lever, Ashby, and Workday. Validates that detected
    boards actually belong to the target company to prevent false positives.

    Args:
        company_name: The company name to look up.

    Returns:
        Dict with {"ats": platform, "board_token": token} if found,
        None if no ATS detected.
    """
    slugs = _company_to_slugs(company_name)
    logger.info("Probing ATS for '%s' with slugs: %s", company_name, slugs)

    with httpx.Client(timeout=PROBE_TIMEOUT, follow_redirects=True) as client:
        # Try Greenhouse, Lever, Ashby first (simpler APIs)
        for slug in slugs:
            for platform, url_template in ATS_ENDPOINTS.items():
                url = url_template.format(slug=slug)
                try:
                    resp = client.get(url)
                    if resp.status_code == 200:
                        try:
                            data = resp.json()
                        except Exception:
                            continue

                        has_jobs = isinstance(data, list) or (
                            isinstance(data, dict)
                            and ("jobs" in data or "postings" in data)
                        )
                        if not has_jobs:
                            continue

                        if not _verify_board_matches_company(
                            company_name, slug, data, platform
                        ):
                            continue

                        logger.info(
                            "Detected %s for '%s' (slug: %s)",
                            platform,
                            company_name,
                            slug,
                        )
                        return {"ats": platform, "board_token": slug}

                except httpx.TimeoutException:
                    logger.debug("Timeout probing %s for slug '%s'", platform, slug)
                except httpx.HTTPError as e:
                    logger.debug("HTTP error probing %s for slug '%s': %s", platform, slug, e)

        # Try Workday (POST-based, different URL structure)
        workday_result = _detect_workday(company_name, client)
        if workday_result:
            return workday_result

    logger.info("No ATS detected for '%s'", company_name)
    return None


def _normalize_company(name: str) -> str:
    """Normalize a company name for deduplication."""
    normalized = name.strip().lower()
    for suffix in [
        ", inc.", ", inc", " inc.", " inc", " corporation",
        " corp.", " corp", " llc", " ltd.", " ltd", " co.",
    ]:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
    return normalized.strip()


def extract_candidate_companies(
    linkedin_data_dir: str, existing_companies: list[str]
) -> list[str]:
    """Extract companies from LinkedIn data that aren't already monitored.

    Parses Saved Jobs CSV and Company Follows CSV to find unique companies,
    then filters out those already in the ATS config.

    Args:
        linkedin_data_dir: Path to the LinkedIn data export directory.
        existing_companies: List of company names already in ats_companies.json.

    Returns:
        Sorted list of new company name candidates.
    """
    data_dir = Path(linkedin_data_dir)
    companies_found: dict[str, str] = {}  # normalized -> original display name

    # Parse Saved Jobs
    saved_jobs_path = data_dir / "Jobs" / "Saved Jobs.csv"
    if saved_jobs_path.exists():
        with open(saved_jobs_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                company = row.get("Company Name", "").strip()
                if company:
                    norm = _normalize_company(company)
                    if norm and norm not in companies_found:
                        companies_found[norm] = company
        logger.info("Found %d companies from Saved Jobs", len(companies_found))

    # Parse Company Follows
    follows_path = data_dir / "Company Follows.csv"
    if follows_path.exists():
        with open(follows_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                org = row.get("Organization", "").strip()
                if org:
                    norm = _normalize_company(org)
                    if norm and norm not in companies_found:
                        companies_found[norm] = org
        logger.info(
            "Total unique companies after adding Follows: %d", len(companies_found)
        )

    # Filter out already-monitored companies
    existing_normalized = {_normalize_company(c) for c in existing_companies}
    new_companies = {
        norm: display
        for norm, display in companies_found.items()
        if norm not in existing_normalized
    }

    logger.info(
        "%d new companies found (%d already monitored)",
        len(new_companies),
        len(companies_found) - len(new_companies),
    )

    return sorted(new_companies.values(), key=str.lower)
