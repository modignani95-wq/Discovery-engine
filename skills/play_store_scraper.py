"""Scrape Google Play Store reviews via google-play-scraper — free, no key needed."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from google_play_scraper import Sort, app as get_app_info, reviews as get_reviews

from skills.base_skill import BaseSkill

PAGE_SIZE = 10


APP_ALIAS_MAP = {
    "behance": "com.behance.behance",
    "pinterest": "com.pinterest",
    "spotify": "com.spotify.music",
    "wealthfront": "com.wealthfront",
    "acorns": "com.acorns.android",
    "public": "com.public.android",
    "instagram": "com.instagram.android",
    "whatsapp": "com.whatsapp",
    "telegram": "org.telegram.messenger",
    "tiktok": "com.zhiliaoapp.musically",
    "twitter": "com.twitter.android",
    "x": "com.twitter.android",
    "youtube": "com.google.android.youtube",
    "netflix": "com.netflix.mediaclient",
    "duolingo": "com.duolingo",
    "uber": "com.ubercab",
    "canva": "com.canva.editor",
    "figma": "com.figma.mirror",
}


def parse_play_store_input(value: str) -> Tuple[str, str]:
    """
    Parse an input string into (canonical_url, package_id).
    Accepts:
      - 'com.behance.behance'
      - 'behance' (mapped to com.behance.behance)
      - 'https://play.google.com/store/apps/details?id=com.behance.behance'
      - 'https://play.google.com/store/apps/details?id=com.behance.behance&hl=en_US'
    """
    value = value.strip().rstrip("#").strip()
    if value.startswith("http"):
        m = re.search(r"[?&]id=([a-zA-Z0-9._]+)", value)
        if not m:
            m = re.search(r"/details/([a-zA-Z0-9._]+)", value)
        if not m:
            raise ValueError(f"Cannot find package id in URL: {value}")
        pkg_id = m.group(1)
        return f"https://play.google.com/store/apps/details?id={pkg_id}", pkg_id

    clean = value.lower().strip()
    if clean in APP_ALIAS_MAP:
        pkg_id = APP_ALIAS_MAP[clean]
        return f"https://play.google.com/store/apps/details?id={pkg_id}", pkg_id

    for alias, pkg in APP_ALIAS_MAP.items():
        if alias in clean and ("." not in clean):
            return f"https://play.google.com/store/apps/details?id={pkg}", pkg

    if re.match(r"^[a-zA-Z0-9._]+$", value):
        return f"https://play.google.com/store/apps/details?id={value}", value

    raise ValueError(f"Unrecognised Play Store identifier: '{value}'")


class PlayStoreScraperSkill(BaseSkill):
    """Fetch Google Play Store reviews using google-play-scraper (free, no API key needed)."""

    @property
    def name(self) -> str:
        return "scrape_play_store_reviews"

    @property
    def description(self) -> str:
        return (
            "Scrape Google Play Store reviews using google-play-scraper. "
            "Free, no API key needed. Accepts package ID or Play Store URL."
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "app_id": {
                    "type": "string",
                    "description": "Google Play package name (e.g. com.wealthfront) or full Play Store URL",
                },
                "max_reviews": {
                    "type": "integer",
                    "description": "Max reviews per call (default 10)",
                },
                "page": {
                    "type": "integer",
                    "description": "Page or round number (default 1)",
                },
                "lang": {
                    "type": "string",
                    "description": "Review language (default 'en')",
                },
                "country": {
                    "type": "string",
                    "description": "Store country (default 'us')",
                },
            },
            "required": ["app_id"],
        }

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        raw_input: str = kwargs["app_id"].strip()
        count: int = int(kwargs.get("max_reviews", PAGE_SIZE))
        lang: str = kwargs.get("lang", "en")
        country: str = kwargs.get("country", "us")
        continuation_token = kwargs.get("continuation_token", None)

        try:
            canonical_url, pkg_id = parse_play_store_input(raw_input)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

        print(f"   🤖 Google Play API — app {pkg_id} (fetching {count} reviews)...")

        try:
            raw_reviews, next_token = get_reviews(
                pkg_id,
                lang=lang,
                country=country,
                sort=Sort.NEWEST,
                count=count,
                continuation_token=continuation_token,
            )

            reviews_data: List[Dict[str, Any]] = []
            for r in raw_reviews:
                text = (r.get("content") or "").strip()
                if not text:
                    continue
                at = r.get("at")
                date_str = at.isoformat() if hasattr(at, "isoformat") else str(at or "")
                reviews_data.append(
                    {
                        "id": str(r.get("reviewId", "")),
                        "text": text,
                        "title": "",
                        "rating": int(r.get("score")) if r.get("score") is not None else None,
                        "author": r.get("userName") or "Anonymous",
                        "date": date_str,
                        "thumbs_up": r.get("thumbsUpCount", 0),
                        "version": r.get("reviewCreatedVersion") or r.get("appVersion") or "",
                        "app_id": pkg_id,
                    }
                )

            print(f"   ✅ Got {len(reviews_data)} reviews for {pkg_id}")

            return {
                "success": True,
                "data": {
                    "app_id": pkg_id,
                    "app_url": canonical_url,
                    "review_count": len(reviews_data),
                    "continuation_token": next_token,
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                    "reviews": reviews_data,
                },
            }
        except Exception as exc:
            print(f"   ❌ Failed to scrape Play Store for {pkg_id}: {exc}")
            return {"success": False, "error": str(exc)}
