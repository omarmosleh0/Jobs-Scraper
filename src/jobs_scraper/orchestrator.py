"""Main orchestration: scrape -> classify -> dedup -> store -> notify."""

import logging
from datetime import datetime

from jobs_scraper.ai import DigestGenerator, JobClassifier, JobEmbedder, RelevanceScorer
from jobs_scraper.config import load_companies, load_preferences
from jobs_scraper.dedup import content_hash, deduplicate
from jobs_scraper.models import Job
from jobs_scraper.normalizer import normalize_job
from jobs_scraper.notifications import TelegramNotifier
from jobs_scraper.scrapers import get_scraper
from jobs_scraper.storage import SupabaseStorage

logger = logging.getLogger(__name__)

TARGET_CATEGORIES = {"data", "ai_ml", "backend", "software_engineer"}


def run(
    sources: list[str] | None = None,
    dry_run: bool = False,
    skip_ai: bool = False,
    skip_relevance: bool = False,
    use_ai_digest: bool = True,
) -> dict:
    """
    Run full pipeline: scrape, classify, deduplicate, store, notify.
    Returns summary dict.
    """
    companies_config = load_companies()
    prefs = load_preferences()
    job_boards = companies_config.get("job_boards", [])
    companies = companies_config.get("companies", [])

    # Build scrape targets: job_boards + companies
    targets = [{"name": jb.get("name"), "config": jb.get("config", {})} for jb in job_boards]
    targets += [
        {"name": c.get("scraper"), "config": {**c.get("config", {}), "company_name": c.get("name")}}
        for c in companies
    ]

    if sources:
        targets = [t for t in targets if t["name"] in sources]
    if not targets:
        logger.warning("No sources to scrape")
        return {"status": "no_sources", "jobs_found": 0, "new_jobs": 0}

    all_jobs: list[Job] = []
    errors: list[str] = []

    # 1. Scrape
    for target in targets:
        name = target.get("name", "")
        scraper = get_scraper(name)
        if not scraper:
            errors.append(f"Unknown scraper: {name}")
            continue
        config = target.get("config", {})
        try:
            jobs = scraper.scrape(config)
            for j in jobs:
                j = normalize_job(j)
                all_jobs.append(j)
            logger.info("%s: scraped %d jobs", name, len(jobs))
        except Exception as e:
            errors.append(f"{name}: {e}")
            logger.exception("Scraper %s failed", name)

    if not all_jobs:
        return {"status": "no_jobs", "jobs_found": 0, "new_jobs": 0, "errors": errors}

    # 2. Classify (AI)
    classifier = JobClassifier()
    for job in all_jobs:
        if not skip_ai:
            try:
                cat, conf = classifier.classify(job)
                job.category = cat
                job.category_confidence = conf
            except Exception as e:
                logger.warning("Classification failed for %s: %s", job.title, e)
                job.category = "other"
                job.category_confidence = 0.5

    # 2b. Filter by category - only keep data, ai_ml, backend, software_engineer (exclude "other")
    if not skip_ai:
        before = len(all_jobs)
        all_jobs = [j for j in all_jobs if j.category in TARGET_CATEGORIES]
        filtered = before - len(all_jobs)
        if filtered > 0:
            logger.info("Filtered out %d jobs (category=other)", filtered)
        if not all_jobs:
            return {"status": "all_filtered", "jobs_found": before, "new_jobs": 0, "errors": errors}

    # 3. Embeddings
    embedder = None
    try:
        embedder = JobEmbedder()
        for job in all_jobs:
            job.embedding = embedder.embed(job)
    except Exception as e:
        logger.warning("Embeddings disabled: %s", e)

    # 4. Deduplicate
    storage = SupabaseStorage() if not dry_run else None
    existing = set()
    if storage:
        hashes = [content_hash(j) for j in all_jobs]
        existing = storage.get_existing_hashes(hashes)
    unique_jobs = deduplicate(all_jobs, existing, embedder=embedder)

    # 5. Store
    new_jobs: list[Job] = []
    inserted_ids: list[str] = []
    if storage and not dry_run:
        for job in unique_jobs:
            h = content_hash(job)
            try:
                row = storage.insert_job(job, h)
                if row:
                    new_jobs.append(job)
                    if row.get("id"):
                        inserted_ids.append(row["id"])
            except Exception as e:
                logger.error("Store failed for %s: %s", job.title, e)
                errors.append(f"store: {e}")

    # 5b. Relevance scoring (Phase 2)
    if new_jobs and not skip_relevance:
        scorer = RelevanceScorer()
        for job in new_jobs:
            try:
                job.relevance_score = scorer.score(job)
            except Exception as e:
                logger.debug("Relevance score failed for %s: %s", job.title, e)
        new_jobs.sort(key=lambda j: (j.relevance_score or 0), reverse=True)

    # 6. Notify (Telegram)
    if not dry_run and new_jobs:
        notifier = TelegramNotifier()
        notifier.send_jobs(new_jobs)
        if use_ai_digest:
            digest_gen = DigestGenerator()
            summary_text = digest_gen.generate(new_jobs)
            notifier.send_summary_text(summary_text)
        else:
            notifier.send_summary(new_jobs)
        if inserted_ids:
            storage.mark_notified(inserted_ids)

    return {
        "status": "success" if not errors else "partial",
        "jobs_found": len(all_jobs),
        "new_jobs": len(new_jobs),
        "errors": errors,
    }
