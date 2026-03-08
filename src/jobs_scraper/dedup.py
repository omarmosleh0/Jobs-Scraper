"""Deduplication engine: URL hash, content hash, embedding similarity."""

import hashlib
import logging
from collections import defaultdict

from jobs_scraper.ai.embeddings import JobEmbedder
from jobs_scraper.models import Job
from jobs_scraper.normalizer import normalize_url

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.9


def content_hash(job: Job) -> str:
    """Generate content hash for deduplication."""
    key = f"{job.company.lower()}|{job.title.lower()}|{(job.location or '').lower()}"
    return hashlib.sha256(key.encode()).hexdigest()


def url_hash(url: str) -> str:
    """Hash normalized URL."""
    normalized = normalize_url(url)
    return hashlib.sha256(normalized.encode()).hexdigest()


def deduplicate(
    jobs: list[Job],
    existing_hashes: set[str],
    embedder: JobEmbedder | None = None,
    use_embeddings: bool = True,
) -> list[Job]:
    """
    Remove duplicates from job list.
    - Skip if content_hash in existing_hashes
    - Skip if same company + embedding similarity > threshold
    """
    seen_hashes: set[str] = set(existing_hashes)
    seen_by_company: dict[str, list[tuple[Job, list[float]]]] = defaultdict(list)
    unique: list[Job] = []

    if embedder is None and use_embeddings:
        try:
            embedder = JobEmbedder()
        except Exception as e:
            logger.warning("Embedder not available, skipping embedding dedup: %s", e)
            embedder = None
            use_embeddings = False

    for job in jobs:
        h = content_hash(job)
        if h in seen_hashes:
            continue

        # Embedding similarity check for same company
        if use_embeddings and embedder and job.company:
            company_key = job.company.lower().strip()
            emb = embedder.embed(job)
            is_dup = False
            for existing_job, existing_emb in seen_by_company.get(company_key, []):
                sim = JobEmbedder.cosine_similarity(emb, existing_emb)
                if sim >= SIMILARITY_THRESHOLD:
                    is_dup = True
                    break
            if is_dup:
                continue
            seen_by_company[company_key].append((job, emb))

        seen_hashes.add(h)
        unique.append(job)

    return unique
