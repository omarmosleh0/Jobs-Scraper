"""Pydantic models for jobs and scraping results."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Job(BaseModel):
    """A job posting, normalized across all sources."""

    title: str
    company: str
    location: str | None = None
    url: str
    description: str | None = None
    posted_date: datetime | None = None
    source: str  # "akhtaboot", "bayt", "indeed", etc.
    category: str | None = None  # data, ai_ml, backend, other
    category_confidence: float | None = None
    relevance_score: float | None = None
    embedding: list[float] | None = None
    raw_data: dict[str, Any] | None = None

    def to_db_row(self, content_hash: str) -> dict[str, Any]:
        """Convert to Supabase row format."""
        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "url": self.url,
            "description": self.description,
            "posted_date": self.posted_date.isoformat() if self.posted_date else None,
            "source": self.source,
            "category": self.category,
            "category_confidence": self.category_confidence,
            "relevance_score": self.relevance_score,
            "content_hash": content_hash,
            "embedding": self.embedding,
            "notified": False,
            "raw_data": self.raw_data,
        }


class ScrapingResult(BaseModel):
    """Result of a single scraper run."""

    source: str
    jobs: list[Job] = Field(default_factory=list)
    error: str | None = None


class ScrapeRunSummary(BaseModel):
    """Summary of a full scrape run."""

    started_at: datetime = Field(default_factory=datetime.now)
    finished_at: datetime | None = None
    status: str = "running"  # running, success, partial, failed
    jobs_found: int = 0
    new_jobs: int = 0
    errors: list[str] = Field(default_factory=list)
