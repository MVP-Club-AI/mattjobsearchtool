"""Daily markdown report generator for scored job results."""

import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates daily markdown reports from scored job results."""

    def __init__(self, data_dir: str = "data"):
        self.reports_dir = Path(data_dir) / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, scored_jobs: list[dict], stats: dict,
                 filename: str | None = None, title: str | None = None) -> str:
        """Generate a markdown report and save to file.

        Args:
            scored_jobs: List of scored job dicts, already sorted by fit_score descending.
            stats: Dict with keys like total_scanned, sources, etc.
            filename: Custom filename (default: YYYY-MM-DD.md).
            title: Custom report title (default: "Job Search Report -- {date}").

        Returns:
            The file path of the saved report as a string.
        """
        today = date.today().isoformat()
        if filename is None:
            filename = f"{today}.md"
        filepath = self.reports_dir / filename

        total_scanned = stats.get("total_scanned", 0)
        sources = stats.get("sources", "N/A")

        report_title = title or f"Job Search Report -- {today}"
        lines = []
        lines.append(f"# {report_title}")
        lines.append("")
        lines.append(
            f"**Jobs scanned:** {total_scanned} "
            f"| **New matches:** {len(scored_jobs)} "
            f"| **Sources:** {sources}"
        )
        lines.append("")
        lines.append("---")

        if not scored_jobs:
            lines.append("")
            lines.append(
                f"No new matches found today. {total_scanned} jobs were scanned."
            )
            lines.append("")
        else:
            for idx, job in enumerate(scored_jobs, start=1):
                lines.append("")
                lines.append(self._format_job(idx, job))
                lines.append("---")

        report_content = "\n".join(lines) + "\n"
        filepath.write_text(report_content, encoding="utf-8")

        logger.info("Report saved to %s", filepath)
        return str(filepath)

    def _format_job(self, number: int, job: dict) -> str:
        """Format a single job entry as a markdown section."""
        title = job.get("title", "Unknown Title")
        company = job.get("company", "Unknown Company")
        fit_score = job.get("fit_score", "N/A")
        seniority_match = job.get("seniority_match", "Unknown")
        innovation_signal = job.get("innovation_signal", "Unknown")
        location = job.get("location", "Unknown")
        remote = "Yes" if job.get("is_remote") else "Unknown"
        date_posted = job.get("date_posted", "Unknown")
        source = job.get("source", "Unknown")
        reasoning = job.get("reasoning", "No reasoning provided.")
        key_overlaps = job.get("key_overlaps", [])
        key_gaps = job.get("key_gaps", [])
        url = job.get("url", "#")
        connections = job.get("network_connections", [])

        salary_line = self._format_salary(job)

        lines = []
        lines.append(f"## {number}. {title} at {company}")
        lines.append("")
        lines.append(
            f"**Score:** {fit_score}/100 "
            f"| **Seniority:** {seniority_match} "
            f"| **Innovation:** {innovation_signal}"
        )
        lines.append("")
        lines.append(f"**Salary:** {salary_line}")
        lines.append(f"**Location:** {location} | **Remote:** {remote}")
        lines.append(f"**Posted:** {date_posted} | **Source:** {source}")
        lines.append("")
        lines.append(f"**Why this fits:** {reasoning}")
        lines.append("")
        lines.append(f"**Key overlaps:** {', '.join(key_overlaps) if key_overlaps else 'None identified'}")
        lines.append(f"**Gaps to address:** {', '.join(key_gaps) if key_gaps else 'None identified'}")

        if connections:
            lines.append("")
            lines.append(f"**Connections at {company}:**")
            for conn in connections:
                first = conn.get("first_name", "")
                last = conn.get("last_name", "")
                conn_url = conn.get("url", "#")
                position = conn.get("position", "Unknown")
                lines.append(f"- [{first} {last}]({conn_url}) -- {position}")

        lines.append("")
        lines.append(f"**[Apply]({url})**")
        lines.append("")

        return "\n".join(lines)

    def _format_salary(self, job: dict) -> str:
        """Format salary info from various fields.

        Priority:
            1. salary_details (if present and not null) with salary_signal in parens
            2. salary_min / salary_max range formatting
            3. Fallback to "Not listed" with salary_signal
        """
        salary_details = job.get("salary_details")
        salary_signal = job.get("salary_signal", "unknown")
        salary_min = job.get("salary_min")
        salary_max = job.get("salary_max")

        if salary_details:
            return f"{salary_details} ({salary_signal})"

        if salary_min and salary_max:
            return f"${salary_min} - ${salary_max}"
        elif salary_min:
            return f"${salary_min}+"
        elif salary_max:
            return f"Up to ${salary_max}"

        return f"Not listed ({salary_signal})"
