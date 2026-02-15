"""
Fit scoring module - evaluates job descriptions against Matthew's profile
using the Anthropic Python SDK.
"""

import json
import time
import logging

import anthropic

logger = logging.getLogger(__name__)

SCORING_SYSTEM_PROMPT = """You are a job-fit evaluator. You will be given a candidate profile and a job description. Your task is to score how well the job matches the candidate.

Return ONLY a valid JSON object. No markdown, no explanation, no code fences. Just the JSON.

## Scoring Rubric

- 90-100: Near-perfect match. The role explicitly involves AI enablement/adoption, learning/training design, or coaching teams on AI workflows. Correct seniority level (Manager/Director). Strong alignment with the candidate's core mission.
- 75-89: Strong match. At least 2 of the 3 core pillars are present (AI enablement, learning/training design, product/change management). Minor gaps in seniority or domain.
- 60-74: Moderate match. Clear entry points exist for the candidate's skills, but the role emphasizes different primary aspects. The candidate could credibly apply but would need to frame their experience carefully.
- 40-59: Weak match. Some overlapping skills or keywords, but the role is fundamentally different from the candidate's trajectory.
- 0-39: Poor match. Little to no meaningful overlap.

## Candidate Sweet Spot

The ideal role for this candidate has:
- AI adoption/enablement as the PRIMARY mission (not a side responsibility)
- Learning design combined with AI tooling — designing how people learn to use AI
- Coaching teams on AI workflows through hands-on practice
- Manager or Director level seniority (NOT individual contributor, NOT VP/C-suite)
- Base salary of $135k or above

## Critical Context About the Candidate

- The candidate BUILDS with AI tools. They do vibe coding, use Claude Code, and create working prototypes. They are not a pure strategist who only writes decks.
- They coach through hands-on practice and demonstration, not just theory.
- Their background is learning/education moving toward AI enablement. This is a career pivot INTO AI, not out of it.
- They are NOT a software engineer, data scientist, or ML engineer. Do not score engineering roles highly.
- They are NOT looking for pure HR/compliance L&D roles (mandatory training, onboarding logistics, LMS administration). These should score low.
- Remote work is strongly preferred. Fully on-site roles should be penalized slightly.
- Network connections at a company are a meaningful advantage. Having connections who can provide referrals or introductions should be treated as a positive signal. For borderline jobs (scoring 55-70), the presence of strong network connections (especially in relevant departments) can justify a 3-5 point boost. This should NOT override poor fit — a bad match with connections is still a bad match.

## Required JSON Output Schema

{
    "fit_score": <integer 0-100>,
    "reasoning": "<2-3 sentences explaining the score>",
    "salary_signal": "<one of: explicitly_listed | likely_above_floor | likely_below_floor | unknown>",
    "salary_details": "<string with salary info if found, or null>",
    "innovation_signal": "<one of: high | medium | low>",
    "seniority_match": "<one of: target | stretch | below>",
    "key_overlaps": ["<2-4 strings listing areas of alignment>"],
    "key_gaps": ["<strings listing areas of misalignment>"]
}
"""

SCORING_USER_PROMPT_TEMPLATE = """## Candidate Profile
{profile_json}

## Reference: Candidate's Current/Recent Role Context
{verisk_reference}

## Job to Evaluate

**Title:** {job_title}
**Company:** {company}
**Location:** {location}
**Date Posted:** {date_posted}

### Job Description
{job_description}

## Network Context
{network_context}

Evaluate this job against the candidate profile and return ONLY the JSON object."""


def _truncate_description(text: str, max_chars: int = 4000) -> str:
    """Truncate a job description to a maximum character length.

    Attempts to break at a sentence boundary near the limit to avoid
    cutting off mid-word or mid-sentence. Falls back to a hard cut
    if no suitable boundary is found.
    """
    if not text or len(text) <= max_chars:
        return text or ""

    # Try to find a sentence-ending boundary near the limit
    truncated = text[:max_chars]
    last_period = truncated.rfind(". ")
    last_newline = truncated.rfind("\n")
    break_point = max(last_period, last_newline)

    if break_point > max_chars * 0.75:
        return truncated[: break_point + 1].rstrip()

    return truncated.rstrip()


class FitScorer:
    """Scores job descriptions against the candidate profile using Claude."""

    def __init__(self, settings: dict, profile: dict, verisk_reference: dict):
        """Initialize the scorer.

        Args:
            settings: Configuration dict. Relevant keys:
                - model: Anthropic model name (default "claude-sonnet-4-5-20250929")
                - score_threshold: Minimum fit_score to keep (default 60)
                - max_description_chars: Truncation limit (default 4000)
            profile: Candidate profile dict to include in prompts.
            verisk_reference: Context about the candidate's current/recent role.
        """
        self.client = anthropic.Anthropic()
        self.model = settings.get("claude_model", "claude-sonnet-4-5-20250929")
        self.score_threshold = settings.get("score_threshold", 60)
        self.max_description_chars = settings.get("description_max_chars", 4000)
        self.profile = profile
        self.verisk_reference = verisk_reference

    def score_job(self, job: dict, connections: list[dict] | None = None) -> dict | None:
        """Score a single job against the candidate profile.

        Args:
            job: Job dict containing at minimum: title, company, location,
                 date_posted, description.
            connections: Optional list of LinkedIn connection dicts at this
                company. Each has first_name, last_name, position, url.

        Returns:
            The job dict augmented with scoring fields if the score meets
            the threshold, or None if it falls below or an error occurs.
        """
        description = _truncate_description(
            job.get("description", ""), self.max_description_chars
        )

        # Build network context string
        if connections:
            people = ", ".join(
                f"{c.get('first_name', '')} {c.get('last_name', '')} - {c.get('position', 'Unknown role')}"
                for c in connections
            )
            company = job.get("company", "this company")
            network_context = (
                f"The candidate has {len(connections)} connection(s) at {company}: "
                f"{people}. This means the candidate can get a warm introduction or "
                f"internal referral, which materially improves application success."
            )
        else:
            network_context = "No known connections at this company."

        user_prompt = SCORING_USER_PROMPT_TEMPLATE.format(
            profile_json=json.dumps(self.profile, indent=2),
            verisk_reference=json.dumps(self.verisk_reference, indent=2),
            job_title=job.get("title", "Unknown"),
            company=job.get("company", "Unknown"),
            location=job.get("location", "Unknown"),
            date_posted=job.get("date_posted", "Unknown"),
            job_description=description,
            network_context=network_context,
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=SCORING_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )

            response_text = response.content[0].text

            # Strip markdown code fences if present
            stripped = response_text.strip()
            if stripped.startswith("```"):
                # Remove opening fence (```json or ```)
                stripped = stripped.split("\n", 1)[1] if "\n" in stripped else stripped[3:]
                # Remove closing fence
                if stripped.rstrip().endswith("```"):
                    stripped = stripped.rstrip()[:-3].rstrip()
            response_text = stripped

            score_data = json.loads(response_text)

            # Validate required fields
            fit_score = int(score_data["fit_score"])
            score_data["fit_score"] = fit_score

            # Merge scoring fields into the job dict
            job["fit_score"] = fit_score
            job["reasoning"] = score_data.get("reasoning", "")
            job["salary_signal"] = score_data.get("salary_signal", "unknown")
            job["salary_details"] = score_data.get("salary_details")
            job["innovation_signal"] = score_data.get("innovation_signal", "low")
            job["seniority_match"] = score_data.get("seniority_match", "below")
            job["key_overlaps"] = score_data.get("key_overlaps", [])
            job["key_gaps"] = score_data.get("key_gaps", [])

            if fit_score >= self.score_threshold:
                logger.debug(
                    "Job passed threshold: %s at %s (score=%d)",
                    job.get("title"),
                    job.get("company"),
                    fit_score,
                )
                return job

            logger.debug(
                "Job below threshold: %s at %s (score=%d, threshold=%d)",
                job.get("title"),
                job.get("company"),
                fit_score,
                self.score_threshold,
            )
            return None

        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse scoring response as JSON for '%s' at '%s': %s",
                job.get("title"),
                job.get("company"),
                e,
            )
            return None
        except KeyError as e:
            logger.error(
                "Missing required field in scoring response for '%s' at '%s': %s",
                job.get("title"),
                job.get("company"),
                e,
            )
            return None
        except anthropic.APIError as e:
            logger.error(
                "Anthropic API error scoring '%s' at '%s': %s",
                job.get("title"),
                job.get("company"),
                e,
            )
            return None

    def score_batch(self, jobs: list[dict], network_matcher=None) -> list[dict]:
        """Score a batch of jobs and return those above the threshold.

        Jobs with missing or very short descriptions (< 100 chars) are
        skipped. Results are sorted by fit_score in descending order.

        If a NetworkMatcher is provided, connections are looked up before
        each scoring call and passed as context to Claude. Connection
        data is also attached to the job dict for downstream reporting.

        Args:
            jobs: List of job dicts to evaluate.
            network_matcher: Optional NetworkMatcher instance for connection
                lookups. If None, jobs are scored without network context.

        Returns:
            List of scored job dicts that met the threshold, sorted by
            fit_score descending.
        """
        results = []
        total = len(jobs)
        skipped = 0

        for i, job in enumerate(jobs):
            description = job.get("description", "")
            if not description or len(description) < 100:
                logger.debug(
                    "Skipping job with short/missing description: %s at %s",
                    job.get("title"),
                    job.get("company"),
                )
                skipped += 1
                continue

            # Look up network connections before scoring
            connections = None
            if network_matcher:
                connections = network_matcher.find_connections(
                    job.get("company", "")
                )
                job["network_connections"] = connections

            scored = self.score_job(job, connections=connections)
            if scored is not None:
                results.append(scored)

            # Log progress every 10 jobs
            processed = i + 1
            if processed % 10 == 0:
                logger.info(
                    "Scoring progress: %d/%d jobs processed (%d passed, %d skipped)",
                    processed,
                    total,
                    len(results),
                    skipped,
                )

            # Rate-limit between API calls
            if i < total - 1:
                time.sleep(0.5)

        logger.info(
            "Scoring complete: %d/%d jobs passed threshold (score >= %d), %d skipped",
            len(results),
            total,
            self.score_threshold,
            skipped,
        )

        results.sort(key=lambda j: j.get("fit_score", 0), reverse=True)
        return results
