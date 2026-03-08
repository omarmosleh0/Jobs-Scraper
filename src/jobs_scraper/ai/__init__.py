"""AI layer: Ollama classification, embeddings, relevance scoring, digest, extraction."""

from jobs_scraper.ai.classifier import JobClassifier
from jobs_scraper.ai.digest import DigestGenerator
from jobs_scraper.ai.embeddings import JobEmbedder
from jobs_scraper.ai.extractor import JobExtractor
from jobs_scraper.ai.scorer import RelevanceScorer

__all__ = ["JobClassifier", "JobEmbedder", "RelevanceScorer", "DigestGenerator", "JobExtractor"]
