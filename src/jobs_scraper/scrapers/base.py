"""Base scraper interface for job board plugins."""

from abc import ABC, abstractmethod

from jobs_scraper.models import Job


class BaseScraper(ABC):
    """Abstract base class for all job scrapers."""

    name: str = ""

    @abstractmethod
    def scrape(self, config: dict) -> list[Job]:
        """Scrape jobs from the configured source. Returns normalized Job objects."""
        ...
