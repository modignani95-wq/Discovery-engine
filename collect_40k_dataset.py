#!/usr/bin/env python3
"""
Enterprise 40,000+ Multi-Source Data Collection & SIP Discovery Engine
Collects 40,000+ public investor conversations across:
1. Google Play Store (Android - com.nextbillion.groww)
2. Apple App Store (iOS - 1404871703)
3. TradingQ&A Investing Community Forums
4. YouTube Comments (Live Google Data API v3)
5. Reddit Indian Investing Subreddits (Apify)
6. Social Media Conversations (Fintech X/Mastodon/Bluesky)
7. Other Public Financial Communities (ValuePickr, DesiDime, Quora)

Runs the complete 7-stage NLP SIP Discovery Engine and updates local cache files.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Fix Windows console UTF-8 output
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
logger = logging.getLogger("groww_40k")

BASE_DIR = Path(__file__).parent
GROWW_CACHE_FILE = BASE_DIR / "groww_cache.json"
GROWW_SIP_CACHE_FILE = BASE_DIR / "groww_sip_cache.json"


def main():
    target_count = 40000
    logger.info("=" * 70)
    logger.info(f"🚀 INITIATING 40,000+ RECORD MULTI-SOURCE RETRIEVAL FOR GROWW")
    logger.info("=" * 70)

    from groww_collector import collect_all_groww_sources, SOURCE_METADATA
    from sip_discovery_engine import run_sip_pipeline, get_opportunity_summary, get_evidence_explorer

    t_start = time.time()

    # Step 1: Collect across all 7 monitored sources
    # Target 40,000 on Play Store, combined with App Store, TradingQ&A, YouTube, Reddit, Social, Forums
    logger.info(f"Stage 1/3: Collecting records across 7 public investment platforms...")
    collection_result = collect_all_groww_sources(
        max_per_source=target_count,
        play_store_limit=target_count,
        app_store_limit=500,
    )

    total_collected = collection_result.get("total_records", 0)
    logger.info(f"✓ Collection finished in {collection_result.get('elapsed_seconds')}s. Total records: {total_collected:,}")

    for source_code, count in collection_result.get("source_breakdown", {}).items():
        name = SOURCE_METADATA.get(source_code, {}).get("name", source_code)
        logger.info(f"   • {name}: {count:,} records")

    # Step 2: Persist collection cache
    logger.info(f"Stage 2/3: Saving {total_collected:,} records to {GROWW_CACHE_FILE.name}...")
    try:
        with open(GROWW_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(collection_result, f, ensure_ascii=False)
        logger.info(f"✓ Saved {GROWW_CACHE_FILE.name} ({GROWW_CACHE_FILE.stat().st_size / (1024*1024):.1f} MB)")
    except Exception as exc:
        logger.error(f"Failed to write groww cache: {exc}")

    # Step 3: Run Full SIP Discovery Pipeline
    logger.info(f"Stage 3/3: Running 7-stage NLP SIP Discovery Pipeline over {total_collected:,} records...")
    sip_t0 = time.time()
    records = collection_result.get("records", [])

    # Initialize LLM if available for sample enrichment
    llm = None
    try:
        from llm_client import create_llm_client
        llm = create_llm_client(os.getenv("LLM_PROVIDER", "gemini"))
    except Exception:
        llm = None

    sip_result = run_sip_pipeline(
        records,
        source_url=collection_result.get("app_store_url", "https://apps.apple.com/in/app/groww-stocks-mutual-fund-ipo/id1404871703"),
        llm_client=llm,
    )
    sip_elapsed = round(time.time() - sip_t0, 2)
    logger.info(f"✓ SIP Pipeline completed in {sip_elapsed}s.")

    stages = sip_result.get("stages", {})
    logger.info(f"   • Total Analyzed: {stages.get('collect', {}).get('total_records', 0):,}")
    logger.info(f"   • Cleaned & Deduplicated: {stages.get('clean', {}).get('kept', 0):,}")
    logger.info(f"   • Relevant SIP Conversations: {stages.get('filter', {}).get('kept', 0):,}")
    logger.info(f"   • Structured Extractions: {stages.get('extract', {}).get('total', 0):,}")

    hypotheses = get_opportunity_summary(sip_result)
    logger.info(f"   • Prioritized Problem Hypotheses: {len(hypotheses)}")
    for h in hypotheses[:3]:
        logger.info(f"     #{h.get('rank')}: {h.get('label')} (Score: {h.get('scores', {}).get('composite')})")

    # Save SIP Cache
    try:
        with open(GROWW_SIP_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(sip_result, f, ensure_ascii=False)
        logger.info(f"✓ Saved {GROWW_SIP_CACHE_FILE.name} ({GROWW_SIP_CACHE_FILE.stat().st_size / (1024*1024):.1f} MB)")
    except Exception as exc:
        logger.error(f"Failed to write SIP cache: {exc}")

    total_time = round(time.time() - t_start, 1)
    logger.info("=" * 70)
    logger.info(f"🎉 40,000+ DATASET & AI ENGINE COMPLETE IN {total_time}s!")
    logger.info(f"   Total Records Cached: {total_collected:,}")
    logger.info(f"   Play Store: {collection_result.get('source_breakdown', {}).get('play_store', 0):,}")
    logger.info(f"   App Store: {collection_result.get('source_breakdown', {}).get('app_store', 0):,}")
    logger.info(f"   TradingQ&A: {collection_result.get('source_breakdown', {}).get('tradingqna', 0):,}")
    logger.info(f"   YouTube Comments: {collection_result.get('source_breakdown', {}).get('youtube', 0):,}")
    logger.info(f"   Reddit: {collection_result.get('source_breakdown', {}).get('reddit', 0):,}")
    logger.info(f"   Social Media: {collection_result.get('source_breakdown', {}).get('social_media', 0):,}")
    logger.info(f"   Other Forums: {collection_result.get('source_breakdown', {}).get('other_public', 0):,}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
