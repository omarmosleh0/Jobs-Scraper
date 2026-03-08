"""Jobsoid ATS scraper. Covers Almosafer/Seera and other Jobsoid career sites."""

import logging
import re
import time
from urllib.parse import urljoin

from jobs_scraper.models import Job
from jobs_scraper.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class JobsoidScraper(BaseScraper):
    """Scrape jobs from Jobsoid career sites (e.g. jobs.almosafer.com)."""

    name = "jobsoid"

    def scrape(self, config: dict) -> list[Job]:
        """Scrape Jobsoid careers. Config: careers_url (e.g. https://jobs.almosafer.com/search/),
        company_name, locations_filter."""
        careers_url = config.get("careers_url", "")
        company_name = config.get("company_name", "Company")
        locations_filter = config.get("locations_filter") or []

        if not careers_url:
            logger.warning("Jobsoid scraper requires careers_url")
            return []

        jobs: list[Job] = []

        try:
            from scrapling.fetchers import Fetcher
        except ImportError:
            logger.error("Scrapling not installed. Run: pip install 'scrapling[fetchers]'")
            return []

        try:
            base = careers_url.split("/search")[0] if "/search" in careers_url else careers_url.rstrip("/")
            search_url = f"{base}/search/" if "/search" not in careers_url else careers_url

            page = Fetcher.get(search_url)
            if not page or not hasattr(page, "css"):
                logger.warning("Jobsoid: no page content for %s", search_url)
                return []

            page_jobs = self._parse_page(page, base, company_name)
            for j in page_jobs:
                if not locations_filter or self._matches_location(j, locations_filter):
                    jobs.append(j)

            # Pagination
            for p in range(2, 5):
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
                    logger.debug("Jobsoid pagination failed: %s", e)
                    break

        except Exception as e:
            logger.exception("Jobsoid scrape failed for %s: %s", company_name, e)
            return []

        logger.info("Jobsoid %s: scraped %d jobs", company_name, len(jobs))
        return jobs

    def _parse_page(self, page, base_url: str, company_name: str) -> list[Job]:
        """Parse Jobsoid job listings. URL pattern: /job/City-Title/ID"""
        jobs = []
        links = page.css('a[href*="/job/"]')
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

            # Jobsoid URL: /job/Amman-Senior-Specialist-Backend-Engineer/1290671401/
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
        """Extract city from Jobsoid URL: /job/City-Title/ID"""
        match = re.search(r"/job/([^/]+)/", url, re.I)
        if match:
            path = match.group(1)
            # First segment is often city (Amman, Riyadh, Cairo, Dubai, etc.)
            parts = path.split("-")
            if parts:
                city = parts[0]
                if len(city) > 2 and city[0].isupper():
                    return city
        return None

    def _matches_location(self, job: Job, locations_filter: list) -> bool:
        if not locations_filter:
            return True
        loc_str = (job.location or "").lower() + " " + job.url.lower()
        return any(loc and str(loc).lower() in loc_str for loc in locations_filter)
