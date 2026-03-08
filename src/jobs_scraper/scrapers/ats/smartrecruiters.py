"""SmartRecruiters / Talabat careers scraper. Scrapes careers.talabat.com (Delivery Hero)."""

import logging
import re
import time
from urllib.parse import urljoin

from jobs_scraper.models import Job
from jobs_scraper.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

# Default Talabat careers base
TALABAT_CAREERS = "https://careers.talabat.com"
JOBS_PATH = "/jobs"


class SmartRecruitersScraper(BaseScraper):
    """Scrape jobs from Talabat/Delivery Hero careers (careers.talabat.com)."""

    name = "smartrecruiters"

    def scrape(self, config: dict) -> list[Job]:
        """Scrape careers page. Config: company_id (e.g. talabat), company_name, careers_url, locations_filter."""
        company_id = config.get("company_id", "talabat")
        company_name = config.get("company_name") or "Talabat"
        careers_url = config.get("careers_url") or f"{TALABAT_CAREERS}{JOBS_PATH}"
        locations_filter = config.get("locations_filter") or ["JO", "Jordan", "Amman"]

        jobs: list[Job] = []

        try:
            from scrapling.fetchers import Fetcher
        except ImportError:
            logger.error("Scrapling not installed. Run: pip install 'scrapling[fetchers]'")
            return []

        try:
            base = careers_url.rsplit("/", 1)[0] if "/" in careers_url else careers_url
            if not base.startswith("http"):
                base = TALABAT_CAREERS

            page = Fetcher.get(careers_url)
            if not page or not hasattr(page, "css"):
                logger.warning("SmartRecruiters: no page content for %s", careers_url)
                return []

            page_jobs = self._parse_jobs_page(page, base, company_name)
            for j in page_jobs:
                if self._matches_location(j, locations_filter):
                    jobs.append(j)

            # Pagination: try a few more pages
            for p in range(2, 4):
                next_url = f"{careers_url}?page={p}" if "?" not in careers_url else f"{careers_url}&page={p}"
                try:
                    time.sleep(2)
                    next_page = Fetcher.get(next_url)
                    if next_page and hasattr(next_page, "css"):
                        more = self._parse_jobs_page(next_page, base, company_name)
                        for j in more:
                            if self._matches_location(j, locations_filter) and not any(
                                x.url == j.url for x in jobs
                            ):
                                jobs.append(j)
                except Exception as e:
                    logger.debug("Pagination page %d failed: %s", p, e)
                    break

        except Exception as e:
            logger.exception("SmartRecruiters scrape failed for %s: %s", company_id, e)
            return []

        logger.info("SmartRecruiters %s: scraped %d jobs", company_id, len(jobs))
        return jobs

    def _parse_jobs_page(self, page, base_url: str, company_name: str) -> list[Job]:
        """Parse job listings from careers page."""
        jobs = []
        # Common selectors for job listing pages
        links = page.css('a[href*="/job/"]') or page.css('a[href*="jid="]')
        seen_urls = set()

        for link in links:
            href = link.attrib.get("href", "")
            full_url = urljoin(base_url, href) if href.startswith("/") else href
            if "careers.talabat.com" not in full_url and "careers.deliveryhero" not in full_url:
                full_url = urljoin(base_url, href)

            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            title_el = link.css("::text").get() or link.attrib.get("title", "")
            title = (title_el or "").strip()
            if len(title) < 5:
                continue

            # Extract location from URL (e.g. ...-in-amman-jordan-jid-1234)
            location = self._extract_location_from_url(full_url)

            jobs.append(
                Job(
                    title=title[:200],
                    company=company_name,
                    location=location or "Jordan",
                    url=full_url,
                    description=None,
                    posted_date=None,
                    source=self.name,
                )
            )

        return jobs

    def _extract_location_from_url(self, url: str) -> str | None:
        """Extract location from job URL like ...-in-amman-jordan-jid-1234."""
        match = re.search(r"-in-([^-]+(?:-[^-]+)*)-jid-", url, re.I)
        if match:
            loc = match.group(1).replace("-", ", ")
            return loc
        return None

    def _matches_location(self, job: Job, locations_filter: list) -> bool:
        """Check if job matches Jordan/location filter."""
        if not locations_filter:
            return True
        loc_str = (job.location or "").lower() + " " + job.url.lower()
        for loc in locations_filter:
            if loc and str(loc).lower() in loc_str:
                return True
        return False
