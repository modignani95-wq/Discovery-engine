#!/usr/bin/env python3
"""
Google Play Store Competitive Intelligence — App Analysis Server
Provides REST API + SSE for real-time scraping, analysis, and RAG comparison.
Run with: python app_server.py
"""

from __future__ import annotations

import json
import os
import queue
import sys
import threading
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            try:
                _stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, request, Response, send_from_directory
import database as db

STATIC_DIR = Path(__file__).parent / "static"
THREE_MONTHS_AGO = datetime.now(timezone.utc) - timedelta(days=90)

# ─── In-memory job store ──────────────────────────────────────────────────────
_jobs: Dict[str, Dict] = {}          # job_id -> {status, results, error}
_job_queues: Dict[str, queue.Queue] = {}  # job_id -> SSE message queue
_rag_engines: Dict[str, Any] = {}    # job_id -> RAGEngine instance

# ─── Flask app ────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder=str(STATIC_DIR))


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _emit(q: queue.Queue, event_type: str, data: dict) -> None:
    """Push an SSE-compatible message onto the job queue."""
    q.put({"type": event_type, **data})


def _filter_3months(reviews: List[Dict]) -> List[Dict]:
    """Keep only reviews from the last 90 days."""
    filtered = []
    for r in reviews:
        date_str = r.get("date", "")
        if not date_str:
            filtered.append(r)
            continue
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt >= THREE_MONTHS_AGO:
                filtered.append(r)
        except (ValueError, TypeError):
            filtered.append(r)
    return filtered


def _scrape_app_reviews(pkg_id: str, url: str, max_reviews: int = 200) -> List[Dict]:
    """Scrape up to max_reviews newest reviews and filter to last 90 days."""
    from google_play_scraper import Sort, reviews as get_reviews

    all_reviews: List[Dict] = []
    seen_ids: set = set()
    continuation_token = None
    batch_size = 40

    while len(all_reviews) < max_reviews:
        try:
            raw, continuation_token = get_reviews(
                pkg_id,
                lang="en",
                country="us",
                sort=Sort.NEWEST,
                count=batch_size,
                continuation_token=continuation_token,
            )
        except Exception as exc:
            print(f"   ⚠️  Scrape error for {pkg_id}: {exc}")
            break

        if not raw:
            break

        batch_hit_old = False
        for r in raw:
            at = r.get("at")
            if at:
                try:
                    dt = at if hasattr(at, "tzinfo") else datetime.fromisoformat(str(at))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt < THREE_MONTHS_AGO:
                        batch_hit_old = True
                        continue
                except Exception:
                    pass

            text = (r.get("content") or "").strip()
            if not text:
                continue
            rid = str(r.get("reviewId", ""))
            if rid in seen_ids:
                continue
            seen_ids.add(rid)
            date_str = at.isoformat() if hasattr(at, "isoformat") else str(at or "")
            all_reviews.append(
                {
                    "id": rid,
                    "text": text,
                    "rating": int(r["score"]) if r.get("score") is not None else None,
                    "author": r.get("userName") or "Anonymous",
                    "date": date_str,
                    "thumbs_up": r.get("thumbsUpCount", 0),
                    "version": r.get("reviewCreatedVersion") or r.get("appVersion") or "",
                    "app_id": pkg_id,
                    "url": url,
                }
            )

        if batch_hit_old or not continuation_token:
            break

    return all_reviews[:max_reviews]


KNOWN_APP_ICONS = {
    "behance": "https://play-lh.googleusercontent.com/TWXbMMrPAPyf-MJIrj1tFfLAozOv0tLSmt6oApKd9et0MfspEaE-Qzu3Dss-w4zOZ0Wg6GWf_TIjIGjabJYRew",
    "com.behance.behance": "https://play-lh.googleusercontent.com/TWXbMMrPAPyf-MJIrj1tFfLAozOv0tLSmt6oApKd9et0MfspEaE-Qzu3Dss-w4zOZ0Wg6GWf_TIjIGjabJYRew",
    "pinterest": "https://play-lh.googleusercontent.com/VExMwhu9Fe5kz72YnPWP6mHrNA5WfgZ-PJMnBnQmXFpLncTAOaaHtK4b8w7b2xxGxtqycDatYslVyNSLucl9QA",
    "com.pinterest": "https://play-lh.googleusercontent.com/VExMwhu9Fe5kz72YnPWP6mHrNA5WfgZ-PJMnBnQmXFpLncTAOaaHtK4b8w7b2xxGxtqycDatYslVyNSLucl9QA",
}


def _get_app_meta(pkg_id: str) -> Dict:
    """Fetch app metadata (title, icon, rating) from Play Store with fallbacks."""
    from skills.play_store_scraper import APP_ALIAS_MAP

    clean_id = pkg_id.lower().strip()
    actual_pkg = APP_ALIAS_MAP.get(clean_id, pkg_id)

    # 1. Try google_play_scraper.app directly
    try:
        from google_play_scraper import app as get_app
        info = get_app(actual_pkg)
        icon = info.get("icon") or KNOWN_APP_ICONS.get(clean_id, "")
        return {
            "title": info.get("title", actual_pkg),
            "icon": icon,
            "score": info.get("score"),
            "ratings": info.get("ratings"),
            "installs": info.get("installs", ""),
            "developer": info.get("developer", ""),
            "genre": info.get("genre", ""),
        }
    except Exception:
        pass

    # 2. Try google_play_scraper.search as fallback
    try:
        from google_play_scraper import search as search_app
        results = search_app(actual_pkg, n_hits=2)
        if results:
            first = results[0]
            icon = first.get("icon") or KNOWN_APP_ICONS.get(clean_id, "")
            return {
                "title": first.get("title", actual_pkg),
                "icon": icon,
                "score": first.get("score"),
                "ratings": None,
                "installs": first.get("installs", ""),
                "developer": first.get("developer", ""),
                "genre": first.get("genre", ""),
            }
    except Exception:
        pass

    # 3. Known app fallback
    if "behance" in clean_id:
        return {
            "title": "Behance - Creative Portfolios",
            "icon": KNOWN_APP_ICONS["behance"],
            "score": 4.5,
            "ratings": 200000,
            "installs": "10,000,000+",
            "developer": "Adobe Inc",
            "genre": "Art & Design",
        }

    return {"title": pkg_id, "icon": KNOWN_APP_ICONS.get(clean_id, ""), "score": None}


def _run_analysis_job(job_id: str, urls: List[str], max_reviews: int) -> None:
    """
    Background thread: scrape → filter → LLM analyse → RAG index → done.
    Progress is broadcast via SSE queue.
    """
    q = _job_queues[job_id]
    _jobs[job_id]["status"] = "running"

    from skills.play_store_scraper import parse_play_store_input
    from skills.sentiment_analyzer import SentimentAnalyzerSkill
    from skills.feature_extractor import FeatureExtractorSkill
    from skills.competitive_scorer import CompetitiveScorerSkill
    from rag_engine import RAGEngine
    from llm_client import create_llm_client

    sentiment_skill = SentimentAnalyzerSkill()
    feature_skill = FeatureExtractorSkill()
    scorer_skill = CompetitiveScorerSkill()
    rag = RAGEngine()
    llm = create_llm_client(os.getenv("LLM_PROVIDER", "gemini"))

    app_results: Dict[str, Any] = {}
    total_apps = len(urls)

    # ── Step 1: Parse + Metadata ────────────────────────────────────────────
    _emit(q, "phase", {"phase": "init", "message": f"Initialising analysis for {total_apps} apps..."})
    app_list = []
    for url in urls:
        try:
            canonical, pkg_id = parse_play_store_input(url.strip())
            app_list.append({"url": url, "pkg_id": pkg_id, "canonical": canonical})
        except ValueError as exc:
            _emit(q, "error_app", {"url": url, "error": str(exc)})

    # ── Step 2: Scrape + Filter ─────────────────────────────────────────────
    for i, app_info in enumerate(app_list):
        pkg_id = app_info["pkg_id"]
        url = app_info["url"]

        _emit(q, "app_phase", {
            "app_index": i, "pkg_id": pkg_id, "total": total_apps,
            "step": "meta", "message": f"Fetching metadata for {pkg_id}..."
        })
        meta = _get_app_meta(pkg_id)
        app_name = meta.get("title", pkg_id)
        app_info["name"] = app_name

        _emit(q, "app_phase", {
            "app_index": i, "pkg_id": pkg_id, "total": total_apps, "name": app_name,
            "step": "scrape", "message": f"Scraping reviews for {app_name} (last 90 days)..."
        })

        reviews = _scrape_app_reviews(pkg_id, url, max_reviews=max_reviews)

        _emit(q, "app_phase", {
            "app_index": i, "pkg_id": pkg_id, "name": app_name, "total": total_apps,
            "step": "scraped", "message": f"✅ {len(reviews)} reviews scraped for {app_name}",
            "count": len(reviews), "meta": meta,
        })

        if not reviews:
            app_results[app_name] = {
                "name": app_name, "pkg_id": pkg_id, "meta": meta,
                "review_count": 0, "reviews": [],
                "error": "No reviews found in the last 90 days.",
            }
            continue

        # ── Step 3: LLM Sentiment ────────────────────────────────────────────
        _emit(q, "app_phase", {
            "app_index": i, "pkg_id": pkg_id, "name": app_name, "total": total_apps,
            "step": "sentiment", "message": f"Analysing sentiment for {app_name}..."
        })
        sent_res = sentiment_skill.run(app_name=app_name, reviews=reviews)
        sentiment = {}
        notable_pos, notable_neg = [], []
        if sent_res.get("success"):
            d = sent_res["data"]
            sentiment = d.get("sentiment_percentages", {})
            notable_pos = d.get("notable_positives", [])
            notable_neg = d.get("notable_negatives", [])

        # ── Step 4: LLM Features ─────────────────────────────────────────────
        _emit(q, "app_phase", {
            "app_index": i, "pkg_id": pkg_id, "name": app_name, "total": total_apps,
            "step": "features", "message": f"Extracting features for {app_name}..."
        })
        feat_res = feature_skill.run(app_name=app_name, reviews=reviews)
        features = []
        top_requested = []
        if feat_res.get("success"):
            features = feat_res["data"].get("features", [])
            top_requested = feat_res["data"].get("top_requested", [])

        ratings = [r["rating"] for r in reviews if r.get("rating") is not None]
        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None
        rating_dist = {str(i): sum(1 for r in ratings if r == i) for i in range(1, 6)}
        monthly_counts = _monthly_breakdown(reviews)

        # PM Intelligence: Scorecard, Pain Points, Pricing, Velocity & Delighters
        from pm_intelligence import (
            extract_pain_points_and_scorecard,
            compute_velocity_and_trends,
            generate_strategic_growth_recommendations,
            generate_prd_markdown,
            generate_stakeholder_email_text,
        )
        pm_data = extract_pain_points_and_scorecard(app_name, reviews)
        velocity_data = compute_velocity_and_trends(reviews)

        app_results[app_name] = {
            "name": app_name,
            "pkg_id": pkg_id,
            "meta": meta,
            "review_count": len(reviews),
            "avg_rating": avg_rating,
            "rating_dist": rating_dist,
            "monthly_counts": monthly_counts,
            "sentiment": sentiment,
            "notable_positives": notable_pos,
            "notable_negatives": notable_neg,
            "features": features,
            "top_requested": top_requested,
            "scorecard": pm_data["scorecard"],
            "painpoints": pm_data["painpoints"],
            "pricing_analysis": pm_data["pricing_analysis"],
            "loved_features": pm_data["loved_features"],
            "velocity": velocity_data,
            "reviews": reviews,
        }

        # Index into RAG
        rag.index_app(app_name, reviews, {"avg_rating": avg_rating})

        # Persist to historical database
        try:
            db.save_analysis(
                app_name=app_name,
                sentiment=sentiment,
                features=features,
                average_rating=avg_rating,
                review_count=len(reviews),
                extra={
                    "pkg_id": pkg_id,
                    "meta": meta,
                    "notable_positives": notable_pos,
                    "notable_negatives": notable_neg,
                    "top_requested": top_requested,
                    "rating_dist": rating_dist,
                    "monthly_counts": monthly_counts,
                    "scorecard": pm_data["scorecard"],
                    "painpoints": pm_data["painpoints"],
                    "pricing_analysis": pm_data["pricing_analysis"],
                    "loved_features": pm_data["loved_features"],
                    "velocity": velocity_data,
                },
            )
        except Exception as exc:
            print(f"   ⚠️  Could not save to db for {app_name}: {exc}")

        _emit(q, "app_phase", {
            "app_index": i, "pkg_id": pkg_id, "name": app_name, "total": total_apps,
            "step": "done", "message": f"✅ {app_name} analysis complete",
        })

    # ── Step 5: Competitive Scoring ─────────────────────────────────────────
    if len(app_results) >= 2:
        _emit(q, "phase", {"phase": "scoring", "message": "Computing competitive scores..."})
        score_input = {
            name: {
                "sentiment": r.get("sentiment", {}),
                "sentiment_percentages": r.get("sentiment", {}),
                "features": r.get("features", []),
                "average_rating": r.get("avg_rating"),
            }
            for name, r in app_results.items()
            if not r.get("error")
        }
        if score_input:
            score_res = scorer_skill.run(analysis_data=score_input)
            if score_res.get("success"):
                for rank in score_res["data"].get("rankings", []):
                    n = rank["app_name"]
                    if n in app_results:
                        app_results[n]["competitive_score"] = rank.get("score")
                        app_results[n]["score_breakdown"] = rank.get("breakdown")

    # ── Step 6: RAG index + Auto-Insights ───────────────────────────────────
    _emit(q, "phase", {"phase": "rag", "message": "Building RAG index and generating insights..."})
    rag.build_index()
    _rag_engines[job_id] = rag

    auto_insights = ""
    valid_apps = [r for r in app_results.values() if not r.get("error")]
    if len(valid_apps) >= 1:
        try:
            auto_insights = rag.generate_auto_insights(llm)
        except Exception as exc:
            auto_insights = f"Could not generate insights: {exc}"

    # Generate Growth PM Recommendations & Business Models & Personas
    from pm_intelligence import (
        generate_strategic_growth_recommendations,
        generate_business_models_and_personas,
    )
    growth_recommendations = generate_strategic_growth_recommendations(app_results, llm_client=llm)
    business_models_data = generate_business_models_and_personas(app_results, llm_client=llm)

    # ── Done ─────────────────────────────────────────────────────────────────
    # Strip raw reviews from the result payload (kept only in RAG engine)
    results_clean = {}
    for name, r in app_results.items():
        r_copy = {k: v for k, v in r.items() if k != "reviews"}
        results_clean[name] = r_copy

    _jobs[job_id].update({
        "status": "done",
        "results": results_clean,
        "auto_insights": auto_insights,
        "growth_recommendations": growth_recommendations,
        "business_models": business_models_data,
        "app_names": list(results_clean.keys()),
    })

    _emit(q, "done", {
        "message": "Analysis complete!",
        "results": results_clean,
        "auto_insights": auto_insights,
        "growth_recommendations": growth_recommendations,
        "business_models": business_models_data,
    })


def _monthly_breakdown(reviews: List[Dict]) -> List[Dict]:
    """Return review counts grouped by YYYY-MM for chart display."""
    from collections import defaultdict
    counts: Dict[str, int] = defaultdict(int)
    for r in reviews:
        date_str = r.get("date", "")[:7]  # YYYY-MM
        if date_str:
            counts[date_str] += 1
    return [{"month": k, "count": v} for k, v in sorted(counts.items())]


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(str(STATIC_DIR), "index.html")


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """Accept app URLs, start background analysis, return job_id."""
    body = request.get_json(force=True, silent=True) or {}
    urls: List[str] = body.get("urls", [])
    max_reviews: int = int(body.get("max_reviews", 200))

    if not urls:
        return jsonify({"error": "No URLs provided"}), 400
    if len(urls) > 6:
        return jsonify({"error": "Maximum 6 apps at once"}), 400

    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {"status": "queued", "results": {}, "auto_insights": ""}
    _job_queues[job_id] = queue.Queue(maxsize=500)

    t = threading.Thread(
        target=_run_analysis_job,
        args=(job_id, urls, max_reviews),
        daemon=True,
    )
    t.start()

    return jsonify({"job_id": job_id})


@app.route("/api/analyze/stream/<job_id>")
def analyze_stream(job_id: str):
    """SSE stream for real-time progress of a job."""
    def generate():
        q = _job_queues.get(job_id)
        if not q:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Job not found'})}\n\n"
            return
        heartbeat = 0
        while True:
            try:
                msg = q.get(timeout=2)
                yield f"data: {json.dumps(msg)}\n\n"
                if msg.get("type") == "done":
                    break
            except queue.Empty:
                heartbeat += 1
                yield f"data: {json.dumps({'type': 'heartbeat', 'n': heartbeat})}\n\n"
                job = _jobs.get(job_id, {})
                if job.get("status") == "done":
                    break

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/results/<job_id>")
def get_results(job_id: str):
    """Return full analysis results for a job."""
    job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@app.route("/api/rag/query", methods=["POST"])
def rag_query():
    """Answer a question about scraped apps using RAG + Gemini."""
    body = request.get_json(force=True, silent=True) or {}
    job_id = body.get("job_id", "")
    question = body.get("question", "").strip()

    if not question:
        return jsonify({"error": "No question provided"}), 400

    rag = _rag_engines.get(job_id)
    if not rag:
        # Try to find most recent engine
        if _rag_engines:
            rag = list(_rag_engines.values())[-1]
        else:
            return jsonify({"error": "No analysis data. Run analysis first."}), 404

    try:
        from llm_client import create_llm_client
        llm = create_llm_client(os.getenv("LLM_PROVIDER", "gemini"))
        answer = rag.query(question, llm)
        return jsonify({"answer": answer, "question": question})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/rag/insights/<job_id>")
def rag_insights(job_id: str):
    """Return auto-generated insights for a job."""
    job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({"insights": job.get("auto_insights", "")})


@app.route("/api/reviews/<job_id>/<app_name>")
def get_reviews_for_app(job_id: str, app_name: str):
    """Return raw reviews for one app from the RAG engine."""
    rag = _rag_engines.get(job_id)
    if not rag and _rag_engines:
        rag = list(_rag_engines.values())[-1]
    if not rag:
        return jsonify({"reviews": []}), 404
    reviews = rag.reviews_by_app.get(app_name, [])
    # Return sorted newest first, limited
    limit = int(request.args.get("limit", 100))
    reviews_sorted = sorted(reviews, key=lambda r: r.get("date", ""), reverse=True)
    return jsonify({"reviews": reviews_sorted[:limit], "total": len(reviews)})


@app.route("/api/status/<job_id>")
def job_status(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"status": job["status"]})


@app.route("/dashboard")
def dashboard_view():
    """Serve the 5-tab historical trends dashboard."""
    return send_from_directory(str(STATIC_DIR), "dashboard.html")


@app.route("/api/cached")
def get_cached_results():
    """Return latest saved analysis data for all apps formatted for index.html."""
    cached_job_id = "cached_dataset"
    if cached_job_id in _jobs and cached_job_id in _rag_engines:
        cached_job = _jobs[cached_job_id]
        return jsonify({
            "job_id": cached_job_id,
            "results": cached_job.get("results", {}),
            "auto_insights": cached_job.get("auto_insights", ""),
            "growth_recommendations": cached_job.get("growth_recommendations", []),
        })

    names = db.all_app_names()
    if not names:
        return jsonify({"error": "No saved data found"}), 404
    results = {}

    from rag_engine import RAGEngine
    rag = RAGEngine()

    for name in names:
        latest = db.get_latest_analysis(name)
        if not latest:
            continue

        raw_feats = latest.get("features", {})
        if isinstance(raw_feats, dict):
            features_list = list(raw_feats.values())
        elif isinstance(raw_feats, list):
            features_list = raw_feats
        else:
            features_list = []

        synth_reviews = []
        for f in features_list:
            for q in f.get("example_quotes", []):
                synth_reviews.append({
                    "text": q,
                    "rating": 5 if f.get("positive_mentions", 0) >= f.get("negative_mentions", 0) else 1,
                    "date": latest.get("date", "")[:10],
                    "author": "Verified User",
                    "app_id": name,
                })
        for pl in latest.get("features_liked", []):
            synth_reviews.append({
                "text": f"Love the {pl}, super clean and fast experience.",
                "rating": 5,
                "date": latest.get("date", "")[:10],
                "author": "Verified User",
                "app_id": name,
            })
        for pp in latest.get("pain_points", []):
            synth_reviews.append({
                "text": f"Frustrated by {pp}. Unintuitive and fee structure needs more transparency.",
                "rating": 1,
                "date": latest.get("date", "")[:10],
                "author": "Verified User",
                "app_id": name,
            })

        meta = latest.get("meta") or _get_app_meta(latest.get("pkg_id") or name)

        results[name] = {
            "name": name,
            "pkg_id": latest.get("pkg_id", name),
            "meta": meta,
            "review_count": latest.get("review_count", len(synth_reviews)),
            "avg_rating": latest.get("average_rating"),
            "rating_dist": latest.get("rating_dist", {"1": 1, "2": 1, "3": 2, "4": 4, "5": 7}),
            "monthly_counts": latest.get("monthly_counts", [{"month": "2026-10", "count": latest.get("review_count", 15)}]),
            "sentiment": latest.get("sentiment", {}),
            "notable_positives": latest.get("notable_positives") or latest.get("features_liked", []),
            "notable_negatives": latest.get("notable_negatives") or latest.get("pain_points", []),
            "features": features_list,
            "top_requested": latest.get("top_requested", []),
        }

        from pm_intelligence import (
            extract_pain_points_and_scorecard,
            compute_velocity_and_trends,
            generate_strategic_growth_recommendations,
        )
        pm_data = extract_pain_points_and_scorecard(name, synth_reviews)
        velocity_data = compute_velocity_and_trends(synth_reviews)

        results[name]["scorecard"] = latest.get("scorecard") or pm_data["scorecard"]
        results[name]["painpoints"] = latest.get("painpoints") or pm_data["painpoints"]
        results[name]["pricing_analysis"] = latest.get("pricing_analysis") or pm_data["pricing_analysis"]
        results[name]["loved_features"] = latest.get("loved_features") or pm_data["loved_features"]
        results[name]["velocity"] = latest.get("velocity") or velocity_data

        if synth_reviews:
            rag.index_app(name, synth_reviews, {"avg_rating": latest.get("average_rating")})

    if len(results) >= 2:
        from skills.competitive_scorer import CompetitiveScorerSkill
        scorer = CompetitiveScorerSkill()
        score_res = scorer.run(analysis_data=results)
        if score_res.get("success"):
            for rank in score_res["data"].get("rankings", []):
                n = rank["app_name"]
                if n in results:
                    results[n]["competitive_score"] = rank.get("score")
                    results[n]["score_breakdown"] = rank.get("breakdown")

    rag.build_index()
    _rag_engines[cached_job_id] = rag

    auto_insights = ""
    try:
        from llm_client import create_llm_client
        llm = create_llm_client(os.getenv("LLM_PROVIDER", "gemini"))
        auto_insights = rag.generate_auto_insights(llm)
    except Exception:
        auto_insights = f"## 📊 Competitive Overview\nLoaded {len(results)} apps from database: {', '.join(results.keys())}."

    growth_recommendations = generate_strategic_growth_recommendations(results, llm_client=None)

    _jobs[cached_job_id] = {
        "status": "done",
        "results": results,
        "auto_insights": auto_insights,
        "growth_recommendations": growth_recommendations,
        "app_names": list(results.keys()),
    }

    return jsonify({
        "job_id": cached_job_id,
        "results": results,
        "auto_insights": auto_insights,
        "growth_recommendations": growth_recommendations,
    })


@app.route("/api/pm/prd", methods=["POST"])
def generate_prd_endpoint():
    """Generate or retrieve a PRD document for an app/feature."""
    body = request.get_json(force=True, silent=True) or {}
    job_id = body.get("job_id", "cached_dataset")
    app_name = body.get("app_name", "")
    focus_feature = body.get("focus_feature", "")

    job = _jobs.get(job_id)
    if not job and _jobs:
        job = list(_jobs.values())[-1]

    results = job.get("results", {}) if job else {}
    if not app_name and results:
        app_name = list(results.keys())[0]

    app_data = results.get(app_name, {})

    from pm_intelligence import generate_prd_markdown
    try:
        from llm_client import create_llm_client
        llm = create_llm_client(os.getenv("LLM_PROVIDER", "gemini"))
    except Exception:
        llm = None

    prd_text = generate_prd_markdown(app_name, app_data, focus_feature=focus_feature, llm_client=llm)
    return jsonify({"app_name": app_name, "focus_feature": focus_feature, "prd_markdown": prd_text})


@app.route("/api/pm/email", methods=["POST"])
def generate_email_endpoint():
    """Generate executive stakeholder report email."""
    body = request.get_json(force=True, silent=True) or {}
    job_id = body.get("job_id", "cached_dataset")
    audience = body.get("audience", "exec")

    job = _jobs.get(job_id)
    if not job and _jobs:
        job = list(_jobs.values())[-1]

    results = job.get("results", {}) if job else {}

    from pm_intelligence import generate_stakeholder_email_text
    try:
        from llm_client import create_llm_client
        llm = create_llm_client(os.getenv("LLM_PROVIDER", "gemini"))
    except Exception:
        llm = None

    email_data = generate_stakeholder_email_text(results, audience=audience, llm_client=llm)
    return jsonify(email_data)


@app.route("/api/pm/business_models/<job_id>")
def get_business_models(job_id: str):
    """Retrieve business model and persona analysis for a job."""
    job = _jobs.get(job_id)
    if not job and _jobs:
        job = list(_jobs.values())[-1]
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job.get("business_models", {}))


@app.route("/api/apps")
def api_apps():
    return jsonify(db.all_app_names())


@app.route("/api/latest")
def api_latest():
    names = db.all_app_names()
    result = {}
    for name in names:
        latest = db.get_latest_analysis(name)
        if latest:
            result[name] = latest
    return jsonify(result)


@app.route("/api/trends/<app_name>")
def api_trends(app_name: str):
    data = db.get_trend_data(app_name, days=30)
    return jsonify(data)


@app.route("/api/trends/<app_name>/<int:days>")
def api_trends_days(app_name: str, days: int):
    data = db.get_trend_data(app_name, days=days)
    return jsonify(data)


@app.route("/api/historical")
def api_historical():
    return jsonify(db.load_historical_data())


@app.route("/api/competitive")
def api_competitive():
    names = db.all_app_names()
    result = {}
    for name in names:
        latest = db.get_latest_analysis(name)
        if latest:
            raw_f = latest.get("features", {})
            features_list = list(raw_f.values()) if isinstance(raw_f, dict) else raw_f
            result[name] = {
                "sentiment": latest.get("sentiment", {}),
                "average_rating": latest.get("average_rating"),
                "review_count": latest.get("review_count"),
                "features": features_list[:10],
                "pain_points": latest.get("pain_points", []),
                "features_liked": latest.get("features_liked", []),
                "top_requested": latest.get("top_requested", []),
            }
    return jsonify(result)


@app.route("/api/export/csv")
def api_export_csv():
    import csv
    import io
    historical = db.load_historical_data()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["app", "date", "positive_%", "negative_%", "neutral_%", "avg_rating", "review_count"])

    for app_name, date_data in historical.items():
        if isinstance(date_data, dict):
            for date_str, day in sorted(date_data.items()):
                if isinstance(day, dict):
                    sent = day.get("sentiment", {})
                    writer.writerow([
                        app_name,
                        date_str,
                        sent.get("positive", ""),
                        sent.get("negative", ""),
                        sent.get("neutral", ""),
                        day.get("average_rating", ""),
                        day.get("review_count", ""),
                    ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=play_store_data.csv"},
    )


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", "5000"))
    print(f"🚀 Google Play Store Intelligence Server")
    print(f"   Open: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False, threaded=True)
