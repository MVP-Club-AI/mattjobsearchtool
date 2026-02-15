# Job Search Tool — Claude Code Guide

This is an automated job search pipeline that discovers roles from multiple sources, scores them against a candidate profile using Claude AI, cross-references LinkedIn connections, and generates daily reports.

## First-Time Setup Guide

When a new user clones this repo and opens Claude Code, walk them through setup by opening the interactive guide:

```
Open docs/guide.html in the browser to see a visual walkthrough of how the tool works.
```

Then help them complete these steps:

### 1. Create their `.env` file
```bash
cp .env.example .env
```
They need two API keys:
- `ANTHROPIC_API_KEY` — from console.anthropic.com (required for Claude scoring)
- `SERPER_API_KEY` — from serper.dev (required for Google search discovery, 2500 free queries/month)

### 2. Create their `config/profile_index.json`
Copy the example and fill in their own profile:
```bash
cp config/profile_index.example.json config/profile_index.json
```
This file defines who the candidate IS — their name, location, salary floor, target titles, competencies, tools, education, experience highlights, and industry interests. The Claude scoring system uses this to evaluate job fit.

### 3. Create their `config/verisk_reference.json`
Copy the example and fill in a reference job:
```bash
cp config/verisk_reference.json.example config/verisk_reference.json
```
This is a "gold standard" job posting that represents the candidate's ideal role. Claude uses it as a reference point when scoring. Name it whatever you want — just keep the same JSON structure.

### 4. Add their LinkedIn connections
Export connections from LinkedIn (Settings → Data Privacy → Get a copy of your data → Connections) and place the CSV at:
```
data/connections.csv
```
This enables network matching — the tool will flag when you have connections at companies with open roles.

### 5. Edit `config/settings.json`
Update location, remote preference, and score threshold to match their search:
- `location` — their city (used in location filtering)
- `is_remote` — whether they prefer remote roles
- `score_threshold` — minimum fit score (0–100) to include in reports (default: 60)
- `hours_old` — how recent a posting must be (default: 72 hours)

### 6. Customize `config/ats_companies.json`
Add or remove companies to monitor via direct ATS feeds (Greenhouse, Lever, Ashby, Workday).

### 7. Install and run
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
jobsearch run
```

## Architecture Overview

```
Discovery (3 sources)    →    Triage (free)    →    Scoring (Claude API)    →    Report
├─ JobSpy (5 boards)          Keyword filter         Semantic fit scoring       Markdown report
├─ ATS feeds (57+ co's)      Location filter         Network context boost      data/reports/YYYY-MM-DD.md
└─ Serper (Google)            Score 0-10              Score 0-100
```

### Discovery Sources
- **JobSpy** (`src/discovery/jobspy_search.py`): Scrapes Indeed, LinkedIn, ZipRecruiter, Google, Glassdoor using 16 pre-defined queries
- **ATS Feeds** (`src/discovery/ats_feeds.py`): Polls Greenhouse, Lever, Ashby, Workday APIs for companies in `config/ats_companies.json`
- **Serper** (`src/discovery/serper_search.py`): Google searches via Serper API for niche job boards

### Two-Stage Filtering
1. **Triage** (`src/scoring/triage.py`): Free, instant keyword + location filter. Scores 0–10. Rejects irrelevant roles (engineers, healthcare, sales). Only Denver/Front Range or remote pass.
2. **Claude Scoring** (`src/scoring/fit_scorer.py`): Semantic evaluation via Claude API. Scores 0–100 with detailed reasoning, salary signal, innovation signal, seniority match, key overlaps, and gaps.

### Network Matching
`src/network/matcher.py` cross-references the company on each job against `data/connections.csv`. Uses exact + fuzzy matching. Connections are passed to Claude as context, giving a 3–5 point boost for borderline jobs (score 55–70).

### State Management
`src/state/manager.py` tracks all seen jobs in `data/seen_jobs.json` to prevent duplicates across runs. Also tracks query performance in `data/query_performance.json`.

### Reporting
`src/reporting/generator.py` produces daily markdown reports sorted by score, with salary info, network connections, apply links, and Claude's reasoning.

## CLI Commands

| Command | What it does |
|---------|-------------|
| `jobsearch run` | Full pipeline: discover → triage → score → report |
| `jobsearch search "query"` | Ad-hoc single-query search with scoring |
| `jobsearch status` | Stats: jobs seen, top queries, network size |
| `jobsearch add-company "Name" --ats greenhouse --token slug` | Add a company to ATS monitoring |
| `jobsearch expand-ats /path/to/LinkedInExport --auto` | Auto-detect ATS platforms from LinkedIn data |

## Folder Structure

```
job-search-tool/
├── config/
│   ├── settings.json              # Runtime settings (API keys via ENV:, thresholds, location)
│   ├── profile_index.json         # YOUR profile (gitignored — personal)
│   ├── verisk_reference.json      # YOUR reference job (gitignored — personal)
│   ├── ats_companies.json         # Companies to monitor via ATS feeds
│   ├── profile_index.example.json # Template for new users
│   └── verisk_reference.json.example # Template for new users
├── data/
│   ├── connections.csv            # LinkedIn connections export (gitignored — personal)
│   ├── seen_jobs.json             # Deduplication state (gitignored)
│   ├── query_performance.json     # Query effectiveness tracking (gitignored)
│   ├── reports/                   # Daily markdown reports (gitignored)
│   └── logs/                      # Run logs (gitignored)
├── src/
│   ├── cli.py                     # Click CLI entry point
│   ├── discovery/
│   │   ├── jobspy_search.py       # JobSpy board scraper
│   │   ├── ats_feeds.py           # Direct ATS API polling
│   │   ├── serper_search.py       # Google search via Serper
│   │   └── ats_detector.py        # Auto-detect ATS for new companies
│   ├── scoring/
│   │   ├── triage.py              # Keyword + location pre-filter (free)
│   │   └── fit_scorer.py          # Claude AI semantic scoring (paid)
│   ├── network/
│   │   └── matcher.py             # LinkedIn connection matching
│   ├── reporting/
│   │   └── generator.py           # Markdown report generation
│   └── state/
│       └── manager.py             # Deduplication + query tracking
├── .env                           # API keys (gitignored)
├── .env.example                   # Template for .env
├── run.sh                         # Cron wrapper for daily automation
├── setup.py                       # Package installer
└── requirements.txt               # Python dependencies
```

## What Users Can Ask Claude Code to Do

### Search & Discovery
- "Run a full job search" → `jobsearch run`
- "Search for AI coach roles" → `jobsearch search "AI coach"`
- "Add Stripe to the ATS monitoring list" → `jobsearch add-company`
- "Expand ATS monitoring from my LinkedIn export" → `jobsearch expand-ats`

### Profile Customization
- "Update my target titles to focus on product management"
- "Change my salary floor to $150k"
- "Add new competencies to my profile"
- "Set a new reference job posting" (update verisk_reference.json)

### Analysis & Reports
- "Show me my search status" → `jobsearch status`
- "Read today's report and summarize the top 5 matches"
- "Which queries are performing best?"
- "How many jobs have I seen this week?"

### Scoring Tuning
- "Change the score threshold to 70"
- "Adjust the triage keywords to include 'program manager'"
- "Update the scoring rubric to weight remote roles higher"

### Automation
- "Set up a daily cron job" → configure `run.sh` in crontab
- "Check the latest run log"

## Key Design Principles

1. **Two-stage filter saves money**: Free keyword triage runs first, Claude API scoring only runs on promising candidates
2. **Network context matters**: LinkedIn connections are looked up BEFORE scoring so Claude can factor them in
3. **No duplicates**: All seen jobs are tracked across runs via URL normalization
4. **Atomic state writes**: State files use tmp + rename to prevent corruption
5. **Personal data stays local**: Profile, connections, reports, and API keys are all gitignored

## Scoring Rubric (for reference)

| Score | Meaning |
|-------|---------|
| 90–100 | Near-perfect: AI enablement is the PRIMARY mission, correct seniority |
| 75–89 | Strong: 2 of 3 core pillars present (enablement + coaching + building) |
| 60–74 | Moderate: credible entry points into the candidate's target career |
| 40–59 | Weak: some overlap but not a strong match |
| 0–39 | Poor: little overlap with candidate profile |
