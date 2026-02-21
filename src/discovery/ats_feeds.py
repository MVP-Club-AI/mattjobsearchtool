"""ATS Feeds Discovery Module.

Polls Greenhouse, Lever, and Ashby public APIs for job postings
at monitored companies.
"""

import json
import logging
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# Titles containing any of these terms are excluded outright.
_EXCLUDE_TERMS = [
    "software engineer",
    "backend engineer",
    "frontend engineer",
    "devops",
    "sre",
    "site reliability",
    "data scientist",
    "ml engineer",
    "machine learning engineer",
    "accountant",
    "financial analyst",
    "fp&a",
    "lawyer",
    "legal counsel",
    "counsel",
    "sales representative",
    "sales specialist",
    "sales director",
    "account executive",
    "account manager",
    "bdr",
    "sdr",
    "nurse",
    "physician",
    "pharmacist",
    "security engineer",
    "infrastructure engineer",
    "database administrator",
    "qa engineer",
    "test engineer",
    "presales",
    "pre-sales",
    "solutions engineer",
    "solution engineer",
    "solutions architect",
    "solution architect",
    "technical account manager",
    "support engineer",
    "support expert",
    "support specialist",
    "game design",
    "game director",
    "level designer",
    "noc ",
    "network operations",
    "firmware",
    "hardware",
    "mechanical engineer",
    "electrical engineer",
    "tax ",
    "audit",
    "compliance",
    "regulatory",
    "recruiter",
    "talent acquisition",
    "channel ",
    "partner manager",
    "partnership",
    "marketing manager",
    "marketing specialist",
    "growth marketing",
    "lifecycle marketing",
    "demand gen",
    "creative director",
    "graphic design",
    "visual design",
    "art director",
    "animator",
    "warehouse",
    "driver",
    "cashier",
    "real estate",
    "plumber",
    "electrician",
    "mechanic",
]

# Titles containing any of these terms are explicitly included.
# Only titles matching at least one include term will pass through.
_INCLUDE_TERMS = [
    # Core function: learning/training design
    "learn",
    "train",
    "education",
    "instructional",
    "curriculum",
    "content architect",
    "content design",
    "academy",
    "l&d",
    "workshop",
    # AI context
    "ai ",
    " ai",
    "artificial intelligence",
    # Enablement and adoption
    "enablement",
    "adoption",
    "literacy",
    "upskill",
    "reskill",
    "workforce",
    "center of excellence",
    "transformation",
    "change management",
    # Adjacent
    "product manager",
    "product design",
    "program manager",
    "coach",
]


class ATSFeeds:
    """Discover job postings from Greenhouse, Lever, Ashby, and Workday public boards."""

    def __init__(self, settings: dict, state_manager):
        self._settings = settings
        self._state_manager = state_manager

        base_dir = Path(__file__).resolve().parent.parent.parent
        config_path = base_dir / "config" / "ats_companies.json"

        with open(config_path, "r", encoding="utf-8") as fh:
            self._config = json.load(fh)

        self._companies: list[dict] = self._config.get("companies", [])
        self._max_age_hours = self._settings.get("hours_old", 72)

    # ------------------------------------------------------------------
    # Recency filter
    # ------------------------------------------------------------------

    def _is_recent(self, date_value) -> bool:
        """Check if a posting date is within the configured max age.

        Handles ISO strings, epoch milliseconds, and epoch seconds.
        Returns True if the date can't be parsed (benefit of the doubt).
        """
        if not date_value:
            return True  # No date available, let it through

        cutoff = datetime.now(timezone.utc) - timedelta(hours=self._max_age_hours)

        try:
            if isinstance(date_value, (int, float)):
                # Lever uses epoch milliseconds
                if date_value > 1e12:
                    dt = datetime.fromtimestamp(date_value / 1000, tz=timezone.utc)
                else:
                    dt = datetime.fromtimestamp(date_value, tz=timezone.utc)
                return dt >= cutoff

            if isinstance(date_value, str):
                # Try ISO format (Greenhouse, Ashby)
                cleaned = date_value.replace("Z", "+00:00")
                dt = datetime.fromisoformat(cleaned)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt >= cutoff

        except (ValueError, TypeError, OSError):
            pass

        return True  # Can't parse, let it through

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def fetch_all(self) -> list[dict]:
        """Poll every configured ATS board and return a flat list of job dicts."""
        all_jobs: list[dict] = []

        with httpx.Client(timeout=30) as client:
            for company in self._companies:
                ats = company.get("ats", "")
                board_token = company.get("board_token")
                company_name = company.get("name", "unknown")

                if ats == "custom" or not board_token:
                    continue

                fetch_method = {
                    "greenhouse": self._fetch_greenhouse,
                    "lever": self._fetch_lever,
                    "ashby": self._fetch_ashby,
                    "workday": self._fetch_workday,
                }.get(ats)

                if fetch_method is None:
                    logger.warning(
                        "%s: unsupported ATS type '%s', skipping",
                        company_name,
                        ats,
                    )
                    continue

                try:
                    jobs = fetch_method(client, company_name, board_token)
                    all_jobs.extend(jobs)
                except Exception:
                    logger.exception(
                        "Error fetching jobs for %s (%s)", company_name, ats
                    )

                time.sleep(0.5)

        return all_jobs

    # ------------------------------------------------------------------
    # Per-ATS fetch methods
    # ------------------------------------------------------------------

    def _fetch_greenhouse(
        self, client: httpx.Client, company_name: str, board_token: str
    ) -> list[dict]:
        url = (
            f"https://boards-api.greenhouse.io/v1/boards/{board_token}"
            f"/jobs?content=true"
        )
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()

        jobs: list[dict] = []
        for job in data.get("jobs", []):
            title = job.get("title", "")
            if not self._title_might_be_relevant(title):
                continue

            updated_at = job.get("updated_at")
            if not self._is_recent(updated_at):
                continue

            job_url = job.get("absolute_url", "")
            if self._state_manager.is_seen(job_url):
                continue

            location_obj = job.get("location") or {}
            location = location_obj.get("name", "")

            jobs.append(
                _build_job_dict(
                    title=title,
                    company=company_name,
                    location=location,
                    url=job_url,
                    description=job.get("content", ""),
                    date_posted=updated_at,
                    source=f"ats:greenhouse:{company_name}",
                )
            )

        logger.info(
            "%s (greenhouse): found %d recent relevant jobs",
            company_name,
            len(jobs),
        )
        return jobs

    def _fetch_lever(
        self, client: httpx.Client, company_name: str, board_token: str
    ) -> list[dict]:
        url = f"https://api.lever.co/v0/postings/{board_token}"
        resp = client.get(url)
        resp.raise_for_status()
        postings = resp.json()

        jobs: list[dict] = []
        for posting in postings:
            title = posting.get("text", "")
            if not self._title_might_be_relevant(title):
                continue

            created_at = posting.get("createdAt")
            if not self._is_recent(created_at):
                continue

            job_url = posting.get("hostedUrl", "")
            if self._state_manager.is_seen(job_url):
                continue

            categories = posting.get("categories") or {}
            location = categories.get("location", "")
            description = posting.get("descriptionPlain") or posting.get(
                "description", ""
            )

            jobs.append(
                _build_job_dict(
                    title=title,
                    company=company_name,
                    location=location,
                    url=job_url,
                    description=description,
                    date_posted=created_at,
                    source=f"ats:lever:{company_name}",
                )
            )

        logger.info(
            "%s (lever): found %d recent relevant jobs",
            company_name,
            len(jobs),
        )
        return jobs

    def _fetch_ashby(
        self, client: httpx.Client, company_name: str, board_token: str
    ) -> list[dict]:
        url = (
            f"https://api.ashbyhq.com/posting-api/job-board/{board_token}"
            f"?includeCompensation=true"
        )
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()

        jobs: list[dict] = []
        for job in data.get("jobs", []):
            title = job.get("title", "")
            if not self._title_might_be_relevant(title):
                continue

            published_at = job.get("publishedAt")
            if not self._is_recent(published_at):
                continue

            job_url = job.get("jobUrl", "")
            if self._state_manager.is_seen(job_url):
                continue

            description = job.get("descriptionHtml") or job.get(
                "descriptionPlain", ""
            )
            compensation = job.get("compensationTierSummary")
            salary_min, salary_max = _parse_compensation(compensation)

            jobs.append(
                _build_job_dict(
                    title=title,
                    company=company_name,
                    location=job.get("location", ""),
                    url=job_url,
                    description=description,
                    date_posted=published_at,
                    source=f"ats:ashby:{company_name}",
                    salary_min=salary_min,
                    salary_max=salary_max,
                )
            )

        logger.info(
            "%s (ashby): found %d potentially relevant jobs",
            company_name,
            len(jobs),
        )
        return jobs

    def _fetch_workday(
        self, client: httpx.Client, company_name: str, board_token: str
    ) -> list[dict]:
        """Fetch jobs from a Workday CXS API.

        The board_token is formatted as "subdomain:wd_version:board_path"
        (e.g., "nvidia:wd5:nvidiaExternalCareerSite").

        Workday paginates via offset/limit and returns jobs as POST responses.
        We fetch up to 100 jobs per company to stay reasonable.
        """
        parts = board_token.split(":", 2)
        if len(parts) != 3:
            logger.error(
                "%s: invalid workday board_token format '%s' "
                "(expected 'subdomain:wd:board')",
                company_name,
                board_token,
            )
            return []

        subdomain, wd, board = parts
        base_url = (
            f"https://{subdomain}.{wd}.myworkdayjobs.com"
            f"/wday/cxs/{subdomain}/{board}/jobs"
        )

        jobs: list[dict] = []
        offset = 0
        limit = 20  # Workday's typical page size

        while offset < 100:  # Cap at 100 jobs per company
            try:
                resp = client.post(
                    base_url,
                    json={"limit": limit, "offset": offset, "appliedFacets": {}},
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
            except (httpx.HTTPError, Exception) as e:
                logger.error(
                    "%s (workday): error fetching page at offset %d: %s",
                    company_name,
                    offset,
                    e,
                )
                break

            postings = data.get("jobPostings", [])
            if not postings:
                break

            for posting in postings:
                title = posting.get("title", "")
                if not self._title_might_be_relevant(title):
                    continue

                external_path = posting.get("externalPath", "")
                if not external_path:
                    continue

                job_url = (
                    f"https://{subdomain}.{wd}.myworkdayjobs.com"
                    f"{external_path}"
                )

                if self._state_manager.is_seen(job_url):
                    continue

                # Workday "postedOn" is human-readable (e.g., "Posted Today",
                # "Posted 2 Days Ago"). Filter out old posts.
                posted_on = posting.get("postedOn", "")
                if not self._workday_is_recent(posted_on):
                    continue

                location = posting.get("locationsText", "")

                # Fetch full description from the detail endpoint
                detail_url = (
                    f"https://{subdomain}.{wd}.myworkdayjobs.com"
                    f"/wday/cxs/{subdomain}/{board}{external_path}"
                )
                description = ""
                try:
                    detail_resp = client.get(detail_url)
                    if detail_resp.status_code == 200:
                        detail = detail_resp.json()
                        info = detail.get("jobPostingInfo", {})
                        description = info.get("jobDescription", "")
                        if not location:
                            location = info.get("location", "")
                except (httpx.HTTPError, Exception):
                    pass  # Proceed with empty description

                jobs.append(
                    _build_job_dict(
                        title=title,
                        company=company_name,
                        location=location,
                        url=job_url,
                        description=description,
                        date_posted=None,
                        source=f"ats:workday:{company_name}",
                    )
                )

            total = data.get("total", 0)
            offset += limit
            if offset >= total:
                break

        logger.info(
            "%s (workday): found %d relevant jobs",
            company_name,
            len(jobs),
        )
        return jobs

    # ------------------------------------------------------------------
    # Workday recency filter
    # ------------------------------------------------------------------

    def _workday_is_recent(self, posted_on: str) -> bool:
        """Check if a Workday 'postedOn' string is within max age.

        Workday uses human-readable strings like "Posted Today",
        "Posted Yesterday", "Posted 2 Days Ago", "Posted 30+ Days Ago".
        """
        if not posted_on:
            return True  # No date, let it through

        lower = posted_on.lower()

        if "today" in lower or "yesterday" in lower:
            return True

        # "Posted 2 Days Ago", "Posted 5 Days Ago"
        import re

        days_match = re.search(r"(\d+)\+?\s*days?\s*ago", lower)
        if days_match:
            days = int(days_match.group(1))
            return days * 24 <= self._max_age_hours

        # "Posted 30+ Days Ago" — the + means "more than"
        if "30+" in lower:
            return False

        return True  # Can't parse, let it through

    # ------------------------------------------------------------------
    # Title pre-filter
    # ------------------------------------------------------------------

    @staticmethod
    def _title_might_be_relevant(title: str) -> bool:
        """Pre-filter to avoid sending irrelevant roles to Claude for scoring.

        A title must match at least one include term AND not match any
        exclude term. Titles matching neither list are rejected — this
        prevents generic roles (NOC Lead, Presales Engineer, Game Designer)
        from consuming scoring API calls.
        """
        lower = title.lower()

        for term in _EXCLUDE_TERMS:
            if term in lower:
                return False

        for term in _INCLUDE_TERMS:
            if term in lower:
                return True

        # No include matched — reject to avoid scoring noise.
        return False


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _build_job_dict(
    *,
    title: str,
    company: str,
    location: str,
    url: str,
    description: str,
    date_posted,
    source: str,
    salary_min: float | None = None,
    salary_max: float | None = None,
) -> dict:
    """Return a standardised job dict matching the JobSpy format."""
    is_remote = bool(location and "remote" in location.lower())

    return {
        "title": title,
        "company": company,
        "location": location,
        "url": url,
        "description": description,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "date_posted": date_posted,
        "is_remote": is_remote,
        "source": source,
        "query": "ats_feed",
    }


def _parse_compensation(summary: str | None) -> tuple[float | None, float | None]:
    """Best-effort extraction of min/max salary from an Ashby compensation string.

    Ashby compensation summaries are free-form (e.g. "$150,000 - $200,000 USD").
    This helper does a simple numeric extraction and returns the first two
    dollar figures found, or (None, None) if parsing fails.
    """
    if not summary:
        return None, None

    import re

    amounts = re.findall(r"[\$]?\s*([\d,]+(?:\.\d+)?)", summary)
    nums = []
    for raw in amounts:
        try:
            nums.append(float(raw.replace(",", "")))
        except ValueError:
            continue

    if len(nums) >= 2:
        return min(nums[0], nums[1]), max(nums[0], nums[1])
    if len(nums) == 1:
        return nums[0], nums[0]
    return None, None
