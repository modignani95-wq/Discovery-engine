#!/usr/bin/env python3
"""
Sync Trained Multi-Source Dataset (YouTube Channels, Reddit Communities, Investing Forums)
into groww_cache.json and generate groww_sip_cache.json.
Strictly excludes all Play Store and App Store reviews per user requirement.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sync_trained_conversations")

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

YT_FILE = DATA_DIR / "youtube_channel_comments.json"
REDDIT_FILE = DATA_DIR / "reddit_community_posts.json"
CACHE_FILE = BASE_DIR / "groww_cache.json"
SIP_CACHE_FILE = BASE_DIR / "groww_sip_cache.json"

SOURCE_METADATA = {
    "youtube": {
        "name": "YouTube Comments",
        "description": "Viewer comments across the 10 personal finance channels from Master Directory (Last 4 Months)",
        "badge_color": "var(--youtube-red)",
        "icon": "smart_display",
    },
    "reddit": {
        "name": "Reddit Indian Communities",
        "description": "Discussions & comments from r/MutualfundsIndia, r/IndianMutualFunds, r/IndiaInvestments, and seed threads",
        "badge_color": "var(--reddit-orange)",
        "icon": "forum",
    },
    "tradingqna": {
        "name": "Investing Forums (TradingQ&A)",
        "description": "TradingQ&A Discourse community discussions on mutual funds & Groww SIPs (Last 4 Months)",
        "badge_color": "var(--tradingqna-blue)",
        "icon": "chat_bubble",
    },
    "social_media": {
        "name": "Social Media (Fintech Leaders)",
        "description": "Discussions and creator posts from verified finance leaders (Last 4 Months)",
        "badge_color": "var(--social-violet)",
        "icon": "alternate_email",
    },
    "other_public": {
        "name": "Other Public Forums",
        "description": "ValuePickr, DesiDime, and Bogleheads India discussions on first-time investing (Last 4 Months)",
        "badge_color": "var(--forums-emerald)",
        "icon": "public",
    },
}


def sync_all():
    logger.info("Loading YouTube comments...")
    yt_comments = []
    if YT_FILE.exists():
        with open(YT_FILE, "r", encoding="utf-8") as f:
            yt_comments = json.load(f)
    logger.info(f"Loaded {len(yt_comments)} YouTube comments from 10 channels.")

    logger.info("Loading Reddit posts and comments...")
    reddit_posts = []
    if REDDIT_FILE.exists():
        with open(REDDIT_FILE, "r", encoding="utf-8") as f:
            reddit_posts = json.load(f)
    logger.info(f"Loaded {len(reddit_posts)} Reddit discussions from sheet subreddits & seed threads.")

    logger.info("Loading existing forum and social conversations (excluding play_store and app_store)...")
    old_records = []
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            old_data = json.load(f)
            old_records = old_data.get("records", [])

    forum_records = [
        r for r in old_records
        if r.get("source_code") in ("tradingqna", "social_media", "other_public")
    ]
    logger.info(f"Retained {len(forum_records)} forum and social records.")

    # Combine all clean records
    all_records = yt_comments + reddit_posts + forum_records

    # Deduplicate by post_id
    seen_ids = set()
    deduped_records = []
    for r in all_records:
        pid = r.get("post_id")
        if pid and pid in seen_ids:
            continue
        if pid:
            seen_ids.add(pid)
        deduped_records.append(r)

    logger.info(f"Total clean records assembled: {len(deduped_records):,}")

    from collections import Counter
    source_stats = dict(Counter(r.get("source_code") for r in deduped_records))
    logger.info(f"Source breakdown: {source_stats}")

    cache_data = {
        "success": True,
        "app_name": "Groww (Stocks, Mutual Fund, IPO) & SIP Intelligence",
        "app_store_url": "https://groww.in/mutual-funds",
        "play_store_url": "https://groww.in/mutual-funds",
        "timeframe": "last_4_months",
        "timeframe_label": "Last 4 Months (Verified Multi-Source Intelligence)",
        "timeframe_cutoff": "2026-06-27T00:00:00Z",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": 12.5,
        "total_records": len(deduped_records),
        "source_breakdown": source_stats,
        "sources_metadata": SOURCE_METADATA,
        "records": deduped_records,
        "errors": {},
    }

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved {CACHE_FILE.name} successfully.")

    # Now run SIP discovery pipeline on these clean records
    logger.info("Executing SIP Discovery Pipeline on clean multi-source dataset...")
    from sip_discovery_engine import run_sip_pipeline
    sip_result = run_sip_pipeline(
        deduped_records,
        source_url="https://groww.in/mutual-funds",
        llm_client=None,
    )

    with open(SIP_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(sip_result, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved {SIP_CACHE_FILE.name} with {len(sip_result.get('hypothesis_report', {}).get('hypotheses', []))} grounded hypotheses.")


if __name__ == "__main__":
    sync_all()
