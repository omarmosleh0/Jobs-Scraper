"""Supabase client for job storage."""

import logging
from typing import Any

from jobs_scraper.config import SUPABASE_KEY, SUPABASE_URL
from jobs_scraper.models import Job

logger = logging.getLogger(__name__)


class SupabaseStorage:
    """Store and retrieve jobs from Supabase."""

    def __init__(self, url: str | None = None, key: str | None = None):
        self.url = url or SUPABASE_URL
        self.key = key or SUPABASE_KEY
        self._client = None

    @property
    def client(self):
        """Lazy init Supabase client."""
        if self._client is None:
            if not self.url or not self.key:
                raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
            from supabase import create_client

            self._client = create_client(self.url, self.key)
        return self._client

    def insert_job(self, job: Job, content_hash: str) -> dict[str, Any] | None:
        """Insert a job. Returns the row if inserted, None if duplicate (unique violation)."""
        row = job.to_db_row(content_hash)
        row["content_hash"] = content_hash
        try:
            result = self.client.table("jobs").insert(row).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
        except Exception as e:
            err_str = str(e).lower()
            if "duplicate" in err_str or "23505" in err_str or "unique" in err_str:
                return None  # Duplicate, skip
            logger.error("Supabase insert failed: %s", e)
            raise

    def get_existing_hashes(self, hashes: list[str]) -> set[str]:
        """Return set of content hashes that already exist in DB."""
        if not hashes:
            return set()
        try:
            result = self.client.table("jobs").select("content_hash").in_("content_hash", hashes).execute()
            return {r["content_hash"] for r in (result.data or [])}
        except Exception as e:
            logger.warning("Failed to fetch existing hashes: %s", e)
            return set()

    def get_unnotified_jobs(self, limit: int = 100) -> list[dict]:
        """Get jobs that haven't been notified yet."""
        try:
            result = (
                self.client.table("jobs")
                .select("*")
                .eq("notified", False)
                .order("scraped_at", desc=False)
                .limit(limit)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.error("Failed to fetch unnotified jobs: %s", e)
            return []

    def mark_notified(self, job_ids: list[str]) -> None:
        """Mark jobs as notified."""
        if not job_ids:
            return
        try:
            self.client.table("jobs").update({"notified": True}).in_("id", job_ids).execute()
        except Exception as e:
            logger.error("Failed to mark jobs notified: %s", e)
