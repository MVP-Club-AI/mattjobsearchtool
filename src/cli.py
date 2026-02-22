"""CLI entry point for the job search automation tool."""

import json
import logging
import os
from datetime import date, datetime
from pathlib import Path

import click

from src.state.manager import StateManager
from src.scoring.fit_scorer import FitScorer
from src.network.matcher import NetworkMatcher
from src.discovery.jobspy_search import JobSpySearch
from src.discovery.ats_feeds import ATSFeeds
from src.discovery.serper_search import SerperSearch
from src.discovery.ats_detector import extract_candidate_companies, detect_ats
from src.reporting.generator import ReportGenerator
from src.scoring.triage import triage_batch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def load_settings(path: Path) -> dict:
    """Load settings.json, resolving ENV: prefixed values from environment."""
    data = json.loads(path.read_text())
    for key, value in data.items():
        if isinstance(value, str) and value.startswith("ENV:"):
            env_var = value[4:]
            data[key] = os.environ.get(env_var, "")
            if not data[key]:
                logger.warning(f"Environment variable {env_var} not set for setting {key}")
    return data


@click.group()
@click.pass_context
def cli(ctx):
    """AI-powered job search automation tool."""
    ctx.ensure_object(dict)
    base_dir = Path(__file__).parent.parent
    ctx.obj["base_dir"] = base_dir
    ctx.obj["settings"] = load_settings(base_dir / "config" / "settings.json")
    ctx.obj["profile"] = json.loads((base_dir / "config" / "profile_index.json").read_text())
    ctx.obj["verisk_ref"] = json.loads((base_dir / "config" / "verisk_reference.json").read_text())


@cli.command()
@click.pass_context
def run(ctx):
    """Full discovery + scoring + report pipeline."""
    base_dir = ctx.obj["base_dir"]
    settings = ctx.obj["settings"]
    profile = ctx.obj["profile"]
    verisk_ref = ctx.obj["verisk_ref"]

    # Initialize shared components
    state_mgr = StateManager(str(base_dir / "data"))
    network_matcher = NetworkMatcher(str(base_dir / "data" / "connections.csv"))
    fit_scorer = FitScorer(settings, profile, verisk_ref)
    report_gen = ReportGenerator(str(base_dir / "data"))

    all_jobs = []
    source_counts = {}

    # JobSpy discovery
    click.echo("Running JobSpy discovery...")
    jobspy = JobSpySearch(settings, state_mgr)
    jobspy_results = jobspy.run_all_queries()
    all_jobs.extend(jobspy_results)
    source_counts["JobSpy"] = len(jobspy_results)
    click.echo(f"  Found {len(jobspy_results)} new jobs from JobSpy")

    # ATS feeds discovery
    click.echo("Running ATS feeds discovery...")
    ats = ATSFeeds(settings, state_mgr)
    ats_results = ats.fetch_all()
    all_jobs.extend(ats_results)
    source_counts["ATS"] = len(ats_results)
    click.echo(f"  Found {len(ats_results)} new jobs from ATS feeds")

    # Serper search discovery
    click.echo("Running Serper search...")
    serper = SerperSearch(settings, state_mgr)
    serper_results = serper.search_all()
    all_jobs.extend(serper_results)
    source_counts["Serper"] = len(serper_results)
    click.echo(f"  Found {len(serper_results)} new jobs from Serper")

    total_discovered = len(all_jobs)
    click.echo(f"\nTotal new jobs discovered: {total_discovered}")

    if not all_jobs:
        click.echo("No new jobs found. Exiting.")
        return

    # Stage 1: Fast keyword triage (free, instant)
    click.echo(f"\nRunning keyword triage + location filter on {total_discovered} jobs...")
    max_age_hours = settings.get("hours_old", 72)
    min_triage = settings.get("min_triage_score", 3)
    triaged = triage_batch(all_jobs, min_score=min_triage, max_age_hours=max_age_hours, settings=settings)
    rejected_count = total_discovered - len(triaged)
    click.echo(f"  {len(triaged)} passed triage, {rejected_count} rejected (keyword/location/age filter)")

    # Stage 2: Cap at max_jobs_per_run (triaged list is already sorted by triage score desc)
    max_jobs = settings.get("max_jobs_per_run", 500)
    if len(triaged) > max_jobs:
        scoring_batch = triaged[:max_jobs]
        remaining = triaged[max_jobs:]
        click.echo(f"  Capped at {max_jobs} for scoring, {len(remaining)} lower-ranked deferred")

        # Mark deferred jobs as seen so they don't pile up
        for job in remaining:
            state_mgr.mark_seen(job["url"], {
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "source": job.get("source", ""),
                "fit_score": None,
                "triage_score": job.get("triage_score"),
                "deferred": True,
            })
    else:
        scoring_batch = triaged

    # Mark rejected jobs as seen too
    rejected_jobs = [j for j in all_jobs if j.get("triage_score", 1) < 1]
    for job in rejected_jobs:
        state_mgr.mark_seen(job["url"], {
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "source": job.get("source", ""),
            "fit_score": None,
            "triage_score": 0,
            "rejected": True,
        })

    # Score jobs with Claude (network connections looked up inline before each score)
    click.echo(f"\nScoring {len(scoring_batch)} jobs with Claude (with network context)...")
    scored_jobs = fit_scorer.score_batch(scoring_batch, network_matcher=network_matcher)
    click.echo(f"  {len(scored_jobs)} jobs passed the score threshold (>= {settings.get('score_threshold', 60)})")

    conn_count = sum(1 for j in scored_jobs if j.get("network_connections"))
    click.echo(f"  {conn_count} jobs have network connections")

    # Mark scored batch as seen (deferred jobs already marked above)
    for job in scoring_batch:
        state_mgr.mark_seen(job["url"], {
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "source": job.get("source", ""),
            "fit_score": job.get("fit_score"),
        })

    # Record query performance
    query_stats: dict[str, dict] = {}
    for job in scoring_batch:
        q = job.get("query", "unknown")
        if q not in query_stats:
            query_stats[q] = {"found": 0, "high_score": 0, "scores": []}
        query_stats[q]["found"] += 1
        score = job.get("fit_score")
        if score is not None:
            query_stats[q]["scores"].append(score)
            if score >= settings.get("score_threshold", 60):
                query_stats[q]["high_score"] += 1

    for query, qs in query_stats.items():
        avg = sum(qs["scores"]) / len(qs["scores"]) if qs["scores"] else 0
        state_mgr.record_query_result(query, qs["found"], qs["high_score"], avg)

    # Generate report
    sources_str = ", ".join(f"{k}: {v}" for k, v in source_counts.items())
    stats = {
        "total_scanned": total_discovered,
        "sources": sources_str,
    }
    click.echo("\nGenerating report...")
    report_path = report_gen.generate(scored_jobs, stats)

    # Save state
    state_mgr.save()

    # Print summary
    click.echo("\n--- Summary ---")
    click.echo(f"Total scanned: {total_discovered}")
    click.echo(f"Passed threshold: {len(scored_jobs)}")
    click.echo(f"With network connections: {conn_count}")
    click.echo(f"Report saved: {report_path}")


@cli.command()
@click.argument("query")
@click.pass_context
def search(ctx, query):
    """Ad-hoc single query search with scoring."""
    base_dir = ctx.obj["base_dir"]
    settings = ctx.obj["settings"]
    profile = ctx.obj["profile"]
    verisk_ref = ctx.obj["verisk_ref"]

    state_mgr = StateManager(str(base_dir / "data"))

    # Run single JobSpy query
    click.echo(f"Searching for: {query}")
    jobspy = JobSpySearch(settings, state_mgr)
    results = jobspy.search_single(query)
    click.echo(f"Found {len(results)} results")

    if not results:
        click.echo("No results found.")
        return

    # Score results (with network context)
    click.echo("Scoring (with network context)...")
    fit_scorer = FitScorer(settings, profile, verisk_ref)
    network_matcher = NetworkMatcher(str(base_dir / "data" / "connections.csv"))
    scored_jobs = fit_scorer.score_batch(results, network_matcher=network_matcher)

    # Persist ad-hoc results to state (prevents re-scoring in future runs)
    for job in results:
        state_mgr.mark_seen(job["url"], {
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "source": job.get("source", ""),
            "fit_score": job.get("fit_score"),
            "query": query,
            "adhoc": True,
        })
    state_mgr.save()

    # Generate ad-hoc report with unique filename
    report_gen = ReportGenerator(str(base_dir / "data"))
    safe_query = query.replace(" ", "-").replace("/", "-")[:40]
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    report_filename = f"search-{safe_query}-{timestamp}.md"
    report_title = f"Ad-Hoc Search: {query} -- {date.today().isoformat()}"
    stats = {"total_scanned": len(results), "sources": "JobSpy (ad-hoc)"}
    report_path = report_gen.generate(scored_jobs, stats,
                                      filename=report_filename, title=report_title)

    # Save companion JSON with structured data
    json_filename = report_filename.replace(".md", ".json")
    json_path = Path(report_path).parent / json_filename
    json_data = {
        "query": query,
        "timestamp": datetime.now().isoformat(),
        "total_scanned": len(results),
        "matches": len(scored_jobs),
        "jobs": scored_jobs,
    }
    json_path.write_text(json.dumps(json_data, indent=2, default=str), encoding="utf-8")

    # Print results to console
    click.echo(f"\n--- Results ({len(scored_jobs)} passed threshold) ---")
    for job in scored_jobs:
        score = job.get("fit_score", 0)
        title = job.get("title", "Unknown")
        company = job.get("company", "Unknown")
        connections = job.get("network_connections", [])
        conn_str = ""
        if connections:
            names = [f"{c.get('first_name', '')} {c.get('last_name', '')}".strip() for c in connections]
            conn_str = f" [Network: {', '.join(names)}]"
        click.echo(f"  [{score:3d}] {title} @ {company}{conn_str}")

    click.echo(f"\nReport saved: {report_path}")
    click.echo(f"Data saved: {json_path}")


@cli.command()
@click.pass_context
def status(ctx):
    """Show current stats."""
    base_dir = ctx.obj["base_dir"]

    state_mgr = StateManager(str(base_dir / "data"))
    network_matcher = NetworkMatcher(str(base_dir / "data" / "connections.csv"))

    # State stats
    state_stats = state_mgr.stats()
    ats_config = json.loads((base_dir / "config" / "ats_companies.json").read_text())
    ats_count = len(ats_config.get("companies", []))
    reports_dir = base_dir / "data" / "reports"
    report_count = len(list(reports_dir.glob("*.md"))) if reports_dir.exists() else 0

    click.echo("--- Job Search Status ---")
    click.echo(f"Total jobs seen: {state_stats['seen_jobs']}")
    click.echo(f"ATS companies monitored: {ats_count}")
    click.echo(f"Reports generated: {report_count}")
    click.echo(f"Total query runs: {state_stats['total_query_runs']}")

    # Top performing queries
    top_queries = state_mgr.get_top_queries(5)
    if top_queries:
        click.echo("\nTop 5 performing queries:")
        for i, q in enumerate(top_queries, 1):
            click.echo(
                f"  {i}. \"{q['query']}\" "
                f"({q['total_high_score_jobs']} high-score hits, "
                f"{q['total_runs']} runs)"
            )

    # Network stats
    net_stats = network_matcher.get_stats()
    click.echo(f"\nNetwork: {net_stats['total_connections']} connections across {net_stats['unique_companies']} companies")


@cli.command("add-company")
@click.argument("company_name")
@click.option("--ats", type=click.Choice(["greenhouse", "lever", "ashby", "workday"]), required=True)
@click.option("--token", required=True, help="Board token / slug for the ATS")
@click.pass_context
def add_company(ctx, company_name, ats, token):
    """Add a company to ATS monitoring."""
    base_dir = ctx.obj["base_dir"]
    ats_path = base_dir / "config" / "ats_companies.json"

    config = json.loads(ats_path.read_text())
    companies = config.get("companies", [])

    # Check for duplicate
    for existing in companies:
        if existing.get("name", "").lower() == company_name.lower():
            click.echo(f"'{company_name}' is already in the ATS monitoring list.")
            return

    new_entry = {
        "name": company_name,
        "ats": ats,
        "board_token": token,
    }
    companies.append(new_entry)
    config["companies"] = companies
    ats_path.write_text(json.dumps(config, indent=2) + "\n")

    click.echo(f"Added {company_name} ({ats}, token: {token}) to ATS monitoring.")


@cli.command("expand-ats")
@click.argument("linkedin_dir")
@click.option("--auto", "auto_add", is_flag=True, help="Add all detected companies without prompting")
@click.pass_context
def expand_ats(ctx, linkedin_dir, auto_add):
    """Expand ATS monitoring using LinkedIn data (Saved Jobs + Company Follows).

    LINKEDIN_DIR is the path to the LinkedIn data export directory
    (e.g., LinkedinDataFeb2026/).
    """
    base_dir = ctx.obj["base_dir"]
    ats_path = base_dir / "config" / "ats_companies.json"

    config = json.loads(ats_path.read_text())
    companies = config.get("companies", [])
    existing_names = [c["name"] for c in companies]

    # Extract candidate companies from LinkedIn data
    click.echo("Extracting companies from LinkedIn data...")
    candidates = extract_candidate_companies(linkedin_dir, existing_names)

    if not candidates:
        click.echo("No new companies found in LinkedIn data.")
        return

    click.echo(f"Found {len(candidates)} companies not yet monitored.\n")

    # Probe each for ATS
    detected = []
    not_detected = []

    with click.progressbar(candidates, label="Probing ATS platforms") as bar:
        for company in bar:
            result = detect_ats(company)
            if result:
                detected.append({"name": company, **result})
            else:
                not_detected.append(company)

    # Report results
    click.echo(f"\n--- Results ---")
    click.echo(f"ATS detected: {len(detected)}")
    click.echo(f"Not detected: {len(not_detected)}")

    # Handle detected companies
    added = 0
    if detected:
        click.echo(f"\nDetected ATS platforms:")
        for entry in detected:
            click.echo(f"  {entry['name']} -> {entry['ats']} (token: {entry['board_token']})")

        if auto_add:
            for entry in detected:
                companies.append({
                    "name": entry["name"],
                    "ats": entry["ats"],
                    "board_token": entry["board_token"],
                })
                added += 1
        else:
            click.echo()
            for entry in detected:
                if click.confirm(f"Add {entry['name']} ({entry['ats']})?", default=True):
                    companies.append({
                        "name": entry["name"],
                        "ats": entry["ats"],
                        "board_token": entry["board_token"],
                    })
                    added += 1

    # Save updated config
    if added > 0:
        config["companies"] = companies
        ats_path.write_text(json.dumps(config, indent=2) + "\n")
        click.echo(f"\nAdded {added} companies to ATS monitoring (total: {len(companies)})")
    else:
        click.echo("\nNo companies added.")

    # Show undetected for manual review
    if not_detected:
        click.echo(f"\nCompanies with no ATS auto-detected (manual review needed):")
        for name in not_detected:
            click.echo(f"  - {name}")


if __name__ == "__main__":
    cli()
