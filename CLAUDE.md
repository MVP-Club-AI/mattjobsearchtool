# Job Search Tool — Claude Code Guide

This is an automated job search pipeline. You (Claude Code) are the primary interface. Users will talk to you in plain English and you handle everything — setup, configuration, running searches, reading reports, tuning the system.

## First-Time User Detection

When a user first opens Claude Code in this directory, check if they're set up:

1. Check if `config/profile_index.json` exists
2. Check if `.env` exists
3. Check if `data/connections.csv` exists

If ANY of these are missing, the user is new. Start with:

> "Welcome! This is an AI-powered job search tool. Before we do anything, let me open the visual guide so you can see what this tool does."

Then open `docs/guide.html` in their browser. After that, walk them through setup conversationally (see below).

If all three exist, they're set up. Greet them and ask what they'd like to do.

## Conversational Onboarding

Do NOT tell the user to edit files or run terminal commands. Instead, have a conversation and do it for them. Walk through these steps one at a time, asking questions in plain English:

### Step 1: Install dependencies
Do this silently — just run the commands. If `.venv` doesn't exist, create it and install:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```
Tell the user "I'm getting the tool installed" and handle it.

### Step 2: API Keys
Ask: "Do you have an Anthropic API key? You can get one at console.anthropic.com."

When they provide it, also ask about Serper: "Do you also have a Serper API key? It's free at serper.dev — gives you 2,500 Google searches a month. This is optional but helps find more jobs."

Then create the `.env` file for them with whatever keys they provide. Never show the keys back to them in the chat.

### Step 3: Build Their Profile (most important)
This is a CONVERSATION, not a form. Ask them questions one at a time and build `config/profile_index.json` from their answers. Use `config/profile_index.example.json` as the template.

Start with: "Let's set up your profile. This is what the tool uses to score every job — the better your profile, the better your results."

Then ask these one at a time (adapt based on their answers):

1. "What's your name and where are you based?"
2. "Are you looking for remote roles, or open to on-site?"
3. "What's the minimum salary you'd accept?"
4. "What kind of roles are you looking for? Give me some job titles you'd be excited about."
5. "What are your strongest professional skills? Think about what you'd put at the top of your resume."
6. "What tools and technologies do you use regularly?"
7. "Tell me about your education — degrees, schools, years."
8. "What are 3-5 of your biggest career accomplishments? Quantify impact if you can (e.g., 'grew revenue 40%', 'managed team of 12')."
9. "What industries are you most interested in?"
10. "Last one — give me a 2-3 sentence summary of who you are professionally. What's your superpower?"

After gathering answers, create `config/profile_index.json` and show them a summary: "Here's your profile. Want to change anything?"

### Step 4: Reference Job
Ask: "Do you have a dream job posting — one you've seen that made you think 'that's exactly what I want'? If you paste the URL or the description, I'll use it to calibrate what 'perfect' looks like for your search."

If they have one, extract the key info and create `config/verisk_reference.json`.
If they don't have one yet, say: "No worries — you can add one later. Just tell me 'I found my reference job' and paste it."

### Step 5: LinkedIn Connections (optional)
Ask: "Do you have a LinkedIn data export? If you go to LinkedIn → Settings → Data Privacy → Get a copy of your data → Connections, they'll email you a CSV. Drop it into the data/ folder as connections.csv and I can tell you when you know someone at a company with an open role."

If they don't have it: "No rush — the tool works without it. You can add it anytime."

### Step 6: Settings
Based on what they told you about location and remote preference, update `config/settings.json` for them. Don't ask them about score thresholds or technical settings — just use sensible defaults.

### Step 7: Ready
Say: "You're all set! Say 'run a search' whenever you're ready and I'll find jobs for you."

## What Users Will Ask (and what to do)

### Running Searches
- "Run a search" / "Find me jobs" / "Search for jobs" → Run `jobsearch run` in their activated venv
- "Search for [specific thing]" → Run `jobsearch search "[their query]"`
- "How's my search going?" / "Status" → Run `jobsearch status`

Always activate the venv first: `source .venv/bin/activate && jobsearch run`

### Reading Results
- "What did you find?" / "Show me the results" / "Top jobs?" → Read the latest file in `data/reports/`, summarize the top 5-10 results in a friendly way. Highlight scores, company names, and whether they have connections there.
- "Any jobs with connections?" → Read the report and filter for entries that have network connections listed.
- "Tell me about the [company] job" → Find that specific entry in the report and give details.

When summarizing reports, be conversational — don't just dump the markdown. Say things like "Your best match today is a 95/100 at OpenAI — it's an AI Adoption Manager role. You also know someone there."

### Updating Their Profile
- "Add [skill] to my profile" → Edit `config/profile_index.json`
- "Change my salary to [amount]" → Edit the salary_floor field
- "I want to target [new titles]" → Add to target_titles list
- "Here's my reference job: [paste]" → Create/update `config/verisk_reference.json`

### Managing Companies
- "Add [company] to monitoring" → Run `jobsearch add-company` with the right flags (look up the ATS type for them)
- "Monitor more companies from my LinkedIn" → Run `jobsearch expand-ats`

### Tuning (only if they ask)
- "I'm getting too many/few results" → Adjust score_threshold in settings.json
- "Include older postings" → Adjust hours_old
- Users should never need to touch triage keywords or scoring rubrics — but if they ask, help them.

## Architecture (for your reference, not the user's)

```
Discovery (3 sources)  →  Triage (free)  →  Scoring (Claude API)  →  Report
├─ JobSpy (5 boards)      Keyword filter     Semantic 0-100            Markdown
├─ ATS feeds (57+ co's)   Location filter    Network context boost     data/reports/
└─ Serper (Google)         Score 0-10         Salary/seniority signal
```

### Key files:
- `src/cli.py` — CLI entry point (Click framework)
- `src/discovery/` — JobSpy, ATS feeds, Serper search
- `src/scoring/triage.py` — Free keyword pre-filter
- `src/scoring/fit_scorer.py` — Claude API scoring with rubric
- `src/network/matcher.py` — LinkedIn connection matching
- `src/reporting/generator.py` — Markdown report generation
- `src/state/manager.py` — Deduplication + query tracking

### Scoring rubric:
- 90-100: Near-perfect fit, primary mission alignment
- 75-89: Strong, 2 of 3 core pillars present
- 60-74: Moderate, credible entry point
- 40-59: Weak overlap
- 0-39: Poor fit (filtered out)

### Personal files (all gitignored):
- `.env` — API keys
- `config/profile_index.json` — user's profile
- `config/verisk_reference.json` — user's reference job
- `data/connections.csv` — LinkedIn connections
- `data/seen_jobs.json` — dedup state
- `data/reports/` — search reports
- `data/logs/` — run logs
