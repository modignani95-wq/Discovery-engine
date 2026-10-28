#!/usr/bin/env python3
"""
Dedicated YouTube Collector for the 10 Specific Financial Channels
listed in the User's Google Sheet Master Directory.
Uses the user's YOUTUBE_API_KEY from .env.
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
logger = logging.getLogger("yt_sheet_collector")

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = DATA_DIR / "youtube_channel_comments.json"

TARGET_CHANNELS = [
    {
        "id": 14,
        "name": "ET Money",
        "handle": "@ETMONEY",
        "channel_id": "UCxv9T8da7658T9R8LQT_3PQ",
        "queries": ["SIP", "mutual funds", "portfolio overlap", "XIRR"],
        "angle": "Deep-dive mutual fund data, SIP behavior studies, asset allocation, and downside protection."
    },
    {
        "id": 15,
        "name": "Shankar Nath",
        "handle": "@shankarnath",
        "channel_id": "UCtnItzU7q_bA1eoEBjqcVrw",
        "queries": ["SIP", "step up SIP", "daily SIP", "index funds"],
        "angle": "SEBI-registered RA focusing on data-backed mutual fund strategies, SIP variations, and mature retail investor psychology."
    },
    {
        "id": 16,
        "name": "Pranjal Kamra (Finology)",
        "handle": "@pranjalkamra",
        "channel_id": "UCwAdQUuPT6laN-AQR17fe1g",
        "queries": ["SIP", "mutual fund mistake", "regular to direct"],
        "angle": "Mass retail beginners & intermediate investors; great comment section for fund-switching anxiety."
    },
    {
        "id": 17,
        "name": "Labour Law Advisor (LLA)",
        "handle": "@LabourLawAdvisor",
        "channel_id": "UCVOTBwF0vnSxMRIbfSE_K_g",
        "queries": ["SIP", "ELSS", "tax saving", "mutual funds"],
        "angle": "Salaried employees, tax-saving (ELSS) SIPs, and personal finance hygiene."
    },
    {
        "id": 18,
        "name": "Zero1 by Zerodha",
        "handle": "@Zero1byZerodha",
        "channel_id": "UCUUlw3anBIkbW9W44Y-eURw",
        "queries": ["SIP", "investing", "psychology", "wealth"],
        "angle": "Behavioral finance, Gen-Z/millennial money habits, and overcoming market noise."
    },
    {
        "id": 19,
        "name": "Freefincal (Pattu)",
        "handle": "@freefincal",
        "channel_id": "UCf5H6aT6NzCQES8OJIhciTw",
        "queries": ["SIP", "sequence of returns", "market crash", "asset allocation"],
        "angle": "Hardcore data & goal-based investing; critiques of blind SIP myths and sequence-of-returns risk."
    },
    {
        "id": 20,
        "name": "Yadnya Investment Academy",
        "handle": "@YadnyaInvestmentAcademy",
        "channel_id": "UCtrJz27bLRkCsgI_0DEXZig",
        "queries": ["SIP", "mutual fund review", "financial planning"],
        "angle": "Comprehensive mutual fund reviews and long-term family financial planning."
    },
    {
        "id": 21,
        "name": "CA Rachana Phadke Ranade",
        "handle": "@CARachanaRanade",
        "channel_id": "UCe3qdG0A_gr-sEdat5y2twQ",
        "queries": ["SIP", "mutual funds for beginners", "compounding"],
        "angle": "First-time investors transitioning from traditional FDs to mutual fund SIPs."
    },
    {
        "id": 22,
        "name": "Asset Yogi",
        "handle": "@AssetYogi",
        "channel_id": "UCsNxHPbaCWL1tKw2hxGQD6g",
        "queries": ["SIP", "compounding", "small cap", "mutual fund"],
        "angle": "Hindi-speaking mass retail belt (Tier-2/Tier-3 cities) learning compounding and SIP basics."
    },
    {
        "id": 23,
        "name": "Ankur Warikoo",
        "handle": "@warikoo",
        "channel_id": "UCRzYN32xtBf3Yxsx5BvJWJw",
        "queries": ["SIP", "first salary", "index fund", "investing"],
        "angle": "Early-career 20-somethings starting their very first ₹500–₹5,000 SIPs."
    }
]


def collect_channel_comments(max_per_channel: int = 150) -> list:
    yt_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not yt_key:
        logger.error("YOUTUBE_API_KEY not found in environment!")
        return []

    from googleapiclient.discovery import build
    yt = build("youtube", "v3", developerKey=yt_key, cache_discovery=False)

    all_comments = []
    seen_comment_ids = set()
    total_start = time.time()

    logger.info(f"🚀 Starting live comment collection from {len(TARGET_CHANNELS)} specific YouTube channels...")

    for ch in TARGET_CHANNELS:
        ch_name = ch["name"]
        ch_handle = ch["handle"]
        ch_id = ch["channel_id"]
        ch_comments = []
        logger.info(f"► Querying Channel: {ch_name} ({ch_handle})...")

        for query in ch["queries"]:
            if len(ch_comments) >= max_per_channel:
                break
            try:
                # Search videos from this channel
                s_resp = yt.search().list(
                    channelId=ch_id,
                    q=query,
                    part="id,snippet",
                    maxResults=5,
                    type="video",
                    order="relevance"
                ).execute()
                video_items = s_resp.get("items", [])
                if not video_items:
                    s_resp2 = yt.search().list(
                        q=f"{ch_name} {query}",
                        part="id,snippet",
                        maxResults=5,
                        type="video",
                        order="relevance"
                    ).execute()
                    video_items = s_resp2.get("items", [])
                for v in video_items:
                    if len(ch_comments) >= max_per_channel:
                        break
                    vid = v.get("id", {}).get("videoId")
                    if not vid:
                        continue
                    v_title = v.get("snippet", {}).get("title", "")
                    v_published = v.get("snippet", {}).get("publishedAt", "")

                    # Fetch comment threads for this video
                    try:
                        ct_resp = yt.commentThreads().list(
                            part="snippet",
                            videoId=vid,
                            maxResults=100,
                            textFormat="plainText",
                            order="relevance"
                        ).execute()

                        for ct in ct_resp.get("items", []):
                            cid = ct.get("id")
                            if cid in seen_comment_ids:
                                continue
                            seen_comment_ids.add(cid)

                            snip = ct.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
                            text = (snip.get("textDisplay") or "").strip()
                            if not text or len(text) < 12:
                                continue

                            author = snip.get("authorDisplayName", "Investor")
                            date_str = snip.get("publishedAt") or v_published
                            likes = snip.get("likeCount", 0)

                            comment_record = {
                                "post_id": f"yt_ch_{cid}",
                                "source": "YouTube Channel Comments",
                                "source_code": "youtube",
                                "source_url": f"https://www.youtube.com/watch?v={vid}",
                                "collected_at": datetime.now(timezone.utc).isoformat(),
                                "text": f"[{ch_name} | {v_title}] {text}",
                                "title": v_title,
                                "rating": None,
                                "author": author,
                                "date": date_str,
                                "channel": f"YouTube ({ch_name} {ch_handle})",
                                "channel_name": ch_name,
                                "channel_handle": ch_handle,
                                "video_id": vid,
                                "likes": likes,
                                "timeframe": "verified_channel_mine"
                            }
                            ch_comments.append(comment_record)
                            all_comments.append(comment_record)

                            if len(ch_comments) >= max_per_channel:
                                break
                    except Exception as ct_err:
                        # Comments may be disabled on some videos
                        pass
            except Exception as s_err:
                logger.warning(f"Error querying {ch_name} for '{query}': {s_err}")
                continue

        logger.info(f"  ✓ {ch_name}: Retrieved {len(ch_comments)} viewer comments.")

    logger.info(f"🎉 Complete! Retrieved total of {len(all_comments)} live comments across {len(TARGET_CHANNELS)} channels in {time.time()-total_start:.1f}s")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_comments, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved to {OUTPUT_FILE}")

    return all_comments


if __name__ == "__main__":
    max_count = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    collect_channel_comments(max_per_channel=max_count)
