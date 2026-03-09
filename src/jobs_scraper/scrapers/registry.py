"""Scraper plugin registry and auto-discovery."""

from jobs_scraper.scrapers.base import BaseScraper
from jobs_scraper.scrapers.job_boards.akhtaboot import AkhtabootScraper
from jobs_scraper.scrapers.job_boards.bayt import BaytScraper
from jobs_scraper.scrapers.ats.workable import WorkableScraper
from jobs_scraper.scrapers.ats.smartrecruiters import SmartRecruitersScraper
from jobs_scraper.scrapers.ats.workday import WorkdayScraper
from jobs_scraper.scrapers.ats.phenom import PhenomScraper
from jobs_scraper.scrapers.ats.zenats import ZenATSScraper
from jobs_scraper.scrapers.ats.jobsoid import JobsoidScraper
from jobs_scraper.scrapers.custom.generic_llm import GenericLLMScraper
from jobs_scraper.scrapers.linkedin import LinkedInScraper

_REGISTRY: dict[str, BaseScraper] = {
    "akhtaboot": AkhtabootScraper(),
    "bayt": BaytScraper(),
    "workable": WorkableScraper(),
    "smartrecruiters": SmartRecruitersScraper(),
    "workday": WorkdayScraper(),
    "phenom": PhenomScraper(),
    "zenats": ZenATSScraper(),
    "jobsoid": JobsoidScraper(),
    "generic_llm": GenericLLMScraper(),
    "linkedin": LinkedInScraper(),
}


def get_scraper(name: str) -> BaseScraper | None:
    """Get a scraper by name."""
    return _REGISTRY.get(name)


def list_scrapers() -> list[str]:
    """List all registered scraper names."""
    return list(_REGISTRY.keys())
