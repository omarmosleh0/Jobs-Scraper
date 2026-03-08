"""Normalize job data across different sources."""

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from jobs_scraper.models import Job

TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "ref", "fbclid"}


def normalize_url(url: str) -> str:
    """Normalize URL: strip tracking params, ensure https."""
    if not url or not url.strip():
        return ""
    url = url.strip()
    if url.startswith("//"):
        url = "https:" + url
    elif not url.startswith("http"):
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.query:
        params = parse_qs(parsed.query, keep_blank_values=True)
        filtered = {k: v for k, v in params.items() if k.lower() not in TRACKING_PARAMS}
        query = urlencode(filtered, doseq=True)
        url = urlunparse(parsed._replace(query=query))
    return url


def normalize_job(job: Job) -> Job:
    """Normalize a job's fields for consistency."""
    if job.url:
        job = job.model_copy(update={"url": normalize_url(job.url)})
    if job.company:
        job = job.model_copy(update={"company": job.company.strip()})
    if job.title:
        job = job.model_copy(update={"title": job.title.strip()})
    return job
