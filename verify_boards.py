#!/usr/bin/env python3
"""One-time verification script to test all ATS board tokens.

Run this after setting up ats_companies.json to confirm that every
board_token resolves to a valid public job board.
"""

import json
import sys
from pathlib import Path

import httpx

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config" / "ats_companies.json"


def check_greenhouse(client: httpx.Client, name: str, token: str) -> bool:
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    resp = client.get(url)
    if resp.status_code == 200:
        data = resp.json()
        count = len(data.get("jobs", []))
        print(f"  OK  {name} (greenhouse:{token}) - {count} open jobs")
        return True
    print(f"  FAIL {name} (greenhouse:{token}) - HTTP {resp.status_code}")
    return False


def check_lever(client: httpx.Client, name: str, token: str) -> bool:
    url = f"https://api.lever.co/v0/postings/{token}"
    resp = client.get(url)
    if resp.status_code == 200:
        data = resp.json()
        count = len(data) if isinstance(data, list) else 0
        print(f"  OK  {name} (lever:{token}) - {count} open postings")
        return True
    print(f"  FAIL {name} (lever:{token}) - HTTP {resp.status_code}")
    return False


def check_ashby(client: httpx.Client, name: str, token: str) -> bool:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{token}"
    resp = client.get(url)
    if resp.status_code == 200:
        data = resp.json()
        count = len(data.get("jobs", []))
        print(f"  OK  {name} (ashby:{token}) - {count} open jobs")
        return True
    print(f"  FAIL {name} (ashby:{token}) - HTTP {resp.status_code}")
    return False


def main():
    config = json.loads(CONFIG_PATH.read_text())
    companies = config.get("companies", [])

    print(f"Verifying {len(companies)} ATS board tokens...\n")

    checkers = {
        "greenhouse": check_greenhouse,
        "lever": check_lever,
        "ashby": check_ashby,
    }

    ok = 0
    fail = 0
    skip = 0

    with httpx.Client(timeout=15) as client:
        for company in companies:
            name = company.get("name", "unknown")
            ats = company.get("ats", "")
            token = company.get("board_token", "")

            if ats == "custom" or not token:
                print(f"  SKIP {name} (ats={ats}, no board_token)")
                skip += 1
                continue

            checker = checkers.get(ats)
            if checker is None:
                print(f"  SKIP {name} (unknown ats type: {ats})")
                skip += 1
                continue

            try:
                if checker(client, name, token):
                    ok += 1
                else:
                    fail += 1
            except Exception as e:
                print(f"  ERROR {name} ({ats}:{token}) - {e}")
                fail += 1

    print(f"\nResults: {ok} OK, {fail} FAILED, {skip} skipped")
    sys.exit(1 if fail > 0 else 0)


if __name__ == "__main__":
    main()
