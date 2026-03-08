"""ZenATS scraper. Covers Jawaker and other ZenATS (ZenHR) career sites."""

import logging
import re
import time
from urllib.parse import urljoin

from jobs_scraper.models import Job
from jobs_scraper.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class ZenATSScraper(BaseScraper):
    """Scrape jobs from ZenATS career sites (e.g. careers.jawaker.com)."""

    name = "zenats"

    def scrape(self, config: dict) -> list[Job]:
        """Scrape ZenATS careers. Config: careers_url, company_name, locations_filter."""
        careers_url = config.get("careers_url", "")
        company_name = config.get("company_name", "Company")
        locations_filter = config.get("locations_filter") or []

        if not careers_url:
            logger.warning("ZenATS scraper requires careers_url")
            return []

        jobs: list[Job] = []

        try:
            from scrapling.fetchers import Fetcher
        except ImportError:
            logger.error("Scrapling not installed. Run: pip install 'scrapling[fetchers]'")
            return []

        try:
            base = careers_url.rstrip("/")
            page = Fetcher.get(careers_url)
            if not page or not hasattr(page, "css"):
                logger.warning("ZenATS: no page content for %s", careers_url)
                return []

            page_jobs = self._parse_page(page, base, company_name)
            for j in page_jobs:
                if not locations_filter or self._matches_location(j, locations_filter):
                    jobs.append(j)

        except Exception as e:
            logger.exception("ZenATS scrape failed for %s: %s", company_name, e)
            return []

        logger.info("ZenATS %s: scraped %d jobs", company_name, len(jobs))
        return jobs

    def _parse_page(self, page, base_url: str, company_name: str) -> list[Job]:
        """Parse ZenATS job listings (table or list structure)."""
        jobs = []
        # ZenATS often uses table rows or job links
        links = (
            page.css('a[href*="/job/"]')
            or page.css('a[href*="/jobs/"]')
            or page.css('a[href*="job_id"]')
            or page.css("table a")
            or page.css(".job-item a")
            or page.css("[class*='job'] a")
        )
        seen = set()

        for link in links:
            href = link.attrib.get("href", "")
            if not href or "login" in href.lower() or "signup" in href.lower():
                continue
            full_url = urljoin(base_url, href) if href.startswith("/") else href
            if full_url in seen:
                continue
            seen.add(full_url)

            title_el = link.css("::text").get() or link.attrib.get("title", "")
            title = (title_el or "").strip()
            if len(title) < 5 or title.lower() in ("apply", "view", "details"):
                continue

            location = self._extract_location_from_url(full_url)

            jobs.append(
                Job(
                    title=title[:200],
                    company=company_name,
                    location=location or None,
                    url=full_url,
                    description=None,
                    posted_date=None,
                    source=self.name,
                )
            )

        return jobs

    def _extract_location_from_url(self, url: str) -> str | None:
        match = re.search(r"/job/([^/]+)/", url, re.I)
        if match:
            return match.group(1).replace("-", ", ")
        return None

    def _matches_location(self, job: Job, locations_filter: list) -> bool:
        if not locations_filter:
            return True
        loc_str = (job.location or "").lower() + " " + job.url.lower()
        return any(loc and str(loc).lower() in loc_str for loc in locations_filter)
