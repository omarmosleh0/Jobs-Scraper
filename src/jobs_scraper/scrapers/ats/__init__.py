"""ATS platform scrapers."""

from jobs_scraper.scrapers.ats.workable import WorkableScraper
from jobs_scraper.scrapers.ats.smartrecruiters import SmartRecruitersScraper
from jobs_scraper.scrapers.ats.workday import WorkdayScraper
from jobs_scraper.scrapers.ats.phenom import PhenomScraper
from jobs_scraper.scrapers.ats.zenats import ZenATSScraper
from jobs_scraper.scrapers.ats.jobsoid import JobsoidScraper

__all__ = [
    "WorkableScraper",
    "SmartRecruitersScraper",
    "WorkdayScraper",
    "PhenomScraper",
    "ZenATSScraper",
    "JobsoidScraper",
]
