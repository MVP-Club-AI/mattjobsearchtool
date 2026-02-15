"""Network matcher module.

Cross-references company names from job postings against LinkedIn connections
to identify people Matthew knows at companies with open roles.
"""

import csv
import logging
from pathlib import Path

from thefuzz import fuzz

logger = logging.getLogger(__name__)

# Suffixes to strip during normalization, ordered longest-first to avoid
# partial removals (e.g. ", inc." before " inc").
_COMPANY_SUFFIXES = [
    ", inc.",
    ", inc",
    " inc.",
    " inc",
    " corporation",
    " company",
    " corp",
    " llc",
    " ltd",
    " co.",
]


class NetworkMatcher:
    """Matches company names from job postings against LinkedIn connections."""

    def __init__(self, connections_csv_path: str) -> None:
        self.connections: list[dict] = []
        self.company_index: dict[str, list[dict]] = {}

        path = Path(connections_csv_path)
        if not path.exists():
            logger.warning("Connections file not found: %s", connections_csv_path)
            return

        self._load(path)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load(self, path: Path) -> None:
        """Parse the LinkedIn Connections.csv, skipping the 3 preamble lines."""
        with open(path, newline="", encoding="utf-8") as fh:
            # Skip the 3 non-CSV preamble lines:
            #   Line 1: "Notes:"
            #   Line 2: long note about email addresses
            #   Line 3: empty
            for _ in range(3):
                fh.readline()

            reader = csv.DictReader(fh)
            for row in reader:
                company = (row.get("Company") or "").strip()
                if not company:
                    continue

                connection = {
                    "first_name": (row.get("First Name") or "").strip(),
                    "last_name": (row.get("Last Name") or "").strip(),
                    "url": (row.get("URL") or "").strip(),
                    "email": (row.get("Email Address") or "").strip(),
                    "company": company,
                    "position": (row.get("Position") or "").strip(),
                    "connected_on": (row.get("Connected On") or "").strip(),
                }
                self.connections.append(connection)

                key = self._normalize(company)
                self.company_index.setdefault(key, []).append(connection)

        logger.info(
            "Loaded %d connections across %d unique companies",
            len(self.connections),
            len(self.company_index),
        )

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------

    def find_connections(self, company_name: str) -> list[dict]:
        """Find LinkedIn connections at *company_name*.

        Tries an exact (normalized) match first.  Falls back to fuzzy matching
        with thefuzz when no exact hit is found.
        """
        target = self._normalize(company_name)

        # Exact match
        if target in self.company_index:
            return list(self.company_index[target])

        # Fuzzy match
        matches: list[dict] = []
        for indexed_name, conns in self.company_index.items():
            if (
                fuzz.ratio(target, indexed_name) >= 85
                or fuzz.partial_ratio(target, indexed_name) >= 90
            ):
                matches.extend(conns)

        return matches

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(name: str) -> str:
        """Lowercase, strip, and remove common corporate suffixes."""
        result = name.lower().strip()
        for suffix in _COMPANY_SUFFIXES:
            if result.endswith(suffix):
                result = result[: -len(suffix)]
                break
        return result

    def get_stats(self) -> dict:
        """Return summary statistics about the loaded connections."""
        return {
            "total_connections": len(self.connections),
            "unique_companies": len(self.company_index),
        }
