"""Bayt.com job board scraper."""

import logging
import re
import time
from urllib.parse import quote_plus, urljoin

from jobs_scraper.models import Job
from jobs_scraper.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class BaytScraper(BaseScraper):
    """Scrape tech jobs from Bayt.com (Jordan)."""

    name = "bayt"

    def scrape(self, config: dict) -> list[Job]:
        """Scrape Bayt for jobs matching keywords in Jordan."""
        keywords = config.get("keywords", ["software engineer", "data engineer"])
        location = config.get("location", "jordan")
        jobs: list[Job] = []
        base_url = "https://www.bayt.com/en/jordan/jobs/"

        try:
            from scrapling.fetchers import Fetcher

            for kw in keywords[:5]:  # Limit to avoid too many requests
                # Bayt search: use q param or scrape main jobs page
                url = f"{base_url}?q={quote_plus(kw)}" if kw else base_url
                try:
                    page = Fetcher.get(url)
                    page_jobs = self._parse_page(page, base_url)
                    for j in page_jobs:
                        j.source = self.name
                        if j not in jobs and not any(
                            j.url == x.url and j.title == x.title for x in jobs
                        ):
                            jobs.append(j)
                    time.sleep(2)  # Rate limit
                except Exception as e:
                    logger.warning("Bayt scrape failed for %s: %s", kw, e)
        except ImportError:
            logger.error("Scrapling not installed. Run: pip install 'scrapling[fetchers]'")
            return []

        return jobs

    def _parse_page(self, page, base_url: str) -> list[Job]:
        """Parse Bayt job listing page."""
        jobs = []
        # Bayt uses various structures; try common selectors
        # Job cards often in article or div with job-related classes
        cards = page.css("article") or page.css("[data-job-id]") or page.css(".jb-result")
        if not cards:
            # Fallback: look for job links
            links = page.css('a[href*="/jobs/"]')
            seen = set()
            for link in links:
                href = link.attrib.get("href", "")
                if "jb_id=" in href or "/jobs/" in href:
                    match = re.search(r"jb_id=(\d+)", href)
                    if match:
                        jb_id = match.group(1)
                        if jb_id in seen:
                            continue
                        seen.add(jb_id)
                        title_el = link.css("::text").get() or link.parent.css("h2::text").get()
                        if not title_el or len(title_el.strip()) < 5:
                            continue
                        company_el = link.parent.css("a[href*='/company/']::text").get()
                        loc_el = link.parent.css("a[href*='/jobs/']::text").getall()
                        url = f"https://www.bayt.com/en/jordan/jobs/?jb_id={jb_id}" if "bayt.com" not in href else urljoin(base_url, href)
                        jobs.append(
                            Job(
                                title=title_el.strip()[:200],
                                company=(company_el or "Unknown").strip(),
                                location=", ".join(loc_el).strip() or "Jordan" if loc_el else "Jordan",
                                url=url,
                                description=None,
                                source=self.name,
                            )
                        )
            return jobs

        for card in cards:
            try:
                title_el = card.css("h2 a::text, .jb-title::text, [data-job-title]::text").get()
                if not title_el:
                    title_el = card.css("a::text").get()
                title = (title_el or "").strip()
                if len(title) < 5:
                    continue

                link_els = card.css("a[href*='jb_id='], a[href*='/jobs/']")
                link_el = link_els[0] if link_els else None
                href = link_el.attrib.get("href", "") if link_el else ""
                url = urljoin(base_url, href) if href else ""
                if not url:
                    continue

                company_el = card.css("a[href*='/company/']::text, .jb-company::text").get()
                company = (company_el or "Unknown").strip()

                loc_parts = card.css("a[href*='/jobs/']::text").getall()
                location = ", ".join(loc_parts).strip() if loc_parts else "Jordan"

                desc_el = card.css(".jb-summary::text, .jb-desc::text, p::text").get()
                desc = (desc_el or "").strip()[:500] if desc_el else None

                jobs.append(
                    Job(
                        title=title[:200],
                        company=company,
                        location=location or "Jordan",
                        url=url,
                        description=desc,
                        source=self.name,
                    )
                )
            except Exception as e:
                logger.debug("Failed to parse Bayt card: %s", e)
                continue

        return jobs
