#!/usr/bin/env python3
"""
Integrate Play Store and App Store reviews for Groww into the SIP Intelligence Engine.
1. Load existing multi-source records (YouTube, Reddit, TradingQ&A, Forums, Social).
2. Scrape live reviews from Apple App Store (iOS) and Google Play Store (Android).
3. Merge and deduplicate by post_id/text.
4. Save combined pool to groww_cache.json.
5. Run SIP domain filtering and classification via sip_filter_engine.py.
6. Save high-signal SIP conversations to data/sip_filtered_intelligence.json.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("integrate_store_reviews")

from groww_collector import fetch_app_store_reviews, fetch_play_store_reviews
from sip_filter_engine import filter_and_enrich_sip_dataset, is_sip_relevant, classify_sip_category, determine_friction_and_intent

BASE_DIR = Path(__file__).parent
GROWW_CACHE_FILE = BASE_DIR / "groww_cache.json"
SIP_FILTERED_FILE = BASE_DIR / "data" / "sip_filtered_intelligence.json"

def main():
    logger.info("=" * 70)
    logger.info("GROWW APP STORE & PLAY STORE SIP REVIEWS INTEGRATION")
    logger.info("=" * 70)

    # 1. Load ground truth YouTube and Reddit datasets + forum records
    yt_comments = []
    yt_file = BASE_DIR / "data" / "youtube_channel_comments.json"
    if yt_file.exists():
        with open(yt_file, "r", encoding="utf-8") as f:
            yt_comments = json.load(f)
    logger.info(f"Loaded {len(yt_comments):,} ground-truth YouTube comments from 10 channels.")

    reddit_posts = []
    rd_file = BASE_DIR / "data" / "reddit_community_posts.json"
    if rd_file.exists():
        with open(rd_file, "r", encoding="utf-8") as f:
            reddit_posts = json.load(f)
    logger.info(f"Loaded {len(reddit_posts):,} ground-truth Reddit discussions.")

    forum_records = []
    if GROWW_CACHE_FILE.exists():
        try:
            with open(GROWW_CACHE_FILE, "r", encoding="utf-8") as f:
                cdata = json.load(f)
            forum_records = [
                r for r in cdata.get("records", [])
                if r.get("source_code") in ("tradingqna", "social_media", "other_public")
            ]
        except Exception as e:
            logger.warning(f"Error loading forum records: {e}")
    logger.info(f"Loaded {len(forum_records):,} TradingQ&A, social, and forum records.")

    # 2. Fetch live Apple App Store reviews
    target_ios = 1500
    logger.info(f"Fetching up to {target_ios:,} live Apple App Store reviews...")
    ios_reviews = fetch_app_store_reviews(count=target_ios)
    logger.info(f"Retrieved {len(ios_reviews):,} Apple App Store reviews.")

    # 3. Fetch live Google Play Store reviews
    target_play = 2500
    logger.info(f"Fetching up to {target_play:,} live Google Play Store reviews...")
    play_reviews = fetch_play_store_reviews(count=target_play)
    logger.info(f"Retrieved {len(play_reviews):,} Google Play Store reviews.")

    # 4. Merge all sources
    all_combined = yt_comments + reddit_posts + forum_records + ios_reviews + play_reviews
    
    # Proper deduplication by post_id or stripped content
    seen = set()
    deduped = []
    for r in all_combined:
        src = r.get("source_code", "")
        pid = r.get("post_id")
        if pid:
            key = f"{src}_{pid}"
        else:
            clean_body = re.sub(r"^\[[^\]]+\]\s*", "", r.get("text") or "").strip().lower()
            key = f"{src}_{clean_body[:100]}"
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    logger.info(f"Combined Master Pool: {len(deduped):,} total records across 7 sources.")

    # 5. Save updated groww_cache.json
    source_counts = {}
    for r in deduped:
        sc = r.get("source_code", "other")
        source_counts[sc] = source_counts.get(sc, 0) + 1

    cache_payload = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "total_records": len(deduped),
        "source_breakdown": source_counts,
        "app_store_url": "https://apps.apple.com/in/app/groww-stocks-mutual-fund-ipo/id1404871703",
        "play_store_url": "https://play.google.com/store/apps/details?id=com.nextbillion.groww",
        "records": deduped,
    }

    with open(GROWW_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache_payload, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved {len(deduped):,} records to groww_cache.json")

    # 6. Run SIP Filtering & Enrichment
    logger.info("Executing SIP domain filtering and 8-vector classification...")
    filtered_res = filter_and_enrich_sip_dataset(deduped)

    logger.info("=" * 70)
    logger.info("SIP FILTERING & STORE INTEGRATION SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Total Evaluated Records: {filtered_res['total_evaluated']:,}")
    logger.info(f"Total SIP Relevant Items: {filtered_res['total_sip_relevant']:,} ({filtered_res['relevance_rate_pct']}%)")
    logger.info("\nSource Breakdown of Filtered SIP Conversations:")
    for src, count in sorted(filtered_res["source_breakdown"].items(), key=lambda x: -x[1]):
        logger.info(f"  • {src:15s}: {count:,} SIP conversations")

    logger.info("\nSIP Category Vectors:")
    for cat, count in sorted(filtered_res["category_breakdown"].items(), key=lambda x: -x[1]):
        logger.info(f"  • {cat:22s}: {count:,} items")

    logger.info("\nFriction Breakdown:")
    for fric, count in sorted(filtered_res["friction_breakdown"].items(), key=lambda x: -x[1]):
        logger.info(f"  • {fric:25s}: {count:,} items")

    return filtered_res

if __name__ == "__main__":
    main()
