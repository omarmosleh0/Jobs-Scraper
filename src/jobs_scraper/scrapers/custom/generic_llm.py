"""Generic LLM scraper: fetch career page + extract jobs via Ollama. Works for any custom career site."""

import logging
import re
import time
from urllib.parse import urljoin, urlparse

import httpx

from jobs_scraper.ai.extractor import JobExtractor
from jobs_scraper.models import Job
from jobs_scraper.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


def _html_to_text(html: str) -> str:
    """Strip HTML tags and normalize whitespace."""
    # Remove script, style
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Strip tags
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class GenericLLMScraper(BaseScraper):
    """Universal scraper: fetch career page, extract jobs via LLM. No per-site selectors needed."""

    name = "generic_llm"

    def scrape(self, config: dict) -> list[Job]:
        """Scrape custom career page. Config: url, company_name, css_selector (optional), locations_filter."""
        url = config.get("url", "")
        company_name = config.get("company_name", "Company")
        css_selector = config.get("css_selector", "")
        locations_filter = config.get("locations_filter") or []

        if not url:
            logger.warning("GenericLLM scraper requires url")
            return []

        jobs: list[Job] = []

        try:
            # Fetch page
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                resp = client.get(url)
                resp.raise_for_status()
                html = resp.text

            # Optionally extract a section via CSS (requires parsel)
            if css_selector:
                try:
                    from parsel import Selector

                    sel = Selector(html)
                    section = sel.css(css_selector).get()
                    if section:
                        html = section
                except ImportError:
                    pass

            text = _html_to_text(html)
            if not text or len(text) < 100:
                logger.warning("GenericLLM: insufficient page content from %s", url)
                return []

            base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
            extractor = JobExtractor()
            jobs = extractor.extract_jobs(text, company_name, base_url)

            for j in jobs:
                if j.url and not j.url.startswith("http"):
                    j.url = urljoin(base_url, j.url)

            if locations_filter:
                jobs = [j for j in jobs if self._matches_location(j, locations_filter)]

        except Exception as e:
            logger.exception("GenericLLM scrape failed for %s: %s", company_name, e)
            return []

        logger.info("GenericLLM %s: extracted %d jobs", company_name, len(jobs))
        return jobs

    def _matches_location(self, job: Job, locations_filter: list) -> bool:
        if not locations_filter:
            return True
        loc_str = (job.location or "").lower() + " " + (job.title or "").lower()
        return any(loc and str(loc).lower() in loc_str for loc in locations_filter)
