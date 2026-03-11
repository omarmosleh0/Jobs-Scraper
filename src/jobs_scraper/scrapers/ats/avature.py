"""Avature ATS scraper. Covers Deloitte Middle East (middleeastjobs.deloitte.com) and other Avature career sites."""

import logging
import re
import time
from urllib.parse import urljoin

from jobs_scraper.models import Job
from jobs_scraper.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class AvatureScraper(BaseScraper):
    """Scrape jobs from Avature career sites (e.g. middleeastjobs.deloitte.com)."""

    name = "avature"

    def scrape(self, config: dict) -> list[Job]:
        """Scrape Avature careers. Config: base_url, careers_path, company_name, locations_filter."""
        base_url = config.get("base_url", "").replace("https://", "").replace("http://", "").rstrip("/")
        careers_path = config.get("careers_path", "/careersME/SearchJobs")
        company_name = config.get("company_name", "Company")
        locations_filter = config.get("locations_filter") or []

        if not base_url:
            logger.warning("Avature scraper requires base_url")
            return []

        careers_url = f"https://{base_url}{careers_path}"
        jobs: list[Job] = []

        try:
            from scrapling.fetchers import Fetcher
        except ImportError:
            logger.error("Scrapling not installed. Run: pip install 'scrapling[fetchers]'")
            return []

        try:
            page_size = 6
            offset = 0
            seen_ids: set[str] = set()

            for _ in range(50):  # Max ~300 jobs
                url = f"{careers_url}?pipelineRecordsPerPage={page_size}&pipelineOffset={offset}"
                page = Fetcher.get(url, impersonate="chrome", stealthy_headers=True, timeout=30)
                if not page or not hasattr(page, "css"):
                    break

                page_jobs = self._parse_page(page, base_url, company_name)
                if not page_jobs:
                    break

                for j in page_jobs:
                    pipeline_id = self._extract_pipeline_id(j.url)
                    if pipeline_id and pipeline_id not in seen_ids:
                        seen_ids.add(pipeline_id)
                        if not locations_filter or self._matches_location(j, locations_filter):
                            jobs.append(j)

                if len(page_jobs) < page_size:
                    break

                offset += page_size
                time.sleep(2)

        except Exception as e:
            logger.exception("Avature scrape failed for %s: %s", company_name, e)
            return []

        logger.info("Avature %s: scraped %d jobs", company_name, len(jobs))
        return jobs

    def _parse_page(self, page, base_url: str, company_name: str) -> list[Job]:
        """Parse Avature job listings. Deloitte structure: h3 (title), then 'Location | Posted', then Apply link."""
        jobs = []
        base = f"https://{base_url}"
        seen_ids: set[str] = set()

        # Deloitte: each job has a[href*="pipelineId="] with preceding h3 (title) and location text
        for link in page.css('a[href*="pipelineId="]'):
            href = link.attrib.get("href", "")
            pipeline_id = self._extract_pipeline_id(href)
            if not pipeline_id or pipeline_id in seen_ids:
                continue
            seen_ids.add(pipeline_id)

            full_url = urljoin(base, href) if href.startswith("/") else href
            if base_url not in full_url:
                full_url = urljoin(base, href)

            # Title: closest preceding heading (Deloitte: h3 before each Apply link)
            title = "Unknown"
            for heading in link.xpath("preceding::*[self::h2 or self::h3 or self::h4][1]"):
                t = (heading.css("::text").get() or "").strip()
                if t and len(t) > 5 and "Apply" not in t:
                    title = t
                    break

            # Location: format "Country | Posted on date" - search in parent/ancestors of link
            location = None
            current = link
            for _ in range(5):
                parent_list = current.xpath("..")
                if not parent_list:
                    break
                parent = parent_list[0]
                text = " ".join(parent.css("::text").getall())
                loc_match = re.search(r"([^|]+)\s*\|\s*Posted", text, re.I)
                if loc_match:
                    loc_part = loc_match.group(1).strip()
                    if loc_part and len(loc_part) > 2 and loc_part != title:
                        location = loc_part
                        break
                current = parent

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

    def _extract_pipeline_id(self, url: str) -> str | None:
        match = re.search(r"pipelineId=(\d+)", url, re.I)
        return match.group(1) if match else None

    def _matches_location(self, job: Job, locations_filter: list) -> bool:
        if not locations_filter:
            return True
        loc_str = (job.location or "").lower() + " " + (job.title or "").lower()
        return any(loc and str(loc).lower() in loc_str for loc in locations_filter)
