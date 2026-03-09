"""
LinkedIn guest API scraper (Phase 4a - EXPERIMENTAL).

Uses the unauthenticated guest endpoint to fetch job listings.
Guest-only, no login. Isolated from other scrapers.
Uses Scrapling Fetcher for TLS fingerprint impersonation and stealthy headers.
"""

import logging
import random
import time
from urllib.parse import urljoin

from jobs_scraper.models import Job
from jobs_scraper.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"


class AdaptiveDelay:
    """Adaptive rate limiter with exponential backoff and circuit breaker."""

    def __init__(self, min_s: float = 5, max_s: float = 15):
        self.min_s = min_s
        self.max_s = max_s
        self.consecutive_fails = 0

    def wait(self) -> None:
        base = random.uniform(self.min_s, self.max_s)
        backoff = min(base * (2**self.consecutive_fails), 120)
        time.sleep(backoff)

    def record_success(self) -> None:
        self.consecutive_fails = 0

    def record_failure(self) -> None:
        self.consecutive_fails += 1

    def should_abort(self) -> bool:
        return self.consecutive_fails >= 3


class LinkedInScraper(BaseScraper):
    """
    Scrape jobs from LinkedIn via guest API (no auth).
    EXPERIMENTAL: May be blocked by LinkedIn. Isolated from other scrapers.
    Uses Scrapling for TLS impersonation and stealthy headers.
    """

    name = "linkedin"

    def scrape(self, config: dict) -> list[Job]:
        """Scrape LinkedIn jobs. Config: location, keywords, max_pages_per_keyword, min_delay, max_delay, fetch_descriptions."""
        try:
            from scrapling.fetchers import Fetcher
        except ImportError:
            logger.error("Scrapling not installed. Run: pip install 'scrapling[fetchers]'")
            return []

        fetcher = Fetcher
        location = config.get("location", "Amman, Jordan")
        keywords = config.get("keywords", ["data engineer", "software engineer"])
        max_pages = config.get("max_pages_per_keyword", 2)
        min_delay = config.get("min_delay", 5)
        max_delay = config.get("max_delay", 15)
        fetch_descriptions = config.get("fetch_descriptions", False)

        delay = AdaptiveDelay(min_s=min_delay, max_s=max_delay)
        jobs: list[Job] = []
        seen_urls: set[str] = set()

        for kw in keywords:
            if delay.should_abort():
                logger.warning("LinkedIn scraper aborted: too many failures")
                break

            for page in range(max_pages):
                if delay.should_abort():
                    break

                delay.wait()

                params = {
                    "keywords": kw,
                    "location": location,
                    "start": page * 25,
                }
                page_obj = self._fetch_page(fetcher, params)
                if page_obj is None:
                    delay.record_failure()
                    continue

                delay.record_success()
                page_jobs = self._parse_jobs(page_obj)
                for j in page_jobs:
                    j.source = self.name
                    if j.url not in seen_urls:
                        seen_urls.add(j.url)
                        jobs.append(j)

                if len(page_jobs) < 10:
                    break

        if fetch_descriptions and jobs:
            for job in jobs[:20]:
                job_id = self._extract_job_id(job.url)
                if job_id:
                    delay.wait()
                    desc = self._fetch_detail(fetcher, job_id)
                    if desc:
                        job.description = desc[:2000]

        logger.info("LinkedIn: scraped %d jobs", len(jobs))
        return jobs

    def _fetch_page(self, fetcher, params: dict):
        """Fetch search page. Returns Scrapling page object or None on failure."""
        try:
            page = fetcher.get(
                SEARCH_URL,
                params=params,
                stealthy_headers=True,
                impersonate="chrome",
                timeout=30,
            )
            if not page or not hasattr(page, "css"):
                return None
            body_text = page.body.decode("utf-8", errors="ignore") if isinstance(page.body, bytes) else str(page.body)
            if self._is_blocked_text(body_text):
                logger.warning("LinkedIn returned block/throttle")
                return None
            return page
        except Exception as e:
            logger.warning("LinkedIn fetch failed: %s", e)
            return None

    def _is_blocked_text(self, text: str) -> bool:
        """Check if response body indicates block/throttle."""
        if len(text) < 30:
            return True
        lower = text.lower()
        if "captcha" in lower or "authwall" in lower or "sign in" in lower:
            return True
        return False

    def _parse_jobs(self, page) -> list[Job]:
        """Extract job cards from Scrapling page object."""
        jobs: list[Job] = []

        cards = page.css("li div.base-card") or page.css("li [class*='base-card']")
        if not cards:
            cards = page.css("li")

        for card in cards:
            try:
                title_els = (
                    card.css(".base-search-card__title")
                    or card.css("[class*='_title']")
                    or card.css("h3, a")
                )
                link_els = (
                    card.css("[class*='_full-link']")
                    or card.css("a[href*='/jobs/view/']")
                    or card.css("a.base-card__full-link")
                )
                company_els = (
                    card.css(".base-search-card__subtitle")
                    or card.css("[class*='_subtitle']")
                )
                location_els = (
                    card.css(".job-search-card__location")
                    or card.css("[class*='_location']")
                )
                date_els = card.css("[class*='listdate']")

                if not title_els or not link_els:
                    continue

                title = (title_els[0].css("::text").get() or "").strip()[:200]
                href = link_els[0].attrib.get("href", "")
                url = href.split("?")[0] if href else ""
                if not url or not title or len(title) < 3:
                    continue
                if "linkedin.com" not in url:
                    url = urljoin("https://www.linkedin.com/", url)

                company = (
                    (company_els[0].css("::text").get() or "").strip()[:200]
                    if company_els
                    else "Unknown"
                )
                location = (
                    (location_els[0].css("::text").get() or "").strip() or None
                    if location_els
                    else None
                )
                posted_text = (
                    (date_els[0].css("::text").get() or "").strip() if date_els else None
                )

                jobs.append(
                    Job(
                        title=title,
                        company=company,
                        location=location,
                        url=url,
                        description=None,
                        posted_date=None,
                        source=self.name,
                        raw_data={"posted_text": posted_text},
                    )
                )
            except Exception as e:
                logger.debug("Failed to parse LinkedIn card: %s", e)
                continue

        return jobs

    def _extract_job_id(self, url: str) -> str | None:
        """Extract job ID from LinkedIn job URL."""
        try:
            path = url.split("?")[0]
            parts = path.rstrip("/").split("-")
            return parts[-1] if parts else None
        except Exception:
            return None

    def _fetch_detail(self, fetcher, job_id: str) -> str | None:
        """Fetch full job description from detail endpoint."""
        url = DETAIL_URL.format(job_id=job_id)
        try:
            page = fetcher.get(
                url,
                stealthy_headers=True,
                impersonate="chrome",
                timeout=30,
            )
            if not page or not hasattr(page, "css"):
                return None
            body_text = page.body.decode("utf-8", errors="ignore") if isinstance(page.body, bytes) else str(page.body)
            if self._is_blocked_text(body_text):
                return None
            desc_els = page.css("[class*='description'] section div") or page.css("[class*='_job-criteria-list']")
            if desc_els:
                text_parts = desc_els[0].css("::text").getall()
                return " ".join(p for p in text_parts if p).strip() if text_parts else None
        except Exception as e:
            logger.debug("LinkedIn detail fetch failed for %s: %s", job_id, e)
        return None
