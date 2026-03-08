"""Configuration loading from YAML and environment."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

# Paths (config.py is in src/jobs_scraper/, config/ is at project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
COMPANIES_PATH = CONFIG_DIR / "companies.yaml"
PREFERENCES_PATH = CONFIG_DIR / "preferences.yaml"


def load_yaml(path: Path) -> dict:
    """Load a YAML file, return empty dict if not found."""
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def load_companies() -> dict:
    """Load companies.yaml config."""
    return load_yaml(COMPANIES_PATH)


def load_preferences() -> dict:
    """Load preferences.yaml config."""
    return load_yaml(PREFERENCES_PATH)


def get_env(key: str, default: str | None = None) -> str | None:
    """Get environment variable."""
    return os.environ.get(key, default)


# Environment config
SUPABASE_URL = get_env("SUPABASE_URL")
SUPABASE_KEY = get_env("SUPABASE_KEY")
TELEGRAM_BOT_TOKEN = get_env("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = get_env("TELEGRAM_CHANNEL_ID")
OLLAMA_URL = get_env("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = get_env("OLLAMA_MODEL", "qwen2.5:7b")
