"""
Persistent state management for the job search tool.

Manages two state files:
- seen_jobs.json: tracks job URLs already processed (deduplication across runs)
- query_performance.json: tracks which search queries yield high-scoring results
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

logger = logging.getLogger(__name__)

# Tracking parameters to strip during URL normalization
_TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "utm_source_platform",
    "utm_creative_format",
    "utm_marketing_tactic",
    "fbclid",
    "gclid",
    "gclsrc",
    "dclid",
    "gbraid",
    "wbraid",
    "msclkid",
    "twclid",
    "li_fat_id",
    "igshid",
    "mc_cid",
    "mc_eid",
    "s_kwcid",
    "ef_id",
    "_openstat",
    "yclid",
    "ref",
    "referrer",
    "source",
}

# Regex to extract LinkedIn job ID from various LinkedIn job URL formats
_LINKEDIN_JOB_ID_RE = re.compile(
    r"linkedin\.com/(?:jobs/view|jobs/collections/recommended/\?currentJobId=)(\d+)",
    re.IGNORECASE,
)


def normalize_url(url: str) -> str:
    """Normalize a job URL for deduplication.

    - Lowercase the scheme and host
    - Strip tracking parameters (utm_*, fbclid, gclid, etc.)
    - Strip trailing slashes from the path
    - For LinkedIn job URLs, reduce to canonical form using job ID
    """
    url = url.strip()

    # LinkedIn canonical form: extract job ID if present
    # Handle currentJobId=XXXXX query parameter form
    parsed = urlparse(url)
    if "linkedin.com" in parsed.netloc.lower():
        # Check for job ID in the path (e.g., /jobs/view/1234567890/)
        path_match = re.search(r"/jobs/view/(\d+)", parsed.path)
        if path_match:
            job_id = path_match.group(1)
            return f"https://www.linkedin.com/jobs/view/{job_id}"

        # Check for currentJobId in the query string
        query_params = parse_qs(parsed.query)
        if "currentJobId" in query_params:
            job_id = query_params["currentJobId"][0]
            return f"https://www.linkedin.com/jobs/view/{job_id}"

    # General normalization for non-LinkedIn URLs (or LinkedIn URLs without a job ID)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")

    # Filter out tracking params
    query_params = parse_qs(parsed.query, keep_blank_values=True)
    filtered_params = {
        k: v for k, v in query_params.items() if k.lower() not in _TRACKING_PARAMS
    }
    # Sort params for deterministic output
    clean_query = urlencode(filtered_params, doseq=True) if filtered_params else ""

    normalized = urlunparse((scheme, netloc, path, parsed.params, clean_query, ""))
    return normalized


def _load_json(path: Path) -> dict:
    """Load a JSON file, returning an empty dict if the file doesn't exist or is corrupt."""
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        if not isinstance(data, dict):
            logger.warning("State file %s does not contain a JSON object; resetting", path)
            return {}
        return data
    except json.JSONDecodeError as exc:
        logger.error("Corrupt state file %s: %s; resetting", path, exc)
        return {}


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON data to a file atomically using a .tmp intermediate file."""
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(str(tmp_path), str(path))


class StateManager:
    """Manages persistent state for job search deduplication and query tracking."""

    def __init__(self, data_dir: str = "data") -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._seen_path = self._data_dir / "seen_jobs.json"
        self._query_path = self._data_dir / "query_performance.json"

        # Create files with empty dicts if they don't exist
        for path in (self._seen_path, self._query_path):
            if not path.exists():
                _atomic_write_json(path, {})

        self._seen_jobs: dict = _load_json(self._seen_path)
        self._query_performance: dict = _load_json(self._query_path)

        logger.info(
            "StateManager loaded: %d seen jobs, %d tracked queries",
            len(self._seen_jobs),
            len(self._query_performance),
        )

    def is_seen(self, job_url: str) -> bool:
        """Check if a job URL has already been processed."""
        canonical = normalize_url(job_url)
        return canonical in self._seen_jobs

    def mark_seen(self, job_url: str, metadata: dict) -> None:
        """Mark a job URL as processed with associated metadata.

        Args:
            job_url: The raw job URL.
            metadata: Dict with keys like title, company, source, score.
                      A first_seen timestamp is added automatically.
        """
        canonical = normalize_url(job_url)
        entry = dict(metadata)
        entry["first_seen"] = datetime.now(timezone.utc).isoformat()
        entry["original_url"] = job_url
        self._seen_jobs[canonical] = entry

    def record_query_result(
        self, query: str, jobs_found: int, high_score_jobs: int, avg_score: float
    ) -> None:
        """Record the results of a search query for performance tracking.

        Each invocation is appended as a history entry so that performance
        can be tracked over time. Summary statistics are maintained alongside
        the raw history.
        """
        now = datetime.now(timezone.utc).isoformat()
        entry = {
            "timestamp": now,
            "jobs_found": jobs_found,
            "high_score_jobs": high_score_jobs,
            "avg_score": round(avg_score, 4),
        }

        if query not in self._query_performance:
            self._query_performance[query] = {
                "history": [],
                "total_runs": 0,
                "total_jobs_found": 0,
                "total_high_score_jobs": 0,
            }

        record = self._query_performance[query]
        record["history"].append(entry)
        record["total_runs"] += 1
        record["total_jobs_found"] += jobs_found
        record["total_high_score_jobs"] += high_score_jobs
        record["last_run"] = now

    def get_top_queries(self, n: int = 10) -> list[dict]:
        """Return the best-performing queries ranked by average high-score yield.

        The high-score yield for a query is the ratio of high-scoring jobs
        found to total runs of that query.
        """
        ranked = []
        for query, record in self._query_performance.items():
            total_runs = record.get("total_runs", 0)
            if total_runs == 0:
                continue
            avg_high_score_yield = record["total_high_score_jobs"] / total_runs
            ranked.append(
                {
                    "query": query,
                    "total_runs": total_runs,
                    "total_jobs_found": record["total_jobs_found"],
                    "total_high_score_jobs": record["total_high_score_jobs"],
                    "avg_high_score_yield": round(avg_high_score_yield, 4),
                    "last_run": record.get("last_run"),
                }
            )
        ranked.sort(key=lambda x: x["avg_high_score_yield"], reverse=True)
        return ranked[:n]

    def save(self) -> None:
        """Persist current state to disk using atomic writes."""
        _atomic_write_json(self._seen_path, self._seen_jobs)
        _atomic_write_json(self._query_path, self._query_performance)
        logger.info(
            "State saved: %d seen jobs, %d tracked queries",
            len(self._seen_jobs),
            len(self._query_performance),
        )

    def stats(self) -> dict:
        """Return summary statistics for the CLI status command."""
        total_high_score = sum(
            r.get("total_high_score_jobs", 0)
            for r in self._query_performance.values()
        )
        total_jobs_found = sum(
            r.get("total_jobs_found", 0)
            for r in self._query_performance.values()
        )
        return {
            "seen_jobs": len(self._seen_jobs),
            "tracked_queries": len(self._query_performance),
            "total_query_runs": sum(
                r.get("total_runs", 0) for r in self._query_performance.values()
            ),
            "total_jobs_found": total_jobs_found,
            "total_high_score_jobs": total_high_score,
        }
