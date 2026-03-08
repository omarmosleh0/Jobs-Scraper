"""Workday ATS scraper. Covers PwC, Deloitte, EY and other Workday career sites."""

import logging
from datetime import datetime

import httpx

from jobs_scraper.models import Job
from jobs_scraper.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class WorkdayScraper(BaseScraper):
    """Scrape jobs from Workday via CXS POST API (no auth)."""

    name = "workday"

    def scrape(self, config: dict) -> list[Job]:
        """Scrape Workday jobs. Config: base_url (e.g. pwc.wd3.myworkdayjobs.com),
        site_name (e.g. Global_Experienced_Careers), tenant, company_name, locations_filter."""
        base_url = config.get("base_url", "")
        site_name = config.get("site_name", "")
        tenant = config.get("tenant", "")
        company_name = config.get("company_name", "Company")
        locations_filter = config.get("locations_filter") or []

        if not base_url or not site_name:
            logger.warning("Workday scraper requires base_url and site_name")
            return []

        # Normalize base_url (strip protocol)
        base = base_url.replace("https://", "").replace("http://", "").rstrip("/")
        if not tenant:
            tenant = base.split(".")[0]

        api_url = f"https://{base}/wday/cxs/{tenant}/{site_name}/jobs"
        jobs: list[Job] = []
        limit = 20
        offset = 0
        total = 1

        try:
            with httpx.Client(timeout=30.0) as client:
                while offset < total:
                    payload = {
                        "appliedFacets": {},
                        "limit": limit,
                        "offset": offset,
                        "searchText": "",
                    }
                    resp = client.post(api_url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()

                    total = data.get("total", 0)
                    postings = data.get("jobPostings", [])

                    for j in postings:
                        title = j.get("title", "Unknown")[:200]
                        loc_info = j.get("locationsText", "") or j.get("location", "") or ""
                        job_url = j.get("externalPath") or ""
                        if job_url and not job_url.startswith("http"):
                            job_url = f"https://{base}{job_url}" if job_url.startswith("/") else f"https://{base}/{job_url}"
                        if not job_url:
                            job_url = f"https://{base}"

                        if locations_filter:
                            if not any(str(loc).lower() in (loc_info or "").lower() for loc in locations_filter if loc):
                                continue

                        posted = None
                        if "postedOn" in j:
                            try:
                                posted = datetime.fromisoformat(j["postedOn"].replace("Z", "+00:00"))
                            except Exception:
                                pass

                        jobs.append(
                            Job(
                                title=title,
                                company=company_name,
                                location=loc_info or None,
                                url=job_url or f"https://{base}",
                                description=None,
                                posted_date=posted,
                                source=self.name,
                            )
                        )

                    offset += limit
                    if offset >= total or not postings:
                        break

        except Exception as e:
            logger.error("Workday fetch failed for %s: %s", company_name, e)
            return []

        logger.info("Workday %s: scraped %d jobs", company_name, len(jobs))
        return jobs
