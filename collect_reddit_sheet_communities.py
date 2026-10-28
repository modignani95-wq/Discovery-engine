#!/usr/bin/env python3
"""
Dedicated Reddit Collector for the 6 Subreddits and 3 Seed Threads
from the User's Google Sheet Master Directory.
Uses Apify Reddit Scraper with the user's APIFY_API_TOKEN.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("reddit_sheet_collector")

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = DATA_DIR / "reddit_community_posts.json"

TARGET_SUBREDDITS = [
    "mutualfunds",
    "IndianMutualFunds",
    "IndiaInvestments",
    "personalfinanceindia",
    "MutualfundsIndia",
    "FIREIndia"
]

SEED_URLS = [
    "https://www.reddit.com/r/IndianMutualFunds/comments/1xf8mkw/have_you_ever_tried_to_pause_or_cancel_a_sip/",
    "https://www.reddit.com/r/MutualfundsIndia/comments/1ni983p/planning_to_pause_sips_for_a_year_to_build/",
    "https://www.reddit.com/r/IndiaInvestments/comments/e2shtc/should_i_continue_my_sips_or_should_i_pause_them/"
]


def collect_reddit_content(max_items: int = 500) -> list:
    apify_token = os.getenv("APIFY_API_TOKEN", "").strip()
    if not apify_token:
        logger.error("APIFY_API_TOKEN not found in environment!")
        return []

    from apify_client import ApifyClient
    client = ApifyClient(apify_token)

    all_records = []
    seen_ids = set()

    logger.info(f"🚀 Starting Reddit crawl across 6 communities + 3 seed threads via Apify...")

    # 1. Scrape the seed threads and target subreddits
    run_input = {
        "startUrls": [{"url": u} for u in SEED_URLS],
        "subreddits": TARGET_SUBREDDITS,
        "searches": [
            "SIP pause cancel",
            "SIP negative XIRR",
            "Groww autopay mandate",
            "emergency fund SIP",
            "small cap portfolio review"
        ],
        "sort": "new",
        "maxItems": max_items,
        "maxComments": 10,
        "includeComments": True
    }

    try:
        t0 = time.time()
        logger.info("Calling Apify actor 'trudax/reddit-scraper'...")
        run = client.actor("trudax/reddit-scraper").call(run_input=run_input, memory_mbytes=1024)
        dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else getattr(run, "default_dataset_id", None)
        logger.info(f"Apify run finished in {time.time()-t0:.1f}s. Dataset ID: {dataset_id}")

        if dataset_id:
            for item in client.dataset(dataset_id).iterate_items():
                pid = str(item.get("id") or item.get("postId") or "")
                if pid and pid in seen_ids:
                    continue
                if pid:
                    seen_ids.add(pid)

                title = (item.get("title") or "Reddit Discussion").strip()
                body = (item.get("body") or item.get("selftext") or item.get("text") or "").strip()
                subreddit = item.get("subreddit") or item.get("communityName") or "mutualfunds"
                author = item.get("author") or item.get("username") or "Reddit User"
                url = item.get("url") or item.get("postUrl") or f"https://reddit.com/r/{subreddit}"
                date_str = item.get("createdAt") or item.get("postedAt") or item.get("date") or datetime.now(timezone.utc).isoformat()
                upvotes = item.get("upVotes") or item.get("score") or 1
                comments_count = item.get("numberOfComments") or item.get("numComments") or 0

                text_combined = f"[{subreddit}] {title}: {body}".strip() if body else f"[{subreddit}] {title}"

                all_records.append({
                    "post_id": f"reddit_{pid or len(all_records)+1}",
                    "source": f"Reddit (r/{subreddit})",
                    "source_code": "reddit",
                    "source_url": url,
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "text": text_combined,
                    "title": title,
                    "rating": None,
                    "author": f"u/{author}" if not str(author).startswith("u/") else author,
                    "date": date_str,
                    "subreddit": subreddit,
                    "upvotes": upvotes,
                    "comments_count": comments_count,
                    "channel": f"Reddit (r/{subreddit})",
                    "timeframe": "verified_reddit_mine"
                })

        logger.info(f"🎉 Successfully extracted {len(all_records)} Reddit items from Apify.")
    except Exception as e:
        logger.error(f"Error during Apify Reddit collection: {e}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_records, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved to {OUTPUT_FILE}")

    return all_records


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    collect_reddit_content(max_items=count)
