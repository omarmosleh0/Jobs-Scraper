"""Workable ATS scraper - public widget API. Covers Foodics and other Workable companies."""

import logging
from datetime import datetime
from urllib.parse import urljoin

import httpx

from jobs_scraper.models import Job
from jobs_scraper.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

WORKABLE_WIDGET_URL = "https://apply.workable.com/api/v1/widget/accounts/{account}"

# Jordan-related location identifiers for filtering
JORDAN_KEYS = {"JO", "Jordan", "Amman", "jordan", "amman"}


class WorkableScraper(BaseScraper):
    """Scrape jobs from Workable via public widget API (no auth)."""

    name = "workable"

    def scrape(self, config: dict) -> list[Job]:
        """Scrape Workable jobs. Config: account (e.g. foodics), company_name override."""
        account = config.get("account", "")
        company_name = config.get("company_name", account.capitalize())
        locations_filter = config.get("locations_filter") or []
        # If locations_filter specified, only include jobs in those locations
        filter_jordan = bool(locations_filter)

        if not account:
            logger.warning("Workable scraper requires 'account' in config")
            return []

        url = WORKABLE_WIDGET_URL.format(account=account)
        jobs: list[Job] = []

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.error("Workable fetch failed for %s: %s", account, e)
            return []

        raw_jobs = data.get("jobs", [])
        for j in raw_jobs:
            location_str = self._format_location(j)
            if filter_jordan and locations_filter:
                if not self._matches_location(j, locations_filter):
                    continue
            jobs.append(
                Job(
                    title=j.get("title", "Unknown")[:200],
                    company=company_name,
                    location=location_str or None,
                    url=j.get("url") or j.get("shortlink", ""),
                    description=None,
                    posted_date=self._parse_date(j.get("published_on")),
                    source=self.name,
                    raw_data={"department": j.get("department"), "shortcode": j.get("shortcode")},
                )
            )

        logger.info("Workable %s: scraped %d jobs", account, len(jobs))
        return jobs

    def _format_location(self, j: dict) -> str:
        """Format location from job dict."""
        locs = j.get("locations", [])
        if locs:
            loc = locs[0]
            parts = [loc.get("city"), loc.get("region"), loc.get("country")]
            return ", ".join(p for p in parts if p)
        city = j.get("city") or ""
        country = j.get("country") or ""
        if city or country:
            return ", ".join(p for p in [city, country] if p)
        return ""

    def _matches_location(self, j: dict, locations_filter: list) -> bool:
        """Check if job matches any of the location filters."""
        loc_str = (
            self._format_location(j).lower()
            + " "
            + (j.get("countryCode") or "").lower()
        )
        for loc in locations_filter:
            if loc and str(loc).lower() in loc_str:
                return True
        return False

    def _parse_date(self, s: str | None) -> datetime | None:
        """Parse YYYY-MM-DD date."""
        if not s:
            return None
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d")
        except ValueError:
            return None
