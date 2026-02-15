"""
JobSpy-based job discovery module.

Primary discovery source that searches across LinkedIn, Indeed, Glassdoor,
Google, and ZipRecruiter using the python-jobspy library.
"""

import logging
import random
import re
import time
import urllib.parse

from jobspy import scrape_jobs

logger = logging.getLogger(__name__)

QUERY_SETS = [
    # Group 1 - Direct AI enablement titles
    {"search_term": "AI Enablement Lead"},
    {"search_term": "AI Adoption Manager"},
    {"search_term": "Director AI Training"},
    {"search_term": "Head of AI Academy"},
    {"search_term": "AI Change Management"},
    # Group 2 - Learning/L&D + AI intersection
    {"search_term": "Learning Manager AI"},
    {"search_term": "Director Learning Design"},
    {"search_term": "Senior Manager Learning Experience Design"},
    {"search_term": "Learning Architect AI"},
    {"search_term": "L&D Manager AI tools"},
    # Group 3 - Product + Education
    {"search_term": "Product Manager Education Technology"},
    {"search_term": "Learning Product Manager"},
    {"search_term": "Product Manager EdTech"},
    # Group 4 - Enablement broadly
    {"search_term": "Director of Enablement AI"},
    {"search_term": "Customer Education Manager AI"},
    {"search_term": "Workforce Transformation AI"},
    # Group 5 - Industry-specific
    {"search_term": "AI Training Manager robotics", "is_remote": False, "location": "Denver, CO"},
    {"search_term": "AI Training agriculture AgTech"},
    # Group 6 - Broad catch-alls
    {"search_term": "AI coaching enablement workforce"},
    {"search_term": "generative AI learning development manager"},
]

TRACKING_PARAMS = re.compile(
    r"^(utm_\w+|fbclid|gclid|gad_source|si|ref|tracking_id|rcid|refId|trk|clickTrackingKey)$",
    re.IGNORECASE,
)

LINKEDIN_JOB_VIEW_RE = re.compile(r"/view/(\d+)")


class JobSpySearch:
    """Searches multiple job boards via python-jobspy and returns deduplicated results."""

    def __init__(self, settings: dict, state_manager):
        self.settings = settings
        self.state_manager = state_manager

    def run_all_queries(self) -> list[dict]:
        """Execute every query in QUERY_SETS, deduplicate, and filter seen jobs."""
        all_jobs: dict[str, dict] = {}  # normalized_url -> job dict
        total = len(QUERY_SETS)

        for i, query_config in enumerate(QUERY_SETS, start=1):
            search_term = query_config["search_term"]
            is_remote = query_config.get("is_remote", True)
            location = query_config.get("location", self.settings.get("location", ""))

            try:
                df = scrape_jobs(
                    site_name=["indeed", "linkedin", "zip_recruiter", "google", "glassdoor"],
                    search_term=search_term,
                    location=location,
                    results_wanted=self.settings.get("results_per_query", 25),
                    hours_old=self.settings.get("hours_old", 72),
                    is_remote=is_remote,
                    country_indeed=self.settings.get("country", "USA"),
                    description_format="markdown",
                    linkedin_fetch_description=True,
                    verbose=0,
                )
            except Exception:
                logger.warning("Query %d/%d: '%s' failed", i, total, search_term, exc_info=True)
                if i < total:
                    time.sleep(random.uniform(2, 5))
                continue

            jobs = self._process_dataframe(df, search_term)
            new_count = 0
            for job in jobs:
                norm_url = job["_normalized_url"]
                if norm_url not in all_jobs:
                    all_jobs[norm_url] = job
                    new_count += 1

            logger.info("Query %d/%d: '%s' - found %d new jobs", i, total, search_term, new_count)

            if i < total:
                time.sleep(random.uniform(2, 5))

        # Filter out previously seen jobs and strip internal keys
        results = []
        for job in all_jobs.values():
            if self.state_manager.is_seen(job["url"]):
                continue
            job.pop("_normalized_url", None)
            results.append(job)

        logger.info("Discovery complete: %d new jobs across %d queries", len(results), total)
        return results

    def search_single(self, query: str) -> list[dict]:
        """Execute a single ad-hoc query and return results (no dedup against seen jobs)."""
        try:
            df = scrape_jobs(
                site_name=["indeed", "linkedin", "zip_recruiter", "google", "glassdoor"],
                search_term=query,
                location=self.settings.get("location", ""),
                results_wanted=self.settings.get("results_per_query", 25),
                hours_old=self.settings.get("hours_old", 72),
                is_remote=True,
                country_indeed=self.settings.get("country", "USA"),
                description_format="markdown",
                linkedin_fetch_description=True,
                verbose=0,
            )
        except Exception:
            logger.warning("Ad-hoc query '%s' failed", query, exc_info=True)
            return []

        jobs = self._process_dataframe(df, query)
        # Strip internal keys
        for job in jobs:
            job.pop("_normalized_url", None)
        return jobs

    def _process_dataframe(self, df, query: str) -> list[dict]:
        """Convert a jobspy DataFrame into a list of standardised job dicts."""
        jobs = []
        if df is None or df.empty:
            return jobs

        for _, row in df.iterrows():
            raw_url = str(row.get("job_url", "") or "")
            if not raw_url or raw_url == "nan":
                continue

            norm_url = self._normalize_url(raw_url)
            if self.state_manager.is_seen(raw_url):
                continue

            site = str(row.get("site", "unknown")).lower()

            # Handle salary fields which may be NaN
            salary_min = row.get("min_amount", None)
            salary_max = row.get("max_amount", None)
            if salary_min is not None:
                try:
                    salary_min = float(salary_min)
                    if salary_min != salary_min:  # NaN check
                        salary_min = None
                except (TypeError, ValueError):
                    salary_min = None
            if salary_max is not None:
                try:
                    salary_max = float(salary_max)
                    if salary_max != salary_max:  # NaN check
                        salary_max = None
                except (TypeError, ValueError):
                    salary_max = None

            date_posted = row.get("date_posted", None)
            if date_posted is not None:
                date_posted = str(date_posted)
                if date_posted == "NaT" or date_posted == "nan":
                    date_posted = None

            is_remote_val = row.get("is_remote", None)
            if is_remote_val is not None:
                try:
                    is_remote_val = bool(is_remote_val)
                except (TypeError, ValueError):
                    is_remote_val = None

            job = {
                "title": str(row.get("title", "") or ""),
                "company": str(row.get("company", "") or ""),
                "location": str(row.get("location", "") or ""),
                "url": raw_url,
                "description": str(row.get("description", "") or ""),
                "salary_min": salary_min,
                "salary_max": salary_max,
                "date_posted": date_posted,
                "is_remote": is_remote_val,
                "source": f"jobspy:{site}",
                "query": query,
                "_normalized_url": norm_url,
            }
            jobs.append(job)

        return jobs

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Produce a canonical URL by stripping trackers and normalising LinkedIn job URLs."""
        url = url.strip()

        # For LinkedIn /view/ URLs, extract the job ID as the canonical form
        match = LINKEDIN_JOB_VIEW_RE.search(url)
        if match:
            return f"https://www.linkedin.com/jobs/view/{match.group(1)}"

        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query, keep_blank_values=False)
        filtered = {k: v for k, v in params.items() if not TRACKING_PARAMS.match(k)}
        clean_query = urllib.parse.urlencode(filtered, doseq=True)

        normalized = urllib.parse.urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            parsed.params,
            clean_query,
            "",  # drop fragment
        ))

        return normalized
