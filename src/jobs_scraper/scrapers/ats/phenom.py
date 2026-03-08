"""Phenom People ATS scraper. Covers Majid Al Futtaim and other Phenom career sites."""

import logging
import re
import time
from urllib.parse import urljoin

from jobs_scraper.models import Job
from jobs_scraper.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class PhenomScraper(BaseScraper):
    """Scrape jobs from Phenom People career sites (e.g. careers.majidalfuttaim.com)."""

    name = "phenom"

    def scrape(self, config: dict) -> list[Job]:
        """Scrape Phenom careers. Config: careers_url, company_name, locations_filter."""
        careers_url = config.get("careers_url", "")
        company_name = config.get("company_name", "Company")
        locations_filter = config.get("locations_filter") or []

        if not careers_url:
            logger.warning("Phenom scraper requires careers_url")
            return []

        jobs: list[Job] = []

        try:
            from scrapling.fetchers import Fetcher
        except ImportError:
            logger.error("Scrapling not installed. Run: pip install 'scrapling[fetchers]'")
            return []

        try:
            base = careers_url.split("/search")[0] if "/search" in careers_url else careers_url.rstrip("/")
            search_url = f"{base}/search-results" if "search" not in careers_url else careers_url

            page = Fetcher.get(search_url)
            if not page or not hasattr(page, "css"):
                logger.warning("Phenom: no page content for %s", search_url)
                return []

            page_jobs = self._parse_page(page, base, company_name)
            for j in page_jobs:
                if not locations_filter or self._matches_location(j, locations_filter):
                    jobs.append(j)

            # Try pagination
            for p in range(2, 4):
                try:
                    time.sleep(2)
                    next_url = f"{search_url}?page={p}" if "?" not in search_url else f"{search_url}&page={p}"
                    next_page = Fetcher.get(next_url)
                    if next_page and hasattr(next_page, "css"):
                        more = self._parse_page(next_page, base, company_name)
                        for j in more:
                            if (not locations_filter or self._matches_location(j, locations_filter)) and not any(
                                x.url == j.url for x in jobs
                            ):
                                jobs.append(j)
                except Exception as e:
                    logger.debug("Phenom pagination failed: %s", e)
                    break

        except Exception as e:
            logger.exception("Phenom scrape failed for %s: %s", company_name, e)
            return []

        logger.info("Phenom %s: scraped %d jobs", company_name, len(jobs))
        return jobs

    def _parse_page(self, page, base_url: str, company_name: str) -> list[Job]:
        """Parse Phenom job listings."""
        jobs = []
        links = (
            page.css('a[href*="/job/"]')
            or page.css('a[href*="phjob"]')
            or page.css('a[href*="phjb"]')
            or page.css('[data-ph-at-id="job-link"]')
        )
        seen = set()

        for link in links:
            href = link.attrib.get("href", "")
            full_url = urljoin(base_url, href) if href.startswith("/") else href
            if full_url in seen:
                continue
            seen.add(full_url)

            title_el = link.css("::text").get() or link.attrib.get("title", "")
            title = (title_el or "").strip()
            if len(title) < 5:
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
        """Extract location from Phenom job URL if present."""
        match = re.search(r"/job/([^/]+)/", url, re.I)
        if match:
            parts = match.group(1).split("-")
            if len(parts) >= 2:
                return ", ".join(parts[:2])
        return None

    def _matches_location(self, job: Job, locations_filter: list) -> bool:
        if not locations_filter:
            return True
        loc_str = (job.location or "").lower() + " " + job.url.lower()
        return any(loc and str(loc).lower() in loc_str for loc in locations_filter)
