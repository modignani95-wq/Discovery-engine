#!/usr/bin/env python3
"""
Update Apple App Store reviews to 3,000+ reviews.
Preserves the existing 40,000 Play Store reviews and other sources,
fetches 3,000+ Apple App Store reviews, re-runs the SIP discovery pipeline,
and saves the updated cache.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

from dotenv import load_dotenv
load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("update_appstore_3k")

BASE_DIR = Path(__file__).parent
GROWW_CACHE_FILE = BASE_DIR / "groww_cache.json"
GROWW_SIP_CACHE_FILE = BASE_DIR / "groww_sip_cache.json"


def main():
    logger.info("=" * 70)
    logger.info("🚀 FETCHING 3,000+ APPLE APP STORE REVIEWS & UPDATING CACHE")
    logger.info("=" * 70)

    # 1. Load existing cache
    if not GROWW_CACHE_FILE.exists():
        logger.error(f"{GROWW_CACHE_FILE.name} not found!")
        return

    with open(GROWW_CACHE_FILE, "r", encoding="utf-8") as f:
        cache_data = json.load(f)

    existing_records = cache_data.get("records", [])
    logger.info(f"Loaded existing cache with {len(existing_records):,} records.")

    # Filter out old app_store records
    non_appstore_records = [r for r in existing_records if r.get("source_code") != "app_store"]
    logger.info(f"Retained {len(non_appstore_records):,} non-App Store records (Play Store, TradingQ&A, YouTube, Reddit, Social).")

    # 2. Fetch 3,000+ Apple App Store reviews
    from groww_collector import fetch_app_store_reviews, SOURCE_METADATA
    t0 = time.time()
    logger.info("Fetching 3,000+ Apple App Store reviews for Groww iOS (1404871703)...")
    new_ios_reviews = fetch_app_store_reviews(count=3000)
    fetch_time = round(time.time() - t0, 1)
    logger.info(f"✓ Retrieved {len(new_ios_reviews):,} Apple App Store reviews in {fetch_time}s!")

    # 3. Combine records
    all_records = new_ios_reviews + non_appstore_records
    total_records = len(all_records)

    # Update breakdown
    source_breakdown = {}
    for r in all_records:
        sc = r.get("source_code", "play_store")
        source_breakdown[sc] = source_breakdown.get(sc, 0) + 1

    cache_data["records"] = all_records
    cache_data["total_records"] = total_records
    cache_data["source_breakdown"] = source_breakdown
    cache_data["collected_at"] = datetime.now(timezone.utc).isoformat()
    cache_data["elapsed_seconds"] = fetch_time

    logger.info(f"Combined total records: {total_records:,}")
    for sc, count in source_breakdown.items():
        name = SOURCE_METADATA.get(sc, {}).get("name", sc)
        logger.info(f"   • {name}: {count:,} records")

    # 4. Save updated groww_cache.json
    logger.info(f"Saving updated {GROWW_CACHE_FILE.name}...")
    with open(GROWW_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, ensure_ascii=False)
    logger.info(f"✓ Saved {GROWW_CACHE_FILE.name} ({GROWW_CACHE_FILE.stat().st_size / (1024*1024):.1f} MB)")

    # 5. Re-run SIP discovery pipeline over all records
    logger.info(f"Running 7-stage SIP Discovery Pipeline across all {total_records:,} records...")
    sip_t0 = time.time()
    from sip_discovery_engine import run_sip_pipeline, get_opportunity_summary

    llm = None
    try:
        from llm_client import create_llm_client
        llm = create_llm_client(os.getenv("LLM_PROVIDER", "gemini"))
    except Exception:
        llm = None

    sip_result = run_sip_pipeline(
        all_records,
        source_url="https://apps.apple.com/in/app/groww-stocks-mutual-fund-ipo/id1404871703",
        llm_client=llm,
    )
    logger.info(f"✓ SIP Pipeline completed in {time.time() - sip_t0:.2f}s.")

    stages = sip_result.get("stages", {})
    logger.info(f"   • Relevant SIP Conversations: {stages.get('filter', {}).get('kept', 0):,}")
    logger.info(f"   • Structured Extractions: {stages.get('extract', {}).get('total', 0):,}")

    hypotheses = get_opportunity_summary(sip_result)
    logger.info(f"   • Problem Hypotheses: {len(hypotheses)}")
    for h in hypotheses[:3]:
        logger.info(f"     #{h.get('rank')}: {h.get('label')} (Score: {h.get('scores', {}).get('composite')})")

    # Save SIP Cache
    with open(GROWW_SIP_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(sip_result, f, ensure_ascii=False)
    logger.info(f"✓ Saved {GROWW_SIP_CACHE_FILE.name}")

    logger.info("=" * 70)
    logger.info(f"🎉 APP STORE 3,000+ SCALE EXPANSION COMPLETE!")
    logger.info(f"   Apple App Store: {len(new_ios_reviews):,} reviews")
    logger.info(f"   Google Play Store: {source_breakdown.get('play_store', 0):,} reviews")
    logger.info(f"   Total Combined Dataset: {total_records:,} conversations")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
