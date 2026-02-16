<div align="center">

# Stop Searching. Start Scoring.

**An AI-powered job search tool that scans thousands of postings, scores them against your profile, and tells you which ones are actually worth applying to.**

You talk to Claude Code. It handles the rest.

[![Built with Claude Code](https://img.shields.io/badge/Built%20with-Claude%20Code-orange?style=for-the-badge)](https://claude.ai/claude-code)
[![MVP Club](https://img.shields.io/badge/MVP%20Club-mvpclub.ai-blue?style=for-the-badge)](https://mvpclub.ai)

</div>

---

## The Big Idea

Job boards show you everything. This tool shows you what matters.

```
   Discover          Filter           Score            Report
┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐
│  Checks 5  │  │  Instantly  │  │Claude reads │  │ Ranked list│
│ job boards │→ │  removes    │→ │ each job &  │→ │with scores,│
│  + 57 ATS  │  │  mismatches │  │scores 0-100│  │  reasoning │
│  + Google  │  │             │  │  for YOU   │  │ & apply links│
└────────────┘  └────────────┘  └────────────┘  └────────────┘
  AUTOMATIC        INSTANT        AI-POWERED      YOUR RESULTS
```

A typical run scans **2,000+ jobs**, filters down to a few hundred, and scores the best matches — all automatically. You get a ranked report with scores, reasoning, salary estimates, network connections, and apply links.

---

## What Makes It Smart

| | Feature | How it works |
|---|---|---|
| 🎯 | **Scores on fit, not keywords** | Claude reads the full job description and compares it to your career story — skills, experience, and where you're headed. |
| 🤝 | **Knows who you know** | Upload your LinkedIn connections and the tool flags when you know someone at a company with an open role. Those jobs get boosted. |
| 💰 | **Reads between the salary lines** | Even when a job doesn't list pay, Claude estimates whether it's above or below your target based on the company and role level. |
| 📝 | **Tells you why** | Every score includes reasoning — what matches, what doesn't, and what to address in your application. It's a cheat sheet for your cover letter. |

### Scoring Scale

```
 0━━━━━━━━━━━39 ┃ 40━━━━━59 ┃ 60━━━━74 ┃ 75━━━━89 ┃ 90━━100
   Not for you   │    Meh    │  Worth   │  Strong  │  Apply
                 │           │  a look  │  match   │   now
```

---

## Getting Started

You need two things: **Claude Code** on your machine and an **Anthropic API key** from [console.anthropic.com](https://console.anthropic.com).

### Step 1: Clone

```bash
git clone https://github.com/hasmatt1066/jobsearchtool.git
cd jobsearchtool
```

### Step 2: Open Claude Code

```bash
claude
```

### Step 3: Just talk

That's it. Claude Code detects that you're new and walks you through everything — installs dependencies, asks about your career, builds your profile, and gets you running. No config files to edit. No commands to memorize.

> **You talk. Claude does the rest.**

---

## What Setup Looks Like

Setup is a conversation, not a config file.

> **Claude Code:** Welcome! I see this is your first time using the job search tool. Let me get you set up. Do you have an Anthropic API key?
>
> **You:** Yeah, here it is: sk-ant-...
>
> **Claude Code:** Got it, saved. Now let's build your profile. What's your name and where are you based?
>
> **You:** Sarah Chen, I'm in Austin TX
>
> **Claude Code:** Great! Are you looking for remote roles, or open to on-site?
>
> **You:** Remote preferred but I'd do hybrid

Claude keeps asking — your target titles, top skills, career accomplishments, salary floor, industries you're interested in. Then it builds your profile and shows you a summary:

> **Claude Code:** Here's your profile:
>
> **Sarah Chen** — Austin, TX (remote preferred)
> Targeting: Product Manager, Senior PM, Director of Product
> Salary floor: $160k
> Top skills: Product Strategy, Developer Tools, Platform Growth...
>
> Want to change anything, or should we run your first search?
>
> **You:** Looks good, let's go!

---

## Things You Can Say

Once you're set up, just talk to Claude Code in plain English.

### Find Jobs

| You say | Claude does |
|---|---|
| "Run a search" | Scans all sources, scores matches, generates a report |
| "Search for AI product roles at startups" | Runs a targeted search and scores results |

### Read Results

| You say | Claude does |
|---|---|
| "What did you find?" | Summarizes your top matches with scores and reasoning |
| "Which jobs have network connections?" | Filters for jobs where you know someone |
| "Tell me more about the Anthropic job" | Gives detailed breakdown of that specific match |

### Update Your Profile

| You say | Claude does |
|---|---|
| "Add AI Strategy to my skills" | Updates your profile |
| "Change my salary floor to $180k" | Adjusts your minimum and future scoring |
| "I found my dream job posting, here it is..." | Saves it as your reference job to calibrate scoring |

### Manage Your Search

| You say | Claude does |
|---|---|
| "Start monitoring Stripe's career page" | Detects their ATS and adds them to your list |
| "I'm getting too many mediocre matches" | Raises your score threshold |
| "How's my search going overall?" | Shows stats — jobs scanned, top queries, network size |

---

## What a Report Looks Like

You don't need to read raw files. Just ask "what did you find?" and Claude gives you a summary like this:

> I found **64 matches** after scanning 2,142 jobs. Here are your top 3:
>
> **1. AI Adoption Manager at OpenAI — 95/100**
> Near-perfect match. Focuses on AI adoption, enablement, and training design. They want hands-on workshop delivery and community building — right in your wheelhouse. Salary likely $150k-$200k+.
> *🤝 You know Jane Doe there (Senior PM).*
> Gap: Based in DC, not remote.
>
> **2. Training Content Architect at Anthropic — 95/100**
> Exceptional fit. AI-augmented learning systems, modular content architecture, train-the-trainer programs. Matches your prototyping experience and coaching style.
> *🤝 You know Raj Agarwal there (Member of Technical Staff).*
> Gap: Role is in SF/NYC, not remote.
>
> **3. AI Deployment Manager at OpenAI — 92/100**
> Designing hands-on workshops, driving measurable adoption, translating AI capabilities into practical workflows. Strong salary signal above your floor.
> Gap: Hybrid in NYC (3 days/week).
>
> Want me to go deeper on any of these?

---

## What to Do with Results

| | Action | Why |
|---|---|---|
| 🎯 | **Chase the 90+ scores** | They're rare. When one shows up, it's genuinely worth your attention. |
| 🤝 | **Reach out to connections first** | A warm intro is worth 10 cold applications. Message them before applying. |
| 📝 | **Use the reasoning in your cover letter** | Claude tells you exactly what overlaps and gaps exist. Lead with the overlaps. |
| 🔄 | **Keep tuning your profile** | If roles you like score low, tell Claude Code to adjust your skills or target titles. |

---

## Bonus: LinkedIn Data

Two optional upgrades that make the tool smarter:

**Your connections** — Export from LinkedIn (Settings → Data Privacy → Get a copy of your data → Connections) and tell Claude Code where the file is. Every job where you know someone at the company gets flagged.

**Companies you follow** — If your LinkedIn export includes Saved Jobs or Company Follows, tell Claude Code to expand your monitoring list. It auto-detects which career pages it can poll.

---

## Your Data Stays Yours

Your profile, API keys, LinkedIn connections, and search results **never leave your machine**. Everything personal is gitignored — the tool works locally and only you see your results.

---

<div align="center">

**[MVP Club](https://mvpclub.ai)** — Stop learning AI. Start building with it.

</div>
