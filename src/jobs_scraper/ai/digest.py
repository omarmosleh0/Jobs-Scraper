"""AI-generated daily digest: natural language summary of new jobs for Telegram."""

import logging
from datetime import datetime

import httpx

from jobs_scraper.config import load_preferences, OLLAMA_MODEL, OLLAMA_URL
from jobs_scraper.models import Job

logger = logging.getLogger(__name__)


class DigestGenerator:
    """Generate a 3-5 sentence natural language digest of new jobs via Ollama."""

    def __init__(
        self,
        ollama_url: str | None = None,
        model: str | None = None,
        fallback_to_simple: bool = True,
    ):
        prefs = load_preferences()
        ai_config = prefs.get("ai", {})
        self.ollama_url = (ollama_url or ai_config.get("ollama_url") or OLLAMA_URL).rstrip("/")
        self.model = model or ai_config.get("model") or OLLAMA_MODEL
        self.fallback_to_simple = fallback_to_simple

    def generate(self, new_jobs: list[Job]) -> str:
        """Generate digest. Falls back to simple summary if Ollama fails."""
        if not new_jobs:
            return "No new jobs today."

        try:
            return self._generate_ollama(new_jobs)
        except Exception as e:
            logger.warning("Ollama digest generation failed: %s", e)
            if self.fallback_to_simple:
                return self._generate_simple(new_jobs)
            return self._generate_simple(new_jobs)

    def _generate_ollama(self, new_jobs: list[Job]) -> str:
        """Generate digest via Ollama."""
        jobs_summary = "\n".join(
            f"- {j.title} @ {j.company} ({j.location or 'N/A'}) [{j.category or 'other'}]"
            for j in new_jobs[:15]
        )

        prompt = (
            "Write a brief 3-5 sentence daily jobs digest for a Telegram channel. "
            "Focus on Jordan/MENA tech jobs. Highlight top companies and standout roles (Data, AI/ML, Backend). "
            "Be concise and engaging.\n\n"
            f"New jobs ({len(new_jobs)} total):\n{jobs_summary}\n\n"
            "Return ONLY the digest text, no JSON, no labels."
        )

        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                },
            )
            resp.raise_for_status()
            text = resp.json().get("response", "").strip()
            if text and len(text) > 50:
                return text[:800]
        return self._generate_simple(new_jobs)

    def _generate_simple(self, new_jobs: list[Job]) -> str:
        """Simple fallback: structured summary without LLM."""
        by_cat: dict[str, int] = {}
        by_company: dict[str, int] = {}
        for j in new_jobs:
            cat = j.category or "other"
            by_cat[cat] = by_cat.get(cat, 0) + 1
            by_company[j.company] = by_company.get(j.company, 0) + 1

        date_str = datetime.now().strftime("%b %d, %Y")
        lines = [
            f"📊 Daily Jobs Report - {date_str}",
            "━━━━━━━━━━━━━━━━━━━━",
            f"New jobs found: {len(new_jobs)}",
        ]
        if by_cat:
            cat_str = " | ".join(f"{k}: {v}" for k, v in sorted(by_cat.items()))
            lines.append(f"  {cat_str}")
        if by_company:
            top = sorted(by_company.items(), key=lambda x: -x[1])[:5]
            lines.append("")
            lines.append("Top companies: " + ", ".join(f"{c} ({n})" for c, n in top))
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)
