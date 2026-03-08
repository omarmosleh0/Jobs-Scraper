"""Relevance scoring: score jobs against user profile via Ollama or keyword matching."""

import json
import logging
from typing import Any

import httpx

from jobs_scraper.config import load_preferences, OLLAMA_MODEL, OLLAMA_URL
from jobs_scraper.models import Job

logger = logging.getLogger(__name__)


def _load_profile() -> dict[str, Any]:
    """Load user profile from preferences."""
    prefs = load_preferences()
    return prefs.get("user_profile", {})


class RelevanceScorer:
    """Score job relevance 0.0-1.0 against user profile."""

    def __init__(
        self,
        ollama_url: str | None = None,
        model: str | None = None,
        fallback_to_keywords: bool = True,
    ):
        prefs = load_preferences()
        ai_config = prefs.get("ai", {})
        self.ollama_url = (ollama_url or ai_config.get("ollama_url") or OLLAMA_URL).rstrip("/")
        self.model = model or ai_config.get("model") or OLLAMA_MODEL
        self.fallback_to_keywords = fallback_to_keywords

    def score(self, job: Job) -> float:
        """Score job relevance. Returns 0.0-1.0."""
        try:
            return self._score_ollama(job)
        except Exception as e:
            logger.warning("Ollama relevance scoring failed: %s", e)
            if self.fallback_to_keywords:
                return self._score_keywords(job)
            return 0.5

    def _score_ollama(self, job: Job) -> float:
        """Score via Ollama."""
        profile = _load_profile()
        skills = profile.get("skills", [])
        categories = profile.get("preferred_categories", [])
        locations = profile.get("preferred_locations", [])

        prompt = (
            "Score how relevant this job is to a candidate with these preferences.\n"
            "Candidate skills: " + ", ".join(skills[:10]) + "\n"
            "Preferred categories: " + ", ".join(categories) + "\n"
            "Preferred locations: " + ", ".join(locations) + "\n\n"
            f"Job title: {job.title}\n"
            f"Company: {job.company}\n"
            f"Location: {job.location or 'Unknown'}\n"
            f"Category: {job.category or 'unknown'}\n"
            f"Description snippet: {(job.description or '')[:200]}\n\n"
            "Return ONLY valid JSON with no extra text: {\"score\": 0.0-1.0, \"reason\": \"brief reason\"}\n"
        )

        with httpx.Client(timeout=30.0) as client:
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
            text = resp.json().get("response", "{}").strip()
            if "```" in text:
                text = text.split("```")[1].replace("json", "").strip()
            parsed = json.loads(text)
            score = float(parsed.get("score", 0.5))
            return max(0.0, min(1.0, score))
        return 0.5

    def _score_keywords(self, job: Job) -> float:
        """Fallback: keyword-based relevance."""
        profile = _load_profile()
        skills = [s.lower() for s in profile.get("skills", [])]
        categories = [c.lower() for c in profile.get("preferred_categories", [])]
        locations = [l.lower() for l in profile.get("preferred_locations", [])]

        text = f"{job.title} {job.company} {(job.location or '')} {(job.description or '')}".lower()
        cat = (job.category or "").lower()

        score = 0.5
        if skills:
            matches = sum(1 for s in skills if s in text)
            score += 0.1 * min(matches, 3)
        if cat in categories:
            score += 0.2
        if locations:
            loc_match = any(l in text for l in locations)
            if loc_match:
                score += 0.1
        return min(1.0, score)
