"""LLM-based structured job extraction from raw HTML/text. Used by generic_llm scraper."""

import json
import logging
import re
from typing import Any

import httpx

from jobs_scraper.config import load_preferences, OLLAMA_MODEL, OLLAMA_URL
from jobs_scraper.models import Job

logger = logging.getLogger(__name__)

# Max chars to send to LLM (avoid token limits)
MAX_PAGE_CHARS = 12000


class JobExtractor:
    """Extract structured Job objects from raw career page text via Ollama."""

    def __init__(
        self,
        ollama_url: str | None = None,
        model: str | None = None,
    ):
        prefs = load_preferences()
        ai_config = prefs.get("ai", {})
        self.ollama_url = (ollama_url or ai_config.get("ollama_url") or OLLAMA_URL).rstrip("/")
        self.model = model or ai_config.get("model") or OLLAMA_MODEL

    def extract_jobs(self, page_text: str, company: str, base_url: str = "") -> list[Job]:
        """
        Feed raw page content to Ollama, get back structured Job objects.
        Returns list of Job with title, location, url, description.
        """
        if not page_text or not page_text.strip():
            return []

        # Truncate to avoid token limits
        text = page_text.strip()[:MAX_PAGE_CHARS]
        # Strip excessive whitespace
        text = re.sub(r"\s+", " ", text)

        prompt = (
            "Extract all job postings from this career page. "
            "Return a JSON array of objects. Each object MUST have: title (string), url (string or full URL). "
            "Optional: location (string), description (string, max 200 chars).\n\n"
            f"Company: {company}\n\n"
            "Page content:\n"
            f"{text}\n\n"
            "Return ONLY valid JSON array, no markdown, no extra text. Example: "
            '[{"title": "Software Engineer", "url": "https://example.com/job/1", "location": "Amman"}]'
        )

        try:
            with httpx.Client(timeout=90.0) as client:
                resp = client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "format": "json",
                        "stream": False,
                    },
                )
                resp.raise_for_status()
                raw = resp.json().get("response", "[]")
        except Exception as e:
            logger.error("JobExtractor Ollama failed: %s", e)
            return []

        raw = raw.strip()
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        # Handle array wrapped in object
        if raw.startswith("{"):
            parsed = json.loads(raw)
            if "jobs" in parsed:
                arr = parsed["jobs"]
            elif "jobPostings" in parsed:
                arr = parsed["jobPostings"]
            else:
                arr = [parsed]
        else:
            try:
                arr = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("JobExtractor: invalid JSON from LLM")
                return []

        if not isinstance(arr, list):
            arr = [arr]

        jobs: list[Job] = []
        for item in arr:
            if not isinstance(item, dict):
                continue
            title = (item.get("title") or item.get("name") or "").strip()
            url = (item.get("url") or item.get("link") or "").strip()
            if not title or len(title) < 3:
                continue
            if url and not url.startswith("http") and base_url:
                url = base_url.rstrip("/") + ("/" + url.lstrip("/") if not url.startswith("/") else url)
            if not url:
                url = base_url or "#"
            location = (item.get("location") or "").strip() or None
            desc = (item.get("description") or "")[:500] or None
            jobs.append(
                Job(
                    title=title[:200],
                    company=company,
                    location=location,
                    url=url,
                    description=desc,
                    posted_date=None,
                    source="generic_llm",
                )
            )

        return jobs
