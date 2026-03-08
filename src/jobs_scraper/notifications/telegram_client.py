"""Telegram channel notifications. Uses sync HTTP and batched messages."""

import logging
import time
from datetime import datetime

import httpx

from jobs_scraper.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
from jobs_scraper.models import Job

logger = logging.getLogger(__name__)

# Telegram message limit
TELEGRAM_MAX_LENGTH = 4096
TELEGRAM_SAFE_LENGTH = 4000  # Leave margin
BATCH_DELAY_SEC = 1.0  # Delay between batch messages


def _format_job_compact(job: Job) -> str:
    """Format a single job in compact form for batching."""
    loc = (job.location or "Jordan").strip()
    cat = f" #{job.category}" if job.category else ""
    return f"🔹 {job.title} @ {job.company} | {loc}{cat}\n🔗 {job.url}\n"


def _build_batched_messages(jobs: list[Job]) -> list[str]:
    """Build message chunks, each under TELEGRAM_SAFE_LENGTH chars. Jobs separated by --------."""
    date_str = datetime.now().strftime("%b %d, %Y")
    header = (
        f"📊 New Jobs - {date_str} ({len(jobs)} total)\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    sep = "\n\n--------\n\n"
    chunks: list[str] = []
    current = header
    for i, job in enumerate(jobs):
        line = _format_job_compact(job)
        to_add = (sep + line) if current != header else line
        if len(current) + len(to_add) > TELEGRAM_SAFE_LENGTH:
            chunks.append(current.rstrip())
            part_num = len(chunks) + 1
            current = f"📋 Part {part_num}\n\n{line}"
        else:
            current += to_add
    if current.strip():
        chunks.append(current.rstrip())
    return chunks


def _format_job_message(job: Job) -> str:
    """Format a single job for Telegram (full format, used when sending one job)."""
    cat_tag = f"#{job.category}" if job.category else ""
    loc = job.location or "Jordan"
    return (
        f"🔹 {job.title}\n"
        f"🏢 {job.company}\n"
        f"📍 {loc}\n"
        f"{f'🏷️ {cat_tag}' if cat_tag else ''}\n"
        f"🔗 {job.url}\n\n"
        f"Via: {job.source}"
    )


def _format_summary(new_count: int, by_category: dict[str, int], by_company: dict[str, int]) -> str:
    """Format daily summary for Telegram."""
    date_str = datetime.now().strftime("%b %d, %Y")
    lines = [
        f"📊 Daily Jobs Report - {date_str}",
        "━━━━━━━━━━━━━━━━━━━━",
        f"New jobs found: {new_count}",
    ]
    if by_category:
        cat_str = " | ".join(f"{k}: {v}" for k, v in sorted(by_category.items()))
        lines.append(f"  {cat_str}")
    if by_company:
        top = sorted(by_company.items(), key=lambda x: -x[1])[:5]
        lines.append("")
        lines.append("Top companies: " + ", ".join(f"{c} ({n})" for c, n in top))
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


class TelegramNotifier:
    """Post job notifications to a Telegram channel. Uses batched messages."""

    def __init__(self, bot_token: str | None = None, channel_id: str | None = None):
        self.bot_token = (bot_token or TELEGRAM_BOT_TOKEN or "").strip()
        self.channel_id = (channel_id or TELEGRAM_CHANNEL_ID or "").strip()
        self._api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

    def _send(self, text: str, disable_preview: bool = True, retries: int = 3) -> bool:
        """Send a message via Telegram REST API (sync). Retries on 429 flood control."""
        if not self.bot_token or not self.channel_id:
            raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID must be set")
        payload = {
            "chat_id": self.channel_id,
            "text": text,
            "disable_web_page_preview": str(disable_preview).lower(),
        }
        for attempt in range(retries):
            try:
                with httpx.Client(timeout=30.0) as client:
                    resp = client.post(self._api_url, data=payload)
                    data = resp.json()
                    if data.get("ok"):
                        return True
                    err = data.get("description", resp.text)
                    if resp.status_code == 429:
                        retry_after = data.get("parameters", {}).get("retry_after", 40)
                        logger.warning("Telegram flood control, waiting %ds before retry", retry_after)
                        time.sleep(retry_after)
                        continue
                    logger.error("Telegram API error: %s", err)
                    return False
            except httpx.TimeoutException:
                logger.warning("Telegram send timed out (attempt %d/%d)", attempt + 1, retries)
                if attempt < retries - 1:
                    time.sleep(5)
                else:
                    return False
            except Exception as e:
                logger.error("Telegram send failed: %s", e)
                return False
        return False

    def send_job(self, job: Job) -> bool:
        """Send a single job to the channel."""
        return self.send_jobs([job]) == 1

    def send_jobs_batched(self, jobs: list[Job]) -> int:
        """Send all jobs in batched messages (each under 4096 chars). Jobs separated by --------. Returns count of messages sent."""
        if not jobs:
            return 0
        chunks = _build_batched_messages(jobs)
        sent = 0
        for i, text in enumerate(chunks):
            if i > 0:
                time.sleep(BATCH_DELAY_SEC)
            if self._send(text):
                sent += 1
        return sent

    def send_jobs(self, jobs: list[Job]) -> int:
        """Send multiple jobs using batched messages with -------- separator between each job."""
        return self.send_jobs_batched(jobs)

    def send_summary(self, new_jobs: list[Job]) -> bool:
        """Send daily summary message (simple format)."""
        if not new_jobs:
            return True
        by_cat: dict[str, int] = {}
        by_company: dict[str, int] = {}
        for j in new_jobs:
            cat = j.category or "other"
            by_cat[cat] = by_cat.get(cat, 0) + 1
            by_company[j.company] = by_company.get(j.company, 0) + 1
        text = _format_summary(len(new_jobs), by_cat, by_company)
        return self.send_summary_text(text)

    def send_summary_text(self, text: str) -> bool:
        """Send a pre-formatted summary/digest message."""
        if not text:
            return True
        return self._send(text)
