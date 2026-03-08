"""Akhtaboot job board scraper."""

import logging
import re
import time
from urllib.parse import quote_plus, urljoin

from jobs_scraper.models import Job
from jobs_scraper.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class AkhtabootScraper(BaseScraper):
    """Scrape tech jobs from Akhtaboot (Jordan)."""

    name = "akhtaboot"

    def scrape(self, config: dict) -> list[Job]:
        """Scrape Akhtaboot for jobs matching keywords in Jordan."""
        keywords = config.get("keywords", ["software engineer", "data engineer"])
        location = config.get("location", "jordan")
        jobs: list[Job] = []
        base_url = "https://www.akhtaboot.com"

        try:
            from scrapling.fetchers import Fetcher, StealthyFetcher

            # Akhtaboot may require JS; try Fetcher first, fallback to StealthyFetcher
            fetcher = Fetcher
            for kw in keywords[:5]:
                # Akhtaboot search: /en/jordan/jobs with query param or job_role
                url = f"{base_url}/en/jordan/jobs"
                if kw:
                    url = f"{base_url}/en/the-middle-east/jobs?q={quote_plus(kw)}"
                try:
                    page = fetcher.get(url)
                    if page and hasattr(page, "css"):
                        page_jobs = self._parse_page(page, base_url)
                        for j in page_jobs:
                            j.source = self.name
                            if not any(j.url == x.url and j.title == x.title for x in jobs):
                                jobs.append(j)
                    time.sleep(2)
                except Exception as e:
                    logger.warning("Akhtaboot scrape failed for %s: %s", kw, e)
        except ImportError:
            logger.error("Scrapling not installed. Run: pip install 'scrapling[fetchers]'")
            return []

        return jobs

    def _parse_page(self, page, base_url: str) -> list[Job]:
        """Parse Akhtaboot job listing page."""
        jobs = []
        # Akhtaboot structure varies; try common patterns
        cards = page.css(".job-card, .job-item, article, [class*='job']")
        if not cards:
            # Fallback: find job links
            links = page.css('a[href*="/jobs/"]')
            seen = set()
            for link in links:
                href = link.attrib.get("href", "")
                if "/jobs/" not in href or "job_role" in href or "browse" in href.lower():
                    continue
                full_url = urljoin(base_url, href)
                if full_url in seen:
                    continue
                seen.add(full_url)
                title_el = link.css("::text").get()
                if not title_el or len(title_el.strip()) < 5:
                    continue
                # Extract location from parent or sibling
                parent = getattr(link, "parent", None)
                loc = "Jordan"
                if parent and hasattr(parent, "css"):
                    loc_els = parent.css("span::text, .location::text").getall()
                    loc = ", ".join(loc_els).strip() or "Jordan"
                jobs.append(
                    Job(
                        title=title_el.strip()[:200],
                        company="Unknown",
                        location=loc,
                        url=full_url,
                        description=None,
                        source=self.name,
                    )
                )
            return jobs

        for card in cards:
            try:
                link_el = card.css("a[href*='/jobs/']")
                if not link_el:
                    continue
                link_el = link_el[0]
                href = link_el.attrib.get("href", "")
                if "job_role" in href or "browse" in href:
                    continue
                url = urljoin(base_url, href)
                title_el = link_el.css("::text").get() or card.css("h3::text, h4::text").get()
                title = (title_el or "").strip()
                if len(title) < 5:
                    continue
                company_el = card.css(".company::text, [class*='company']::text").get()
                company = (company_el or "Unknown").strip()
                loc_el = card.css(".location::text, [class*='location']::text").getall()
                location = ", ".join(loc_el).strip() or "Jordan"
                jobs.append(
                    Job(
                        title=title[:200],
                        company=company,
                        location=location,
                        url=url,
                        description=None,
                        source=self.name,
                    )
                )
            except Exception as e:
                logger.debug("Failed to parse Akhtaboot card: %s", e)
        return jobs
