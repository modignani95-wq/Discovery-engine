"""
TF-IDF based RAG engine for Google Play Store review analysis.
Uses local TF-IDF for retrieval and Gemini for generation — no embedding API cost.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class RAGEngine:
    """
    Retrieval-Augmented Generation engine.
    - Index: TF-IDF vectorizer over all review texts
    - Retrieve: cosine similarity search
    - Generate: Gemini LLM with retrieved context
    """

    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            max_features=8000,
            stop_words="english",
            ngram_range=(1, 2),
            min_df=1,
        )
        self.reviews_by_app: Dict[str, List[Dict[str, Any]]] = {}
        self.app_info: Dict[str, Dict[str, Any]] = {}   # metadata (rating, review_count, etc.)
        self._chunks: List[str] = []
        self._chunk_meta: List[Dict[str, Any]] = []
        self._matrix = None
        self._built = False

    # ──────────────────────────────────────────
    # Indexing
    # ──────────────────────────────────────────

    def index_app(
        self,
        app_name: str,
        reviews: List[Dict[str, Any]],
        info: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store reviews for one app and rebuild the index."""
        self.reviews_by_app[app_name] = reviews
        if info:
            self.app_info[app_name] = info
        self._built = False          # invalidate on new data

    def build_index(self) -> None:
        """Build TF-IDF matrix over all reviews from all apps."""
        self._chunks = []
        self._chunk_meta = []
        for app_name, reviews in self.reviews_by_app.items():
            for r in reviews:
                text = r.get("text", "").strip()
                if not text:
                    continue
                self._chunks.append(text)
                self._chunk_meta.append(
                    {
                        "app": app_name,
                        "rating": r.get("rating"),
                        "date": r.get("date", "")[:10],
                        "author": r.get("author", ""),
                    }
                )
        if self._chunks:
            self._matrix = self.vectorizer.fit_transform(self._chunks)
        self._built = True

    # ──────────────────────────────────────────
    # Retrieval
    # ──────────────────────────────────────────

    def retrieve(self, query: str, top_k: int = 25) -> List[Dict[str, Any]]:
        """Return top-k most relevant review chunks for a query."""
        if not self._built:
            self.build_index()
        if self._matrix is None or self._matrix.shape[0] == 0:
            return []
        q_vec = self.vectorizer.transform([query])
        sims = cosine_similarity(q_vec, self._matrix).flatten()
        top_idx = np.argsort(sims)[::-1][:top_k]
        results = []
        for idx in top_idx:
            if sims[idx] > 0.01:
                results.append(
                    {
                        "text": self._chunks[idx],
                        "meta": self._chunk_meta[idx],
                        "score": float(sims[idx]),
                    }
                )
        return results

    def retrieve_per_app(self, query: str, top_k_per_app: int = 8) -> Dict[str, List[Dict]]:
        """Return top-k chunks per app for balanced comparison."""
        if not self._built:
            self.build_index()
        if self._matrix is None:
            return {}
        q_vec = self.vectorizer.transform([query])
        sims = cosine_similarity(q_vec, self._matrix).flatten()
        # Group by app
        app_hits: Dict[str, List[tuple]] = {a: [] for a in self.reviews_by_app}
        for idx, score in enumerate(sims):
            app = self._chunk_meta[idx]["app"]
            app_hits[app].append((score, idx))
        result = {}
        for app, hits in app_hits.items():
            hits.sort(key=lambda x: x[0], reverse=True)
            result[app] = [
                {"text": self._chunks[i], "meta": self._chunk_meta[i], "score": float(s)}
                for s, i in hits[:top_k_per_app]
                if s > 0.01
            ]
        return result

    # ──────────────────────────────────────────
    # Generation
    # ──────────────────────────────────────────

    def query(self, question: str, llm_client) -> str:
        """Answer a free-form question using retrieved reviews + Gemini."""
        per_app = self.retrieve_per_app(question, top_k_per_app=10)
        apps = list(self.reviews_by_app.keys())

        context_parts = []
        for app, hits in per_app.items():
            if not hits:
                continue
            context_parts.append(f"\n--- {app} reviews (most relevant) ---")
            for h in hits:
                stars = f"{h['meta']['rating']}★" if h['meta']['rating'] else "?★"
                context_parts.append(f"  [{h['meta']['date']} | {stars}] {h['text']}")

        context = "\n".join(context_parts) if context_parts else "No relevant reviews found."

        prompt = f"""You are an expert mobile app competitive intelligence analyst.
You are comparing these Google Play Store apps: {', '.join(apps)}.
You have retrieved the most relevant user reviews for answering the question below.

RELEVANT REVIEWS:
{context}

QUESTION: {question}

Provide a detailed, structured comparison between the apps. 
- Use specific quotes from reviews where possible.
- Highlight clear winners and losers on this specific topic.
- Be direct and actionable.
- Use markdown formatting with headers and bullet points."""

        return llm_client.complete(
            "You are an expert mobile app competitive intelligence analyst. Be specific, use evidence from reviews, and give clear comparative insights.",
            prompt,
        )

    def generate_auto_insights(self, llm_client) -> str:
        """Generate unsolicited top-5 competitive insights across all apps."""
        apps = list(self.reviews_by_app.keys())
        if not apps:
            return ""

        # Build a representative sample for each app
        sample_parts = []
        for app, reviews in self.reviews_by_app.items():
            info = self.app_info.get(app, {})
            sample = reviews[:40]
            texts = [f"  [{r.get('rating', '?')}★] {r.get('text', '')[:200]}" for r in sample]
            sample_parts.append(
                f"=== {app} (avg rating: {info.get('avg_rating', 'N/A')}, "
                f"{len(reviews)} reviews in 90 days) ===\n" + "\n".join(texts)
            )

        all_samples = "\n\n".join(sample_parts)

        prompt = f"""You are an expert mobile app competitive analyst reviewing Google Play Store reviews for the past 3 months.

Apps being compared: {', '.join(apps)}

USER REVIEWS SAMPLE:
{all_samples}

Generate a structured competitive intelligence report with these exact sections:

## 🏆 Competitive Rankings
Rank the apps from best to worst with a brief justification.

## 📊 Key Sentiment Comparison
Compare user sentiment per app with specific themes.

## 💡 Top Opportunities (for weaker apps)
3-5 specific product improvements the lower-ranked apps could make.

## ⚠️ Critical Pain Points
The most commonly mentioned problems per app.

## 🎯 Summary
One-paragraph executive summary for a product manager.

Be specific, cite user language, and make it actionable."""

        return llm_client.complete(
            "You are a world-class mobile app analyst. Be specific, data-driven, and cite user language from reviews.",
            prompt,
        )

    # ──────────────────────────────────────────
    # Utilities
    # ──────────────────────────────────────────

    def get_summary_stats(self) -> Dict[str, Any]:
        """Return summary statistics for all indexed apps."""
        stats = {}
        for app, reviews in self.reviews_by_app.items():
            ratings = [r["rating"] for r in reviews if r.get("rating") is not None]
            stats[app] = {
                "total_reviews": len(reviews),
                "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
                "rating_dist": {
                    str(i): sum(1 for r in ratings if r == i) for i in range(1, 6)
                },
            }
        return stats
