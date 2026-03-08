"""Job embeddings for deduplication using sentence-transformers."""

import logging
from typing import Any

from jobs_scraper.config import load_preferences
from jobs_scraper.models import Job

logger = logging.getLogger(__name__)


class JobEmbedder:
    """Generate embeddings for jobs using sentence-transformers (local, free)."""

    def __init__(self, model_name: str | None = None):
        prefs = load_preferences()
        ai_config = prefs.get("ai", {})
        self.model_name = model_name or ai_config.get("embedding_model", "all-MiniLM-L6-v2")
        self._model: Any = None

    @property
    def model(self):
        """Lazy load the model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_name)
            except Exception as e:
                logger.error("Failed to load embedding model: %s", e)
                raise
        return self._model

    def embed(self, job: Job) -> list[float]:
        """Generate embedding for a job (title + company + location)."""
        text = f"{job.company} {job.title} {job.location or ''}".strip()
        if not text:
            text = job.url or "unknown"
        vec = self.model.encode(text)
        return vec.tolist()

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        import math

        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
