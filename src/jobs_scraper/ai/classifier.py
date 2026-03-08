"""Job classification via Ollama or keyword fallback."""

import json
import logging
from typing import Any

import httpx

from jobs_scraper.config import load_preferences, OLLAMA_MODEL, OLLAMA_URL
from jobs_scraper.models import Job

logger = logging.getLogger(__name__)

CATEGORIES = ["data", "ai_ml", "backend", "software_engineer", "other"]


class JobClassifier:
    """Classify jobs into categories using Ollama or keyword fallback."""

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
        self._keyword_map = self._build_keyword_map(prefs.get("categories", {}))

    def _build_keyword_map(self, categories: dict) -> dict[str, list[str]]:
        """Build category -> keywords map for fallback."""
        result = {}
        for cat, config in categories.items():
            if isinstance(config, dict) and "keywords" in config:
                result[cat] = [k.lower() for k in config["keywords"]]
            else:
                result[cat] = []
        return result

    def classify(self, job: Job) -> tuple[str, float]:
        """Classify a job. Returns (category, confidence)."""
        try:
            return self._classify_ollama(job)
        except Exception as e:
            logger.warning("Ollama classification failed: %s", e)
            if self.fallback_to_keywords:
                return self._classify_keywords(job)
            return ("other", 0.5)

    def _classify_ollama(self, job: Job) -> tuple[str, float]:
        """Classify using Ollama."""
        desc = (job.description or "")[:500]
        prompt = (
            "Classify this job into exactly one category: data, ai_ml, backend, software_engineer, other.\n"
            "Return ONLY valid JSON with no extra text: {\"category\": \"...\", \"confidence\": 0.0-1.0}\n\n"
            f"Title: {job.title}\nCompany: {job.company}\nDescription: {desc}"
        )
        with httpx.Client(timeout=60.0) as client:
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
            result = resp.json()
            text = result.get("response", "{}")
            # Ollama may wrap in markdown or add extra text
            text = text.strip()
            if "```" in text:
                text = text.split("```")[1].replace("json", "").strip()
            parsed = json.loads(text)
            cat = (parsed.get("category") or "other").lower()
            if cat not in CATEGORIES:
                cat = "other"
            conf = float(parsed.get("confidence", 0.7))
            conf = max(0.0, min(1.0, conf))
            return (cat, conf)
        return ("other", 0.5)

    def _classify_keywords(self, job: Job) -> tuple[str, float]:
        """Fallback: classify by keyword matching."""
        text = f"{job.title} {job.company} {(job.description or '')}".lower()
        best_cat = "other"
        best_score = 0.0
        for cat, keywords in self._keyword_map.items():
            if not keywords:
                continue
            matches = sum(1 for k in keywords if k in text)
            if matches > 0:
                score = matches / len(keywords)
                if score > best_score:
                    best_score = score
                    best_cat = cat
        confidence = min(0.9, 0.5 + best_score * 0.4) if best_cat != "other" else 0.5
        return (best_cat, confidence)
