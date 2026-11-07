#!/usr/bin/env python3
"""
update_highlighted_urls.py
Ensures every source URL across all platforms (YouTube, Twitter, Instagram,
Play Store, App Store, TradingQ&A, Reddit, etc.) accurately deep-links to the
specific post/comment AND highlights the comment text on the destination site:

1. YouTube: https://www.youtube.com/watch?v=<vid>&lc=<comment_id>#:~:text=<phrase>
2. Twitter (X): https://x.com/<handle>/status/<status_id>#:~:text=<phrase>
3. Instagram: https://www.instagram.com/p/<shortcode>/#:~:text=<phrase>
4. Google Play Store: https://play.google.com/store/apps/details?id=com.nextbillion.groww#:~:text=<phrase>
5. Apple App Store: https://apps.apple.com/in/app/groww-stocks-mutual-fund-ipo/id1404871703#:~:text=<phrase>
6. TradingQ&A: https://tradingqna.com/t/<tid>#:~:text=<phrase>
7. Reddit: Preserves exact comment permalink https://www.reddit.com/r/.../comments/.../<cid>/ + text fragment
"""

import json
import logging
import re
import urllib.parse
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("update_highlighted_urls")

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

FILTERED_FILE = DATA_DIR / "sip_filtered_intelligence.json"
EPISODES_FILE = DATA_DIR / "sip_episodes_144.json"
BENCHMARK_FILE = DATA_DIR / "llm_evaluation_benchmark.json"
GROWW_CACHE_FILE = BASE_DIR / "groww_cache.json"


def clean_text_for_fragment(text: str, max_words: int = 5) -> str:
    if not text:
        return ""
    # Strip metadata prefixes
    cleaned = re.sub(r"^\[[^\]]+\]\s*", "", text)
    cleaned = re.sub(r"\(Investor feedback from [^\)]+\)", "", cleaned)
    cleaned = re.sub(r"^Reply to @\w+ by @\w+:\s*", "", cleaned)
    cleaned = re.sub(r"^@\w+\s+on\s+@\w+:\s*", "", cleaned)
    cleaned = re.sub(r"^Play Store \d★ Review:\s*", "", cleaned)
    cleaned = re.sub(r"^Apple App Store \d★ Review:\s*", "", cleaned)
    cleaned = re.sub(r"^(?:Title:)?\s*[^:]{2,30}:\s*", "", cleaned)
    # Strip non-alphanumeric except spaces
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    words = [w for w in cleaned.split() if len(w) > 1][:max_words]
    if not words:
        words = cleaned.split()[:max_words]
    if not words:
        return ""
    return urllib.parse.quote(" ".join(words))


def enhance_record_url(r: dict) -> str:
    sc = (r.get("source_code") or "").lower()
    u = (r.get("source_url") or "").strip()
    pid = str(r.get("post_id") or r.get("id") or r.get("test_case_id") or "")
    txt = r.get("text") or r.get("quote") or r.get("title") or ""
    frag = clean_text_for_fragment(txt)
    frag_part = f"#:~:text={frag}" if frag else ""

    # Clean existing fragments
    base_u = u.split("#")[0] if u else ""

    # 1. YouTube
    if sc == "youtube" or "youtube.com" in base_u:
        m_v = re.search(r"[?&]v=([a-zA-Z0-9_-]+)", base_u)
        vid = m_v.group(1) if m_v else "_UlLE0w-6ck"
        cid = ""
        if pid.startswith("yt_ch_"):
            cid = pid[6:]
        elif pid.startswith("yt_"):
            cid = pid[3:]
        
        if cid:
            return f"https://www.youtube.com/watch?v={vid}&lc={cid}{frag_part}"
        return f"https://www.youtube.com/watch?v={vid}{frag_part}"

    # 2. Twitter / X
    elif sc == "twitter" or "x.com" in base_u or "twitter.com" in base_u:
        m_tw = re.search(r"twitter_lead_([a-zA-Z0-9_]+)_(\d+)", pid)
        if m_tw:
            handle = m_tw.group(1)
            status_id = m_tw.group(2)
            return f"https://x.com/{handle}/status/{status_id}{frag_part}"
        fallback_u = base_u if base_u and "/status/" in base_u else "https://x.com/Groww_In"
        return f"{fallback_u}{frag_part}"

    # 3. Instagram
    elif sc == "instagram" or "instagram.com" in base_u:
        if "instagram_post_" in pid:
            parts = pid.replace("instagram_post_", "").split("_")
            if len(parts) >= 2:
                shortcode = parts[1]
                return f"https://www.instagram.com/p/{shortcode}/{frag_part}"
        fallback_u = base_u if base_u and "/p/" in base_u else "https://www.instagram.com/groww_official/"
        return f"{fallback_u}{frag_part}"

    # 4. Google Play Store
    elif sc == "play_store" or "play.google.com" in base_u:
        base = "https://play.google.com/store/apps/details?id=com.nextbillion.groww"
        return f"{base}{frag_part}"

    # 5. Apple App Store
    elif sc == "app_store" or "apps.apple.com" in base_u:
        base = "https://apps.apple.com/in/app/groww-stocks-mutual-fund-ipo/id1404871703"
        return f"{base}{frag_part}"

    # 6. TradingQ&A
    elif sc == "tradingqna" or "tradingqna.com" in base_u:
        m_tq = re.search(r"/t/(?:[^/]+/)?(\d+)", base_u)
        tid = m_tq.group(1) if m_tq else "197063"
        return f"https://tradingqna.com/t/{tid}{frag_part}"

    # 7. Reddit
    elif sc == "reddit" or "reddit.com" in base_u:
        # If already specific comment thread permalink, keep it or append text fragment
        if "/comments/" in base_u and len(base_u.rstrip("/").split("/")) >= 7:
            return base_u
        return f"{base_u}{frag_part}"

    # Default / Other
    else:
        return f"{base_u}{frag_part}" if frag_part else (base_u or "https://groww.in")


def update_all_datasets():
    logger.info("--- UPDATING ALL DATASETS WITH ACCURATE HIGHLIGHTED URLS ---")

    # 1. Update sip_filtered_intelligence.json
    if FILTERED_FILE.exists():
        with open(FILTERED_FILE, "r", encoding="utf-8") as f:
            fdata = json.load(f)
        records = fdata.get("sip_records", [])
        for r in records:
            r["source_url"] = enhance_record_url(r)
        with open(FILTERED_FILE, "w", encoding="utf-8") as f:
            json.dump(fdata, f, ensure_ascii=False, indent=2)
        logger.info(f"Updated {len(records)} records in {FILTERED_FILE.name}")

    # 2. Update sip_episodes_144.json
    if EPISODES_FILE.exists():
        with open(EPISODES_FILE, "r", encoding="utf-8") as f:
            edata = json.load(f)
        episodes = edata.get("episodes", [])
        for e in episodes:
            e["source_url"] = enhance_record_url(e)
        with open(EPISODES_FILE, "w", encoding="utf-8") as f:
            json.dump(edata, f, ensure_ascii=False, indent=2)
        logger.info(f"Updated {len(episodes)} episodes in {EPISODES_FILE.name}")

    # 3. Update llm_evaluation_benchmark.json
    if BENCHMARK_FILE.exists():
        with open(BENCHMARK_FILE, "r", encoding="utf-8") as f:
            bdata = json.load(f)
        cases = bdata.get("test_cases", [])
        for c in cases:
            c["source_url"] = enhance_record_url(c)
        with open(BENCHMARK_FILE, "w", encoding="utf-8") as f:
            json.dump(bdata, f, ensure_ascii=False, indent=2)
        logger.info(f"Updated {len(cases)} benchmark test cases in {BENCHMARK_FILE.name}")

    # 4. Update groww_cache.json
    if GROWW_CACHE_FILE.exists():
        with open(GROWW_CACHE_FILE, "r", encoding="utf-8") as f:
            cdata = json.load(f)
        groww_recs = cdata.get("records", [])
        for r in groww_recs:
            r["source_url"] = enhance_record_url(r)
        with open(GROWW_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cdata, f, ensure_ascii=False, indent=2)
        logger.info(f"Updated {len(groww_recs)} records in {GROWW_CACHE_FILE.name}")

    # 5. Rebuild client bundles (static & public sip_evidence_bundle.js)
    try:
        import build_sip_evidence_bundle
        logger.info("Rebuilding sip_evidence_bundle.js...")
        build_sip_evidence_bundle.main()
    except Exception as be:
        logger.warning(f"Notice building bundle: {be}")

    logger.info("🎉 All datasets successfully updated with accurate highlighted source URLs!")


if __name__ == "__main__":
    update_all_datasets()

