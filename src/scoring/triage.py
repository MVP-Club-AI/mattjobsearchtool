"""Fast keyword-based triage filter.

Scores jobs 0-10 based on title and description keyword matches
to filter out obviously irrelevant roles before sending to Claude
for full semantic scoring. Costs nothing, runs in milliseconds.
"""

import re
import logging

logger = logging.getLogger(__name__)

# High-signal title keywords -- these strongly suggest alignment.
# Weighted 2x when found in title.
_TITLE_KEYWORDS = [
    # Core domain -- these are Matthew's wheelhouse (3 pts each)
    "ai enablement",
    "ai adoption",
    "ai training",
    "ai transformation",
    "ai change management",
    "ai coaching",
    "ai academy",
    "ai literacy",
    "learning design",
    "learning experience",
    "learning architect",
    "learning product",
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
    "change management",
    "workforce transformation",
    "center of excellence",
    "customer education",
]

# Description keywords -- indicate relevant content in the job description.
_DESCRIPTION_KEYWORDS = [
    "ai enablement",
    "ai adoption",
    "ai tools",
    "ai training",
    "ai literacy",
    "ai transformation",
    "generative ai",
    "large language model",
    "llm",
    "prompt engineering",
    "change management",
    "learning design",
    "learning experience",
    "instructional design",
    "curriculum development",
    "workshop",
    "enablement",
    "upskill",
    "reskill",
    "training program",
    "learning management",
    "product management",
    "edtech",
    "education technology",
    "adult learning",
    "hands-on",
    "coaching",
]

# Hard-reject title patterns -- if the title matches these, score 0
# regardless of description content. These are roles that never fit.
_REJECT_PATTERNS = [
    r"\bsoftware engineer",
    r"\bsre\b",
    r"\bdevops\b",
    r"\bdata scientist\b",
    r"\bml engineer",
    r"\bmachine learning engineer",
    r"\bbackend engineer",
    r"\bfrontend engineer",
    r"\bfull.?stack engineer",
    r"\bplatform engineer",
    r"\binfrastructure engineer",
    r"\bsecurity engineer",
    r"\bqa engineer",
    r"\bnurse\b",
    r"\bphysician\b",
    r"\bpharmacist\b",
    r"\bdentist\b",
    r"\baccountant\b",
    r"\bauditor\b",
    r"\blawyer\b",
    r"\blegal counsel",
    r"\bparalegal\b",
    r"\btax\b.*\b(manager|analyst|director)",
    r"\bsales rep",
    r"\baccount executive\b",
    r"\b[bs]dr\b",
    r"\brecruiter\b",
    r"\breal estate\b",
    r"\bmechanic\b",
    r"\belectrician\b",
    r"\bplumber\b",
    r"\bwarehouse\b",
    r"\bdriver\b",
    r"\bcashier\b",
    r"\bcustomer service rep",
]

_REJECT_RE = [re.compile(p, re.IGNORECASE) for p in _REJECT_PATTERNS]

# ---------------------------------------------------------------------------
# Location filter -- hard criteria: Remote or Denver/Front Range only
# ---------------------------------------------------------------------------

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

    Jobs with no location info pass (benefit of the doubt).
    """
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


def triage_batch(jobs: list[dict], min_score: int = 1) -> list[dict]:
    """Score and filter a batch of jobs, returning those above min_score.

    Jobs are returned sorted by triage score descending so the most
    promising candidates get scored first by Claude.

    Each job dict gets a 'triage_score' field added.
    """
    results = []
    rejected = 0
    location_rejected = 0

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

        results.append(job)

    results.sort(key=lambda j: j["triage_score"], reverse=True)

    logger.info(
        "Triage complete: %d passed (min_score=%d), %d keyword-rejected, "
        "%d location-rejected out of %d total",
        len(results), min_score, rejected, location_rejected, len(jobs),
    )

    return results
