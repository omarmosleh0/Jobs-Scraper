# Jordan Tech Jobs Scraper

AI-powered job scraper for Jordan tech companies. Monitors job boards (Akhtaboot, Bayt, Indeed) and company career pages for Data, AI/ML, and Backend positions. Uses Ollama for local LLM classification and sentence-transformers for deduplication.

## Quick Start

1. Install Ollama and pull a model: `ollama pull qwen2.5:7b`
2. Set up Supabase (run `supabase/schema.sql`)
3. Create a Telegram bot and channel
4. Copy `.env.example` to `.env` and fill in your credentials
5. Run: `pip install -e .` then `python -m jobs_scraper.cli run` (or `jobs-scraper run` if in venv)

## Manual Setup

See [Manual Steps Required](docs/MANUAL_SETUP.md) for detailed setup instructions.
