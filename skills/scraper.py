"""Scrape Google Play Store reviews via google-play-scraper — free, no API key needed."""

from __future__ import annotations

import os
from typing import Any, Dict, List

from dotenv import load_dotenv

from skills.base_skill import BaseSkill
from skills.play_store_scraper import PlayStoreScraperSkill, parse_play_store_input

load_dotenv()


class ScraperSkill(BaseSkill):
    """Fetch Play Store reviews for a given Android package id or Play Store URL."""

    def __init__(self):
        self._delegate = PlayStoreScraperSkill()

    @property
    def name(self) -> str:
        return "scrape_reviews"

    @property
    def description(self) -> str:
        return (
            "Scrape user reviews from Google Play Store for one app. "
            "Accepts package name (e.g. com.wealthfront) or full Play Store URL. "
            "Returns review text, star rating, author name, and date."
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "app_id": {
                    "type": "string",
                    "description": "Android package name (e.g. com.wealthfront) or full Play Store URL",
                },
                "max_reviews": {
                    "type": "integer",
                    "description": "Maximum number of reviews to fetch (default 50)",
                },
            },
            "required": ["app_id"],
        }

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        return self._delegate.execute(**kwargs)
