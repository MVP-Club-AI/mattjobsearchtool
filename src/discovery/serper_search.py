"""
Google Search discovery module via SearchAPI.io.

Uses the SearchAPI.io API to search Google for job postings,
targeting niche boards and career pages that JobSpy might miss.
"""

import logging
import time
import urllib.parse

import httpx

logger = logging.getLogger(__name__)

SEARCH_QUERIES = [
    '"AI enablement" OR "AI adoption" manager job remote -linkedin.com -indeed.com',
    '"learning architect" AI remote job posting 2026',
    '"director of AI training" OR "head of AI academy" job',
    'site:greenhouse.io "AI enablement" OR "learning" manager',
    'site:lever.co "AI" "learning" manager',
    '"AI change management" lead OR manager job remote',
    '"workforce AI" OR "AI coaching" job posting',
    'AgTech OR agriculture "AI training" OR "AI enablement" job',
    'robotics company "learning" OR "training" manager job',
    '"center of excellence" AI enablement job posting',
]

_JOB_INDICATORS = [
    "/jobs/",
    "/careers/",
    "/positions/",
    "/job/",
    "/apply/",
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "workday.com",
    "posting",
    "apply now",
    "we're hiring",
    "job description",
    "we are looking for",
    "qualifications",
    "responsibilities",
]


class SerperSearch:
    """Searches Google via SearchAPI.io for job postings on niche boards and career pages."""

    def __init__(self, settings: dict, state_manager):
        self.api_key = settings.get("serper_api_key") or ""
        self.state_manager = state_manager

    def search_all(self) -> list[dict]:
        """Execute all search queries and return a combined list of job dicts."""
        if not self.api_key:
            logger.info("Search API key not configured; skipping Google search discovery")
            return []

        all_jobs: list[dict] = []
        total = len(SEARCH_QUERIES)

        with httpx.Client(timeout=30) as client:
            for i, query in enumerate(SEARCH_QUERIES, start=1):
                try:
                    response = client.get(
                        "https://www.searchapi.io/api/v1/search",
                        params={
                            "engine": "google",
                            "q": query,
                            "api_key": self.api_key,
                            "num": 20,
                            "tbs": "qdr:d3",  # Google: past 3 days
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                    jobs = self._parse_results(data, query)
                    all_jobs.extend(jobs)
                    logger.info(
                        "Search query %d/%d: '%s' - found %d job-like results",
                        i, total, query[:60], len(jobs),
                    )
                except Exception:
                    logger.warning(
                        "Search query %d/%d: '%s' failed",
                        i, total, query[:60], exc_info=True,
                    )

                if i < total:
                    time.sleep(1)

        logger.info("Google search discovery complete: %d total results", len(all_jobs))
        return all_jobs

    def _parse_results(self, data: dict, query: str) -> list[dict]:
        """Extract job-like entries from SearchAPI.io organic results."""
        jobs: list[dict] = []

        for result in data.get("organic_results", []):
            url = result.get("link", "")
            if not url:
                continue

            if self.state_manager.is_seen(url):
                continue

            title = result.get("title", "")
            snippet = result.get("snippet", "")

            if not self._looks_like_job(url, title, snippet):
                continue

            job = {
                "title": title,
                "company": self._extract_company(url, result),
                "location": "",
                "url": url,
                "description": snippet,
                "source": "searchapi",
                "query": query,
                "date_posted": result.get("date", None),
                "salary_min": None,
                "salary_max": None,
                "is_remote": None,
                "description_quality": "snippet",
            }
            jobs.append(job)

        return jobs

    @staticmethod
    def _looks_like_job(url: str, title: str, snippet: str) -> bool:
        """Heuristic check: does this result look like a job posting?"""
        combined = f"{url} {title} {snippet}".lower()
        return any(indicator in combined for indicator in _JOB_INDICATORS)

    @staticmethod
    def _extract_company(url: str, result: dict) -> str:
        """Best-effort company name extraction from URL or title."""
        parsed = urllib.parse.urlparse(url)
        hostname = parsed.netloc.lower()
        path = parsed.path.lower()

        # ATS board URLs: boards.greenhouse.io/anthropic, jobs.lever.co/openai
        ats_hosts = ["boards.greenhouse.io", "jobs.lever.co", "jobs.ashbyhq.com"]
        for ats in ats_hosts:
            if hostname == ats:
                segments = [s for s in path.split("/") if s]
                if segments:
                    return segments[0]

        # Title often formatted as "Job Title - Company Name" or "Job Title | Company Name"
        title = result.get("title", "")
        for sep in [" - ", " | ", " at ", " — "]:
            if sep in title:
                parts = title.split(sep)
                company = parts[-1].strip()
                if company:
                    return company

        # Fallback: use the domain name without common prefixes/suffixes
        domain = hostname
        for prefix in ["www.", "jobs.", "careers.", "boards.", "apply."]:
            if domain.startswith(prefix):
                domain = domain[len(prefix):]
        if "." in domain:
            domain = domain.rsplit(".", 1)[0]

        return domain
