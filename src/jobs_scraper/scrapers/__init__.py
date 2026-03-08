"""Scraper plugins for job boards and company career pages."""

from jobs_scraper.scrapers.base import BaseScraper
from jobs_scraper.scrapers.registry import get_scraper, list_scrapers

__all__ = ["BaseScraper", "get_scraper", "list_scrapers"]
