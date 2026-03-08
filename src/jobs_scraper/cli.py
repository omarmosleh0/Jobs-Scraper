"""CLI entry point."""

import logging
import sys

import typer

from jobs_scraper.orchestrator import run
from jobs_scraper.scrapers import list_scrapers

app = typer.Typer(help="Jordan Tech Jobs Scraper - AI-powered job monitoring")


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


@app.command("run")
def run_cmd(
    sources: list[str] = typer.Option(
        None,
        "--source",
        "-s",
        help="Scrape only these sources (e.g. bayt, akhtaboot, workable). Default: all.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Don't store or notify, just scrape and classify."),
    skip_ai: bool = typer.Option(False, "--skip-ai", help="Skip AI classification (use keyword fallback only)."),
    skip_relevance: bool = typer.Option(False, "--skip-relevance", help="Skip relevance scoring."),
    no_ai_digest: bool = typer.Option(False, "--no-ai-digest", help="Use simple summary instead of AI digest."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging."),
):
    """Run the job scraper pipeline."""
    setup_logging(verbose)
    result = run(
        sources=sources,
        dry_run=dry_run,
        skip_ai=skip_ai,
        skip_relevance=skip_relevance,
        use_ai_digest=not no_ai_digest,
    )
    typer.echo(f"Jobs found: {result['jobs_found']}, New: {result['new_jobs']}")
    if result.get("errors"):
        for e in result["errors"]:
            typer.echo(f"  Error: {e}", err=True)
    raise typer.Exit(0 if result["status"] in ("success", "partial", "no_jobs") else 1)


@app.command()
def list_sources():
    """List available scraper sources."""
    sources = list_scrapers()
    typer.echo("Available sources: " + ", ".join(sources))


if __name__ == "__main__":
    app()
