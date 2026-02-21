"""Fast keyword-based triage filter.

Scores jobs 0-10 based on title and description keyword matches
to filter out obviously irrelevant roles before sending to Claude
for full semantic scoring. Costs nothing, runs in milliseconds.
"""

import re
import logging
from datetime import datetime, timedelta, timezone
from dateutil import parser as dateutil_parser

logger = logging.getLogger(__name__)

# High-signal title keywords -- these strongly suggest alignment.
# Weighted 2x when found in title.
_TITLE_KEYWORDS = [
    # Core domain -- learning/training design in AI context
    "ai enablement",
    "ai adoption",
    "ai training",
    "ai literacy",
    "ai academy",
    "ai coaching",
    "learning design",
    "learning experience",
    "learning architect",
    "learning product",
    "learning innovation",
    "content architect",
    "training content",
    "instructional design",
    "curriculum",
    "l&d",
    "learning and development",
    # Standalone boosters -- any title with these gets a baseline lift
    "learning",
    "education",
    "training",
    # Adjacent domain
    "enablement",
    "training manager",
    "training director",
    "product manager",
    "product design",
    "center of excellence",
    "customer education",
    "workforce transformation",
]

# Description keywords -- indicate relevant content in the job description.
_DESCRIPTION_KEYWORDS = [
    # AI context
    "ai enablement",
    "ai adoption",
    "ai tools",
    "ai training",
    "ai literacy",
    "ai academy",
    "generative ai",
    "large language model",
    "llm",
    "prompt engineering",
    # Learning/training design function
    "learning design",
    "learning experience",
    "instructional design",
    "curriculum development",
    "content architecture",
    "modular curriculum",
    "modular content",
    "learning pathways",
    "training program",
    "learning management",
    "adult learning",
    "experiential learning",
    # Delivery and coaching
    "workshop",
    "hands-on",
    "coaching",
    "train the trainer",
    "train-the-trainer",
    "champion enablement",
    "champion program",
    "champion network",
    # Enablement and adoption
    "enablement",
    "upskill",
    "reskill",
    "center of excellence",
    # Adjacent
    "product management",
    "edtech",
    "education technology",
    "change management",
]

# Hard-reject title patterns -- if the title matches these, score 0
# regardless of description content. These are roles that never fit.
_REJECT_PATTERNS = [
    # Engineering / technical
    r"\bsoftware engineer",
    r"\bsre\b",
    r"\bdevops\b",
    r"\bdata scientist\b",
    r"\bdata engineer",
    r"\bml engineer",
    r"\bmachine learning engineer",
    r"\bbackend engineer",
    r"\bfrontend engineer",
    r"\bfull.?stack engineer",
    r"\bplatform engineer",
    r"\binfrastructure engineer",
    r"\bsecurity engineer",
    r"\bqa engineer",
    r"\bsolutions architect",
    # Clinical / medical
    r"\bnurse\b",
    r"\b(rn|lpn|cna)\b",
    r"\bphysician\b",
    r"\bpharmacist\b",
    r"\bdentist\b",
    r"\btherapist\b",
    r"\bclinical\b",
    r"\bperioperative",
    r"\bsurgical\b",
    r"\bpatient\b",
    # Finance / legal / compliance
    r"\baccountant\b",
    r"\bauditor\b",
    r"\blawyer\b",
    r"\blegal counsel",
    r"\bparalegal\b",
    r"\btax\b.*\b(manager|analyst|director)",
    # Sales / BD
    r"\bsales rep",
    r"\bsales manager\b",
    r"\baccount executive\b",
    r"\b[bs]dr\b",
    # Recruiting
    r"\brecruiter\b",
    # Retail / food service / physical labor
    r"\bretail\b",
    r"\bkey holder",
    r"\bstore manager",
    r"\breal estate\b",
    r"\bmechanic\b",
    r"\belectrician\b",
    r"\bplumber\b",
    r"\bwarehouse\b",
    r"\bdriver\b",
    r"\bcashier\b",
    r"\bbarista\b",
    r"\bbartender\b",
    r"\bchef\b",
    r"\bcook\b",
    # Construction / maintenance / facilities
    r"\bconstruction\b",
    r"\bmaintenance\b",
    r"\bcustodial\b",
    r"\bjanitor",
    # Customer service / support
    r"\bcustomer service rep",
    r"\bcustomer service manager",
    # Marketing (non-learning)
    r"\bbrand marketing",
    r"\bpaid social\b",
    r"\bpaid media\b",
    r"\bperformance marketing",
    r"\bgrowth marketing",
    r"\bdemand gen",
    r"\bseo\b",
    r"\bsem\b",
    # Academic (non-instructional)
    r"\badvising specialist",
    r"\bacademic advis",
    # Other
    r"\bhair removal",
    r"\bveterinar",
]

_REJECT_RE = [re.compile(p, re.IGNORECASE) for p in _REJECT_PATTERNS]

# ---------------------------------------------------------------------------
# Description-based hard rejects -- catch jobs that require technical degrees
# the candidate doesn't have (CS, software engineering, data science, ML, etc.)
#
# These patterns look for degree-requirement language paired with technical
# field names. They won't fire on "experience with ML" or "knowledge of CS" —
# only on phrases like "BS in Computer Science required" or "Master's degree
# in Data Science or related field".
# ---------------------------------------------------------------------------

_TECHNICAL_FIELDS = (
    r"computer\s+science"
    r"|software\s+engineering"
    r"|data\s+science"
    r"|machine\s+learning"
    r"|artificial\s+intelligence"
    r"|electrical\s+engineering"
    r"|computer\s+engineering"
    r"|information\s+systems"
    r"|computational"
    r"|statistics"
    r"|mathematics"
)

# "BS/BA/MS/MA/PhD in [technical field]"
_DEGREE_ABBREV_RE = re.compile(
    r"\b(?:B\.?S\.?|B\.?A\.?|M\.?S\.?|M\.?A\.?|Ph\.?D\.?)\s+in\s+(?:" + _TECHNICAL_FIELDS + r")",
    re.IGNORECASE,
)

# "Bachelor's/Master's/Doctoral degree in [technical field]"
_DEGREE_FULL_RE = re.compile(
    r"\b(?:bachelor'?s?|master'?s?|doctoral|graduate)\s+(?:degree\s+)?in\s+(?:" + _TECHNICAL_FIELDS + r")",
    re.IGNORECASE,
)

# "degree in [technical field] required/preferred"
_DEGREE_GENERIC_RE = re.compile(
    r"\bdegree\s+in\s+(?:" + _TECHNICAL_FIELDS + r")",
    re.IGNORECASE,
)

_DESCRIPTION_DEGREE_REJECT_RES = [
    _DEGREE_ABBREV_RE,
    _DEGREE_FULL_RE,
    _DEGREE_GENERIC_RE,
]

# ---------------------------------------------------------------------------
# Location filter -- hard criteria: Remote or Denver/Front Range only
# Exception: Anthropic jobs always pass regardless of location.
# ---------------------------------------------------------------------------

_LOCATION_EXEMPT_COMPANIES = [
    "anthropic",
]

_ALLOWED_LOCATIONS = [
    "remote",
    "anywhere",
    "distributed",
    "work from home",
    "wfh",
    # Denver metro / Front Range
    "denver",
    "boulder",
    "colorado springs",
    "fort collins",
    "loveland",
    "longmont",
    "broomfield",
    "aurora",
    "lakewood",
    "arvada",
    "westminster",
    "thornton",
    "centennial",
    "littleton",
    "castle rock",
    "golden",
    "parker",
    "highlands ranch",
    "colorado",
    " co ",
    " co,",
    ", co",
]

_ALLOWED_LOCATION_RE = re.compile(
    r"\b("
    + "|".join(re.escape(loc) for loc in _ALLOWED_LOCATIONS)
    + r")\b",
    re.IGNORECASE,
)

# Also match state abbreviation patterns like "Denver, CO" or "CO, USA"
_CO_ABBREV_RE = re.compile(r"\bCO\b")


def passes_location_filter(job: dict) -> bool:
    """Return True if the job is remote or in the Denver/Front Range area.

    Exception: Companies in _LOCATION_EXEMPT_COMPANIES always pass.
    Jobs with no location info pass (benefit of the doubt).
    """
    # Exception: exempt companies pass regardless of location
    company = (job.get("company") or "").strip().lower()
    for exempt in _LOCATION_EXEMPT_COMPANIES:
        if exempt in company:
            return True

    location = (job.get("location") or "").strip()
    if not location:
        return True

    lower = location.lower()

    # Check allowed location terms
    for term in _ALLOWED_LOCATIONS:
        if term in lower:
            return True

    # Check for CO state abbreviation (case-sensitive to avoid false positives)
    if _CO_ABBREV_RE.search(location):
        return True

    # Also check is_remote flag if set
    if job.get("is_remote"):
        return True

    return False


def triage_score(job: dict) -> int:
    """Score a job 0-10 based on keyword relevance.

    Returns:
        0: Hard-rejected (obviously irrelevant title)
        1-3: Low relevance (few keyword matches)
        4-6: Moderate relevance (some signals)
        7-10: High relevance (strong keyword alignment)
    """
    title = (job.get("title") or "").lower()
    description = (job.get("description") or "").lower()

    # Hard reject
    for pattern in _REJECT_RE:
        if pattern.search(title):
            return 0

    score = 0

    # Title keyword matches (high weight)
    for kw in _TITLE_KEYWORDS:
        if kw in title:
            score += 2

    # Description keyword matches (lower weight)
    desc_hits = 0
    for kw in _DESCRIPTION_KEYWORDS:
        if kw in description:
            desc_hits += 1

    # Cap description contribution at 4 points
    score += min(desc_hits, 4)

    # Bonus: "AI" in title is a good signal even without other keywords
    if re.search(r"\bai\b", title):
        score += 1

    # Bonus: manager/director/lead seniority in title
    if re.search(r"\b(manager|director|head of|lead|vp)\b", title):
        score += 1

    return min(score, 10)


def _requires_technical_degree(job: dict) -> bool:
    """Return True if the job description requires a technical degree.

    Catches hard requirements for CS, software engineering, data science,
    ML, AI engineering, or similar degrees that the candidate doesn't have.
    """
    description = (job.get("description") or "")
    if not description:
        return False
    for pattern in _DESCRIPTION_DEGREE_REJECT_RES:
        if pattern.search(description):
            return True
    return False


def _is_too_old(job: dict, max_age_hours: int) -> bool:
    """Return True if the job posting is older than max_age_hours.

    Parses date_posted from various formats (ISO 8601, human-readable, etc.)
    and compares against the cutoff. Jobs with no parseable date from
    external search sources (searchapi) are treated as potentially stale
    and rejected, since we can't verify their freshness. Jobs from ATS
    feeds and JobSpy with no date pass (those sources already filter by age).
    """
    date_str = job.get("date_posted")
    source = (job.get("source") or "")

    if not date_str or str(date_str).lower() in ("none", "nat", "nan", ""):
        # ATS and JobSpy already filter by age at discovery time, so
        # missing dates from those sources are fine. But Google search
        # results with no date are suspect — reject them.
        if "searchapi" in source or "serper" in source:
            return True
        return False

    try:
        posted = dateutil_parser.parse(str(date_str), fuzzy=True)
        # Make timezone-aware if naive
        if posted.tzinfo is None:
            posted = posted.replace(tzinfo=timezone.utc)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        return posted < cutoff
    except (ValueError, OverflowError):
        # Unparseable date from search sources — reject as stale
        if "searchapi" in source or "serper" in source:
            return True
        return False


def triage_batch(jobs: list[dict], min_score: int = 1,
                 max_age_hours: int = 0) -> list[dict]:
    """Score and filter a batch of jobs, returning those above min_score.

    Jobs are returned sorted by triage score descending so the most
    promising candidates get scored first by Claude.

    Each job dict gets a 'triage_score' field added.

    Args:
        max_age_hours: If > 0, reject jobs posted more than this many
            hours ago. Search-sourced jobs with no date are also rejected.
    """
    results = []
    rejected = 0
    location_rejected = 0
    degree_rejected = 0
    age_rejected = 0

    for job in jobs:
        score = triage_score(job)
        job["triage_score"] = score

        if score < min_score:
            rejected += 1
            continue

        if not passes_location_filter(job):
            location_rejected += 1
            job["triage_score"] = 0  # Mark as rejected for downstream tracking
            continue

        if _requires_technical_degree(job):
            degree_rejected += 1
            job["triage_score"] = 0
            continue

        if max_age_hours > 0 and _is_too_old(job, max_age_hours):
            age_rejected += 1
            job["triage_score"] = 0
            continue

        results.append(job)

    results.sort(key=lambda j: j["triage_score"], reverse=True)

    logger.info(
        "Triage complete: %d passed (min_score=%d), %d keyword-rejected, "
        "%d location-rejected, %d degree-rejected, %d age-rejected "
        "out of %d total",
        len(results), min_score, rejected, location_rejected,
        degree_rejected, age_rejected, len(jobs),
    )

    return results
