<a id="readme-top"></a>

<div align="center">

<br>

# You Already Know What You Want. The Problem Is Finding It.

**An AI-powered job search tool that scans thousands of postings, scores them against your career story, and tells you which ones are actually worth your attention.**

You talk to Claude Code. It handles the rest.

<br>

[![Built with Claude Code](https://img.shields.io/badge/Built%20with-Claude%20Code-D97706?style=for-the-badge&logo=anthropic&logoColor=white)](https://claude.ai/claude-code)
[![MVP Club](https://img.shields.io/badge/MVP%20Club-mvpclub.ai-114083?style=for-the-badge)](https://mvpclub.ai)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-34D399?style=for-the-badge)](LICENSE)

<br>

[The Problem](#the-problem) &middot; [Your First Win](#your-first-win) &middot; [The Flywheel](#the-flywheel-why-it-gets-better) &middot; [Things You Can Say](#things-you-can-say) &middot; [Cost & Quality](#tuning-cost--quality) &middot; [LinkedIn Data](#make-it-smarter-linkedin-data)

</div>

---

<details>
<summary><strong>Table of Contents</strong></summary>

- [The Problem](#the-problem)
- [What If You Could Read Every Single One?](#what-if-you-could-read-every-single-one)
- [Your First Win](#your-first-win)
- [What Setup Looks Like](#what-setup-looks-like)
- [The Flywheel: Why It Gets Better](#the-flywheel-why-it-gets-better)
- [What the Scores Mean](#what-the-scores-mean)
- [Things You Can Say](#things-you-can-say)
- [Tuning Cost & Quality](#tuning-cost--quality)
- [Make It Smarter: LinkedIn Data](#make-it-smarter-linkedin-data)
- [What to Do With Results](#what-to-do-with-results)
- [Your Data Stays Yours](#your-data-stays-yours)

</details>

---

## The Problem

You know what a great job looks like when you see it. The problem isn't judgment — it's volume. There are thousands of postings across dozens of boards, and the good ones are buried under noise. You can't read them all, so you use keyword filters that miss context, or you scroll until your eyes glaze over, or you just apply to whatever shows up first.

Meanwhile, the perfect role — the one that actually fits your career trajectory — sits on page 4 of a board you didn't check.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## What If You Could Read Every Single One?

That's what this tool does. It scans 2,000+ jobs across five major boards, 65+ company career pages, and Google — then Claude reads each one and scores it against your actual career story. Not keywords. Your story: where you've been, what you're good at, where you're headed.

```mermaid
flowchart LR
    A["🔍 Discover\n5 job boards + 65 ATS + Google"] --> B["⚡ Filter\nLocation, keywords, direction"]
    B --> C["🧠 Score\nClaude reads & scores 0–100"]
    C --> D["📊 Report\nRanked list with reasoning"]
    style A fill:#114083,color:#fff,stroke:#fff
    style B fill:#D97706,color:#fff,stroke:#fff
    style C fill:#D97706,color:#fff,stroke:#fff
    style D fill:#34D399,color:#081F3F,stroke:#081F3F
```

You get a ranked list. The best matches float to the top with scores, reasoning, salary estimates, and apply links. If you uploaded your LinkedIn connections, it flags when you know someone at the company.[^1]

> [!NOTE]
> A typical run scans **2,000+ jobs**, filters down to a few hundred, and scores the best matches — all automatically. The discovery and filtering are free. The AI scoring step uses the Claude API — cost depends on your [model and settings](#tuning-cost--quality), from under $1 to a few dollars per run.

### Three discovery sources

| Source | What it covers | Requires |
|---|---|---|
| **JobSpy** | Indeed, LinkedIn, Glassdoor, Google Jobs, ZipRecruiter | Nothing (built-in) |
| **ATS feeds** | 65+ company career pages (Greenhouse, Lever, Ashby, Workday) | Nothing (built-in) |
| **Google search** | Niche boards, career pages, ATS postings that the other sources miss | [SearchAPI key](https://www.searchapi.io) |

Without a SearchAPI key, the tool still searches five major job boards and 65+ company career pages directly. The Google search layer adds coverage for roles posted on smaller boards or company sites that aren't in the ATS monitoring list.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Your First Win

The fastest way to understand what this tool does is to use it.

<table>
<tr>
<td width="50%">

### What you need

| What | Where to get it |
|---|---|
| **Your resume** (PDF, DOCX, or text) | Wherever you keep it — drop it in the project folder |
| **An Anthropic API key** | [console.anthropic.com](https://console.anthropic.com) |
| **A SearchAPI key** *(optional)* | [searchapi.io](https://www.searchapi.io) — 100 free searches/month |

The Anthropic key is required — it powers the AI scoring. The SearchAPI key enables Google search discovery, which finds jobs on niche boards and career pages that the main job boards miss. You can skip it and add it later, but your searches will be more thorough with it.

</td>
<td width="50%">

### Clone, open, talk

```bash
git clone https://github.com/MVP-Club-AI/mattjobsearchtool.git
cd mattjobsearchtool
claude
```

Claude Code detects that you're new and walks you through everything — installs dependencies, reads your resume, builds your profile, and gets you running. No config files. No commands to memorize.

</td>
</tr>
</table>

> [!TIP]
> Drop your resume into the project folder **before** running <kbd>claude</kbd>. When Claude Code can read your resume, setup goes from 10 questions to 3 confirmations — it already knows your name, location, skills, and experience.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## What Setup Looks Like

Setup is a conversation, not a config file. Claude does the heavy lifting.

> **Claude Code:** I've read your resume. You're Sarah Chen, based in Austin, with 8 years in product management. Are you looking for remote roles?
>
> **You:** Remote preferred but I'd do hybrid.
>
> **Claude Code:** What kind of roles are you targeting? These might be different from your current title — where do you want to go?
>
> **You:** Product manager, senior PM, director of product... mostly at tech companies focused on AI or developer tools.

Claude builds your profile from this conversation, confirms it with you, and asks if you want to run your first search. A few minutes later:

> I found **64 matches** after scanning 2,142 jobs. Your best match is a **95/100** at OpenAI — an AI Adoption Manager role focused on enablement and training design. Salary likely $150k-$200k+.
>
> Want me to go deeper on any of these?

${\color{green}\text{That's your first win.}}$ You went from zero to a scored, ranked list of real opportunities. Everything after this is tuning.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## The Flywheel: Why It Gets Better

Your first search gives you a baseline. The real value comes from iteration.

```mermaid
flowchart LR
    A["🔄 Run a search"] --> B["👀 See results\nSome scores surprise you"]
    B --> C["🎯 Tune your profile\nAdd skills, adjust targets"]
    C --> D["📈 Sharper results\nScoring reflects what you care about"]
    D --> A
    style A fill:#D97706,color:#fff,stroke:#fff
    style B fill:#114083,color:#fff,stroke:#fff
    style C fill:#114083,color:#fff,stroke:#fff
    style D fill:#34D399,color:#081F3F,stroke:#081F3F
```

Every interaction teaches the system more about what you want. The tool doesn't just find jobs — it helps you clarify what you're actually looking for.

```diff
+ "Add AI Strategy to my skills"        → profile updated, next search is sharper
+ "I found my dream job, here it is..." → scoring calibrated around your ideal role
+ "Raise my salary floor to $180k"      → low-pay roles filtered out automatically
- "I'm getting too many mediocre matches" → score threshold raised, noise reduced
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## What the Scores Mean

<table>
<tr>
<td width="20%" align="center">

**0 – 39**
<br>
${\color{red}\text{Not for you}}$

</td>
<td width="20%" align="center">

**40 – 59**
<br>
${\color{orange}\text{Meh}}$

</td>
<td width="20%" align="center">

**60 – 74**
<br>
${\color{orange}\text{Worth a look}}$

</td>
<td width="20%" align="center">

**75 – 89**
<br>
${\color{green}\text{Strong match}}$

</td>
<td width="20%" align="center">

**90 – 100**
<br>
${\color{green}\text{Apply now}}$

</td>
</tr>
</table>

Every score comes with reasoning — what matched, what didn't, and what you'd need to address in your application. This is a cheat sheet for your cover letter: lead with the overlaps, address the gaps proactively.[^2]

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Things You Can Say

Once you're set up, just talk to Claude Code in plain English.

<details>
<summary><strong>🔍 Find jobs</strong></summary>

<br>

| You say | What happens |
|---|---|
| <kbd>Run a search</kbd> | Scans all sources, scores matches, generates a report |
| <kbd>Search for AI product roles at startups</kbd> | Runs a targeted search and scores results |

</details>

<details>
<summary><strong>📊 Read results</strong></summary>

<br>

| You say | What happens |
|---|---|
| <kbd>What did you find?</kbd> | Summarizes your top matches with scores and reasoning |
| <kbd>Which jobs have network connections?</kbd> | Filters for jobs where you know someone |
| <kbd>Tell me more about the Anthropic job</kbd> | Gives a detailed breakdown of that specific match |

</details>

<details>
<summary><strong>🎯 Tune your profile</strong></summary>

<br>

| You say | What happens |
|---|---|
| <kbd>Add AI Strategy to my skills</kbd> | Updates your profile |
| <kbd>Change my salary floor to $180k</kbd> | Adjusts your minimum and future scoring |
| <kbd>I found my dream job posting, here it is...</kbd> | Saves it as your reference job to calibrate scoring |

</details>

<details>
<summary><strong>⚙️ Manage your search</strong></summary>

<br>

| You say | What happens |
|---|---|
| <kbd>Start monitoring Stripe's career page</kbd> | Detects their ATS and adds them to your list |
| <kbd>I'm getting too many mediocre matches</kbd> | Raises your score threshold |
| <kbd>How's my search going overall?</kbd> | Shows stats — jobs scanned, top queries, network size |

</details>

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Tuning Cost & Quality

The discovery and filtering stages are free. The only cost is the **AI scoring step**, where Claude reads each job that passes the keyword filter. Three settings control how much a run costs — tell Claude Code to adjust them, or edit `config/settings.json` directly.

<table>
<tr>
<td width="33%">

### Scoring model

`claude_model`

Haiku is fast and cheap (~$0.005/job). Sonnet is more nuanced (~$0.02/job). Both follow the same rubric — the difference is how well the model handles edge cases.

</td>
<td width="33%">

### Triage strictness

`min_triage_score`

How many keyword hits a job needs before Claude scores it (1-10 scale). Higher = fewer jobs scored = lower cost. Lower = broader coverage = might catch edge cases.

</td>
<td width="33%">

### Jobs per run cap

`max_jobs_per_run`

Hard ceiling on how many jobs get sent to Claude. A predictable way to control your maximum cost per run.

</td>
</tr>
</table>

| Configuration | ~Jobs scored | ~Cost/run |
|---|---|---|
| Haiku + strict triage + 150 cap | 100-150 | **$0.50-0.75** |
| Haiku + loose triage + 300 cap | 200-300 | **$1.00-1.50** |
| Sonnet + strict triage + 150 cap | 100-150 | **$2.00-3.00** |
| Sonnet + loose triage + 500 cap | 200-500 | **$4.00-10.00** |

> [!TIP]
> Start cheap and experiment. You can always tell Claude Code <kbd>Switch to Sonnet for better scoring</kbd> or <kbd>Make my searches cheaper</kbd> — it adjusts the settings for you and tells you the cost impact.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Make It Smarter: LinkedIn Data

Your LinkedIn export is the single highest-leverage upgrade. It unlocks two things:

<table>
<tr>
<td width="50%">

### 🤝 Network matching

Your connections let the tool flag every job where you know someone. A warm intro changes everything, and the scoring engine knows it — borderline jobs get boosted when you have a connection.

</td>
<td width="50%">

### 🏢 ATS expansion

Your Saved Jobs and Company Follows tell the tool which companies you care about. It auto-detects their career pages and adds them to monitoring, so you never miss a posting.

</td>
</tr>
</table>

> [!TIP]
> **How to get it:** LinkedIn → <kbd>Settings</kbd> → <kbd>Data Privacy</kbd> → <kbd>Get a copy of your data</kbd>. Select "Connections" at minimum. Also select "Jobs" and "Company Follows" for the full benefit. LinkedIn emails you a ZIP within ~24 hours. Unzip it into the project folder.

You can add this at any time — just tell Claude Code <kbd>I added my LinkedIn data</kbd> and it sets everything up.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## What to Do With Results

| | Action | Why |
|---|---|---|
| ${\color{green}\text{1}}$ | **Chase the 90+ scores** | They're rare. When one shows up, it's genuinely worth your attention. |
| ${\color{green}\text{2}}$ | **Reach out to connections first** | A warm intro is worth 10 cold applications. Message them before applying. |
| ${\color{green}\text{3}}$ | **Use the reasoning in your cover letter** | Claude tells you exactly what overlaps and gaps exist. Lead with the overlaps. |
| ${\color{green}\text{4}}$ | **Keep tuning your profile** | If roles you like score low, tell Claude Code to adjust. The next search will be sharper. |

> [!WARNING]
> Scores above 90 are rare — most searches produce only a handful. When one shows up, don't let it sit. These are the roles that genuinely match your trajectory.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Your Data Stays Yours

> [!IMPORTANT]
> Your profile, API keys, LinkedIn connections, and search results **never leave your machine**. Everything personal is gitignored — the tool works locally and only you see your results.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

<div align="center">

<br>

**[MVP Club](https://mvpclub.ai)** — Stop learning AI. Start building with it.

<br>

</div>

<!-- FOOTNOTES -->

[^1]: Network matching requires a LinkedIn data export. See [Make It Smarter: LinkedIn Data](#make-it-smarter-linkedin-data) for setup instructions.

[^2]: Scoring uses Claude's semantic understanding of job descriptions, not keyword matching. The rubric weighs mission alignment, skill overlap, seniority fit, and salary signals.
