"""iCIMS ATS scraper. Covers SITA (careers.sita.aero) and other iCIMS career sites."""

import logging
import re
import time
from urllib.parse import urljoin

from jobs_scraper.models import Job
from jobs_scraper.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class IcimsScraper(BaseScraper):
    """Scrape jobs from iCIMS career sites (e.g. careers.sita.aero)."""

    name = "icims"

    def scrape(self, config: dict) -> list[Job]:
        """Scrape iCIMS careers. Config: base_url, jobs_path, company_name, locations_filter."""
        base_url = config.get("base_url", "").replace("https://", "").replace("http://", "").rstrip("/")
        jobs_path = config.get("jobs_path", "/jobs/search")
        company_name = config.get("company_name", "Company")
        locations_filter = config.get("locations_filter") or []

        if not base_url:
            logger.warning("iCIMS scraper requires base_url")
            return []

        jobs_url = f"https://{base_url}{jobs_path}"
        jobs: list[Job] = []

        try:
            from scrapling.fetchers import Fetcher
        except ImportError:
            logger.error("Scrapling not installed. Run: pip install 'scrapling[fetchers]'")
            return []

        try:
            base = f"https://{base_url}"
            seen_ids: set[str] = set()

            # iCIMS/SITA: paginate with pr (page) or similar
            for page_num in range(10):
                url = f"{jobs_url}?pr={page_num}" if "?" not in jobs_path else f"{jobs_url}&pr={page_num}"
                if page_num == 0:
                    url = jobs_url

                page = Fetcher.get(url, impersonate="chrome", stealthy_headers=True, timeout=30)
                if not page or not hasattr(page, "css"):
                    break

                page_jobs = self._parse_page(page, base, company_name)
                if not page_jobs:
                    break

                for j in page_jobs:
                    job_id = self._extract_job_id(j.url)
                    if job_id and job_id not in seen_ids:
                        seen_ids.add(job_id)
                        if not locations_filter or self._matches_location(j, locations_filter):
                            jobs.append(j)

                if len(page_jobs) < 10:
                    break

                time.sleep(2)

        except Exception as e:
            logger.exception("iCIMS scrape failed for %s: %s", company_name, e)
            return []

        logger.info("iCIMS %s: scraped %d jobs", company_name, len(jobs))
        return jobs

    def _parse_page(self, page, base_url: str, company_name: str) -> list[Job]:
        """Parse iCIMS job listings. Jobs have links to /jobs/{id}."""
        jobs = []
        seen_ids: set[str] = set()

        # Links to job detail: /jobs/12345 or /jobs/12345?lang=
        links = page.css('a[href*="/jobs/"]')
        for link in links:
            href = link.attrib.get("href", "")
            if "login" in href.lower() or "referral" in href.lower():
                continue

            # Extract job ID from URL
            match = re.search(r"/jobs/(\d+)", href, re.I)
            if not match:
                continue
            job_id = match.group(1)
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            full_url = urljoin(base_url, href) if href.startswith("/") else href
            if base_url.split("//")[-1].split("/")[0] not in full_url:
                full_url = urljoin(base_url, href)

            title = (link.css("::text").get() or "").strip()
            if not title or len(title) < 3 or "Apply" in title or "Share" in title:
                continue

            # Location often in sibling or parent - look for "Location X, Y"
            location = None
            parent = link
            for _ in range(5):
                parent = parent.xpath("..")[0] if parent.xpath("..") else None
                if parent is None:
                    break
                parent_text = " ".join(parent.css("::text").getall())
                loc_match = re.search(r"Location\s+([^C]+?)(?:Categories|Position|$)", parent_text, re.I | re.DOTALL)
                if loc_match:
                    location = loc_match.group(1).strip()
                    break

            jobs.append(
                Job(
                    title=title[:200],
                    company=company_name,
                    location=location,
                    url=full_url,
                    description=None,
                    posted_date=None,
                    source=self.name,
                )
            )

        return jobs

    def _extract_job_id(self, url: str) -> str | None:
        match = re.search(r"/jobs/(\d+)", url, re.I)
        return match.group(1) if match else None

    def _matches_location(self, job: Job, locations_filter: list) -> bool:
        if not locations_filter:
            return True
        loc_str = (job.location or "").lower() + " " + (job.title or "").lower()
        return any(loc and str(loc).lower() in loc_str for loc in locations_filter)
