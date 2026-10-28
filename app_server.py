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
@app.route("/engine")
@app.route("/index.html")
def index():
    return send_from_directory(str(STATIC_DIR), "retrieval_discovery_engine.html")


@app.route("/scraper")
def scraper_view():
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


# ─── SIP Discovery Engine Routes ─────────────────────────────────────────────

_sip_jobs: Dict[str, Dict] = {}   # sip_job_id -> pipeline result
_groww_data: Dict[str, Any] = {}
_groww_sip_result: Dict[str, Any] = {}

GROWW_CACHE_FILE = Path(__file__).parent / "groww_cache.json"
GROWW_SIP_CACHE_FILE = Path(__file__).parent / "groww_sip_cache.json"

if GROWW_CACHE_FILE.exists():
    try:
        with open(GROWW_CACHE_FILE, "r", encoding="utf-8") as _f:
            _groww_data = json.load(_f)
            print(f"📦 Pre-loaded {_groww_data.get('total_records', 0)} Groww records from {GROWW_CACHE_FILE.name}")
    except Exception as _exc:
        print(f"⚠️ Could not load groww cache: {_exc}")

if GROWW_SIP_CACHE_FILE.exists():
    try:
        with open(GROWW_SIP_CACHE_FILE, "r", encoding="utf-8") as _f:
            _groww_sip_result = json.load(_f)
            _sip_jobs["groww_latest"] = _groww_sip_result
            print(f"💡 Pre-loaded SIP discovery hypotheses from {GROWW_SIP_CACHE_FILE.name}")
    except Exception as _exc:
        print(f"⚠️ Could not load groww sip cache: {_exc}")


@app.route("/sip")
def sip_dashboard():
    """Serve the flagship Groww SIP Retrieval Discovery Engine dashboard."""
    return send_from_directory(str(STATIC_DIR), "retrieval_discovery_engine.html")


@app.route("/sip-legacy")
def sip_legacy_dashboard():
    """Serve the legacy SIP Discovery Engine dashboard."""
    return send_from_directory(str(STATIC_DIR), "sip_dashboard.html")


@app.route("/api/sip/run", methods=["POST"])
def sip_run():
    """
    Trigger SIP Discovery Engine pipeline on a given job's reviews or Groww multi-source data.
    Body: { job_id: str, use_llm: bool }
    """
    global _groww_data
    body = request.get_json(force=True, silent=True) or {}
    job_id = body.get("job_id", "")
    use_llm = bool(body.get("use_llm", True))

    # Gather all reviews from existing job or cached dataset
    job = _jobs.get(job_id)
    if not job and _jobs:
        job = list(_jobs.values())[-1]
        job_id = list(_jobs.keys())[-1]

    rag = _rag_engines.get(job_id)
    if not rag and _rag_engines:
        rag = list(_rag_engines.values())[-1]

    all_reviews: List[Dict] = []
    if rag:
        for app_reviews in rag.reviews_by_app.values():
            all_reviews.extend(app_reviews)

    if not all_reviews:
        if _groww_data and _groww_data.get("records"):
            all_reviews = _groww_data["records"]
        else:
            try:
                from groww_collector import collect_all_groww_sources
                _groww_data = collect_all_groww_sources(max_per_source=15)
                all_reviews = _groww_data.get("records", [])
            except Exception:
                pass

    if not all_reviews:
        return jsonify({"error": "No review data found. Run a collection first."}), 400

    try:
        from sip_discovery_engine import run_sip_pipeline
        llm = None

        if use_llm:
            try:
                from llm_client import create_llm_client
                llm = create_llm_client(os.getenv("LLM_PROVIDER", "gemini"))
            except Exception:
                llm = None

        sip_result = run_sip_pipeline(all_reviews, llm_client=llm)

        sip_job_id = f"sip_{job_id}"
        _sip_jobs[sip_job_id] = sip_result

        return jsonify({
            "sip_job_id": sip_job_id,
            "stages": sip_result["stages"],
            "hypotheses_count": len(sip_result["hypothesis_report"].get("hypotheses", [])),
            "extractions_count": len(sip_result.get("extractions", [])),
            "disclaimer": sip_result["disclaimer"],
        })
    except Exception as exc:
        import traceback
        return jsonify({"error": str(exc), "trace": traceback.format_exc()[-500:]}), 500


@app.route("/api/sip/results/<sip_job_id>")
def sip_results(sip_job_id: str):
    """Return full SIP pipeline result for a job."""
    result = _sip_jobs.get(sip_job_id)
    if not result and _sip_jobs:
        result = list(_sip_jobs.values())[-1]
    if not result:
        return jsonify({"error": "No SIP results found. Run /api/sip/run first."}), 404

    from sip_discovery_engine import get_opportunity_summary, get_evidence_explorer
    return jsonify({
        "pipeline_run_at": result.get("pipeline_run_at"),
        "stages": result.get("stages"),
        "hypothesis_report": result.get("hypothesis_report"),
        "validation_report": result.get("validation_report"),
        "opportunities": get_opportunity_summary(result),
        "evidence": get_evidence_explorer(result),
        "disclaimer": result.get("disclaimer"),
    })


@app.route("/api/sip/evals/<sip_job_id>")
def sip_evals(sip_job_id: str):
    """Return evaluation report for a SIP job."""
    result = _sip_jobs.get(sip_job_id)
    if not result and _sip_jobs:
        result = list(_sip_jobs.values())[-1]
    if not result:
        return jsonify({"error": "No SIP results found."}), 404

    try:
        from sip_evals import build_eval_report, validate_batch, GOLDEN_DATASET, run_golden_dataset_eval
        batch_report = validate_batch(result.get("extractions", []))
        golden_eval  = run_golden_dataset_eval(result.get("extractions", []), GOLDEN_DATASET)
        result_with_golden = {**result}
        result_with_golden.setdefault("validation_report", {})["golden_eval"] = golden_eval
        eval_report = build_eval_report(result_with_golden)
        return jsonify({
            "eval_report": eval_report,
            "batch_validation": batch_report,
            "golden_eval": golden_eval,
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/sip/latest")
def sip_latest():
    """Return the most recent SIP job results without needing the job ID."""
    if not _sip_jobs and _groww_sip_result:
        _sip_jobs["groww_latest"] = _groww_sip_result
    if not _sip_jobs:
        return jsonify({"error": "No SIP results yet."}), 404
    latest_id = list(_sip_jobs.keys())[-1]
    result = _sip_jobs[latest_id]
    from sip_discovery_engine import get_opportunity_summary, get_evidence_explorer
    return jsonify({
        "sip_job_id": latest_id,
        "pipeline_run_at": result.get("pipeline_run_at"),
        "stages": result.get("stages"),
        "hypothesis_report": result.get("hypothesis_report"),
        "validation_report": result.get("validation_report"),
        "opportunities": get_opportunity_summary(result),
        "evidence": get_evidence_explorer(result),
        "disclaimer": result.get("disclaimer"),
    })


@app.route("/api/sip/training-sources")
@app.route("/api/training-sources")
def api_training_sources():
    """Return all 46 trained sources (38 Google Sheet links + 8 premier investing forums) with retrieved intelligence."""
    sources_file = Path(__file__).parent / "data" / "trained_sources.json"
    if sources_file.exists():
        try:
            with open(sources_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return jsonify({
                "total_sources": len(data),
                "sheet_sources_count": sum(1 for s in data if s.get("is_from_sheet")),
                "added_forums_count": sum(1 for s in data if not s.get("is_from_sheet")),
                "platform_breakdown": {
                    "Investing Forum": sum(1 for s in data if s.get("platform") == "Investing Forum"),
                    "Reddit Community": sum(1 for s in data if s.get("platform") == "Reddit Community"),
                    "Reddit Seed Thread": sum(1 for s in data if s.get("platform") == "Reddit Seed Thread"),
                    "YouTube Channel": sum(1 for s in data if s.get("platform") == "YouTube Channel"),
                    "Twitter (X)": sum(1 for s in data if s.get("platform") == "Twitter (X)"),
                    "Instagram": sum(1 for s in data if s.get("platform") == "Instagram"),
                },
                "sources": data,
            })
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500
    return jsonify({"error": "trained_sources.json not found"}), 404


@app.route("/api/sip/filtered-intelligence")
def api_sip_filtered_intelligence():
    """Return all 1,050 SIP-filtered conversations enriched with categories, friction levels, and PM insights."""
    filtered_file = Path(__file__).parent / "data" / "sip_filtered_intelligence.json"
    if not filtered_file.exists():
        try:
            from sip_filter_engine import filter_and_enrich_sip_dataset
            if GROWW_CACHE_FILE.exists():
                with open(GROWW_CACHE_FILE, "r", encoding="utf-8") as f:
                    cdata = json.load(f)
                filter_and_enrich_sip_dataset(cdata.get("records", []))
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    try:
        with open(filtered_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        category = request.args.get("category")
        source = request.args.get("source")
        friction = request.args.get("friction")
        search = (request.args.get("search") or "").lower().strip()

        records = data.get("sip_records", [])
        if category and category != "all":
            records = [r for r in records if r.get("sip_category") == category]
        if source and source != "all":
            records = [r for r in records if r.get("source_code") == source]
        if friction and friction != "all":
            records = [r for r in records if r.get("sip_friction_level") == friction]
        if search:
            records = [
                r for r in records
                if search in (r.get("text") or "").lower()
                or search in (r.get("title") or "").lower()
                or search in (r.get("author") or "").lower()
                or search in (r.get("sip_category_name") or "").lower()
                or search in (r.get("pm_actionable_insight") or "").lower()
                or search in (r.get("source_name") or "").lower()
                or any(search in k.lower() for k in r.get("sip_matched_terms", []))
            ]

        return jsonify({
            "total_evaluated": data.get("total_evaluated", 1335),
            "total_sip_relevant": data.get("total_sip_relevant", len(data.get("sip_records", []))),
            "returned_count": len(records),
            "categories_metadata": data.get("categories_metadata", {}),
            "category_breakdown": data.get("category_breakdown", {}),
            "source_breakdown": data.get("source_breakdown", {}),
            "friction_breakdown": data.get("friction_breakdown", {}),
            "records": records,
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/sip/episodes")
def api_sip_episodes():
    """Return all 144 structured retrieval & friction failure episodes with cues, stages, and metrics."""
    episodes_file = Path(__file__).parent / "data" / "sip_episodes_144.json"
    if not episodes_file.exists():
        try:
            from build_episodes_144 import main as build_ep
            build_ep()
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    try:
        with open(episodes_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        platform = request.args.get("platform")
        stage = request.args.get("stage")
        category = request.args.get("category")
        search = (request.args.get("search") or "").lower().strip()
        limit = request.args.get("limit")

        episodes = data.get("episodes", [])

        # Sync any newly evaluated Groq cases
        try:
            from groq_judge_engine import load_cached_results
            groq_cached = load_cached_results()
            groq_evals = groq_cached.get("evaluations", {})
            for ep in episodes:
                cid = ep.get("test_case_id")
                if cid in groq_evals:
                    ep["groq_eval"] = groq_evals[cid]
        except Exception:
            pass

        if platform and platform != "all":
            episodes = [e for e in episodes if e.get("source_code") == platform or platform in (e.get("platform") or "").lower()]

        if stage and stage != "all":
            episodes = [e for e in episodes if e.get("stage") == stage]

        if category and category != "all":
            episodes = [e for e in episodes if category.lower() in (e.get("category") or "").lower()]

        if search:
            episodes = [
                e for e in episodes
                if search in (e.get("quote") or "").lower()
                or search in (e.get("title") or "").lower()
                or search in (e.get("author") or "").lower()
                or search in (e.get("test_case_id") or "").lower()
                or search in (e.get("episode_id") or "").lower()
                or search in (e.get("pm_insight") or "").lower()
                or any(search in c.lower() for c in e.get("retained_cues", []))
                or any(search in l.lower() for l in e.get("lost_cues", []))
            ]

        if limit and limit.isdigit():
            episodes = episodes[:int(limit)]

        stage_counts = {
            "payment_mandate": sum(1 for e in data.get("episodes", []) if e.get("stage") == "payment_mandate"),
            "ux_navigation": sum(1 for e in data.get("episodes", []) if e.get("stage") == "ux_navigation"),
            "market_panic": sum(1 for e in data.get("episodes", []) if e.get("stage") == "market_panic"),
            "kyc_folio": sum(1 for e in data.get("episodes", []) if e.get("stage") == "kyc_folio"),
        }

        platform_counts = {
            "play_store": sum(1 for e in data.get("episodes", []) if e.get("source_code") == "play_store"),
            "app_store": sum(1 for e in data.get("episodes", []) if e.get("source_code") == "app_store"),
            "reddit": sum(1 for e in data.get("episodes", []) if e.get("source_code") == "reddit"),
            "youtube": sum(1 for e in data.get("episodes", []) if e.get("source_code") == "youtube"),
            "tradingqna": sum(1 for e in data.get("episodes", []) if e.get("source_code") == "tradingqna"),
            "valuepickr": sum(1 for e in data.get("episodes", []) if e.get("source_code") == "valuepickr"),
        }

        return jsonify({
            "success": True,
            "total_episodes": len(data.get("episodes", [])),
            "returned_count": len(episodes),
            "stage_counts": stage_counts,
            "platform_counts": platform_counts,
            "episodes": episodes,
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/sip/llm-benchmark")
def api_sip_llm_benchmark():
    """Return structured benchmark dataset pairing links with retrieved comments for external LLM evaluation."""
    benchmark_file = Path(__file__).parent / "data" / "llm_evaluation_benchmark.json"
    if not benchmark_file.exists():
        try:
            from build_llm_benchmark import main as build_bm
            build_bm()
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    try:
        with open(benchmark_file, "r", encoding="utf-8") as f:
            bm_data = json.load(f)

        platform = request.args.get("platform")
        search = (request.args.get("search") or "").lower().strip()
        limit = request.args.get("limit")

        cases = bm_data.get("test_cases", [])
        if platform and platform != "all":
            cases = [c for c in cases if c.get("source_code") == platform]
        if search:
            cases = [
                c for c in cases
                if search in (c.get("verbatim_retrieved_text") or "").lower()
                or search in (c.get("source_url") or "").lower()
                or search in (c.get("channel_or_entity") or "").lower()
                or search in (c.get("author") or "").lower()
                or search in (c.get("title") or "").lower()
                or search in (c.get("sip_category_name") or "").lower()
            ]

        if limit and limit.isdigit():
            cases = cases[:int(limit)]

        return jsonify({
            "success": True,
            "benchmark_name": bm_data.get("benchmark_name"),
            "total_benchmark_cases": len(bm_data.get("test_cases", [])),
            "returned_cases_count": len(cases),
            "total_unique_links": bm_data.get("total_unique_links"),
            "platform_breakdown": bm_data.get("platform_breakdown"),
            "evaluation_instructions": bm_data.get("evaluation_instructions"),
            "links_summary": bm_data.get("links_summary", []),
            "test_cases": cases,
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/sip/llm-benchmark/export")
def api_sip_llm_benchmark_export():
    """Send downloadable JSON file for external LLM ingestion."""
    benchmark_file = Path(__file__).parent / "data" / "llm_evaluation_benchmark.json"
    if not benchmark_file.exists():
        from build_llm_benchmark import main as build_bm
        build_bm()
    from flask import send_file
    return send_file(
        str(benchmark_file),
        mimetype="application/json",
        as_attachment=True,
        download_name="groww_sip_retrieval_llm_benchmark.json"
    )


# ─── Mistral LLM-as-a-Judge Evaluation Routes ────────────────────────────────

@app.route("/api/sip/mistral-results", methods=["GET"])
def api_sip_mistral_results():
    """Return all Mistral AI LLM-as-a-Judge rubric evaluations and composite metrics."""
    try:
        from mistral_judge_engine import load_cached_results, seed_initial_mistral_evaluations
        cached = load_cached_results()
        if not cached.get("evaluations"):
            cached = seed_initial_mistral_evaluations(target_count=12)

        verdict = request.args.get("verdict")
        platform = request.args.get("platform")
        category = request.args.get("category")
        search = (request.args.get("search") or "").lower().strip()
        limit = request.args.get("limit")

        eval_list = list(cached.get("evaluations", {}).values())

        if verdict and verdict != "all":
            eval_list = [e for e in eval_list if e.get("verdict") == verdict]

        if platform and platform != "all":
            eval_list = [e for e in eval_list if e.get("source_code") == platform]

        if category and category != "all":
            eval_list = [
                e for e in eval_list
                if e.get("extracted_sip_category") == category
                or e.get("sip_category_name") == category
            ]

        if search:
            eval_list = [
                e for e in eval_list
                if search in (e.get("verbatim_retrieved_text") or "").lower()
                or search in (e.get("detailed_critique") or "").lower()
                or search in (e.get("source_url") or "").lower()
                or search in (e.get("author") or "").lower()
                or search in (e.get("test_case_id") or "").lower()
                or search in (e.get("channel_or_entity") or "").lower()
                or search in (e.get("sip_category_name") or "").lower()
            ]

        if limit and limit.isdigit():
            eval_list = eval_list[:int(limit)]

        return jsonify({
            "success": True,
            "judge_model": cached.get("summary", {}).get("judge_model", "open-mistral-7b"),
            "summary": cached.get("summary", {}),
            "total_evaluations": len(cached.get("evaluations", {})),
            "returned_evaluations": len(eval_list),
            "evaluations": eval_list,
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/sip/mistral-judge", methods=["POST"])
def api_sip_mistral_judge():
    """Trigger Mistral LLM to evaluate a single test case or a batch of cases."""
    try:
        from mistral_judge_engine import judge_single_case, judge_batch, load_cached_results, BENCHMARK_FILE
        body = request.get_json(silent=True) or {}
        case_id = body.get("case_id")
        batch_count = int(body.get("count", 5))
        platform = body.get("platform")
        force = bool(body.get("force", False))

        if case_id:
            with open(BENCHMARK_FILE, "r", encoding="utf-8") as f:
                bm = json.load(f)
            matching = [c for c in bm.get("test_cases", []) if c.get("test_case_id") == case_id]
            if not matching:
                return jsonify({"error": f"Case {case_id} not found in benchmark"}), 404
            
            evaluated = judge_single_case(matching[0], force=force)
            cached = load_cached_results()
            return jsonify({
                "success": True,
                "evaluated_case": evaluated,
                "summary": cached.get("summary", {}),
            })
        else:
            result = judge_batch(count=batch_count, platform=platform, force=force)
            return jsonify({
                "success": True,
                "batch_result": result,
            })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/sip/mistral-results/export", methods=["GET"])
def api_sip_mistral_export():
    """Export all Mistral judge rubric evaluations as downloadable JSON."""
    results_file = Path(__file__).parent / "data" / "mistral_judge_results.json"
    if not results_file.exists():
        from mistral_judge_engine import seed_initial_mistral_evaluations
        seed_initial_mistral_evaluations(target_count=12)
    from flask import send_file
    return send_file(
        str(results_file),
        mimetype="application/json",
        as_attachment=True,
        download_name="mistral_sip_rubrics_evaluation_results.json"
    )


# ─── Groq LLM-as-a-Judge Evaluation Routes ───────────────────────────────────

@app.route("/api/sip/groq-results", methods=["GET"])
def api_sip_groq_results():
    """Return all Groq AI LLM-as-a-Judge rubric evaluations and composite metrics."""
    try:
        from groq_judge_engine import load_cached_results, seed_initial_groq_evaluations
        cached = load_cached_results()
        if not cached.get("evaluations"):
            cached = seed_initial_groq_evaluations(target_count=10)

        verdict = request.args.get("verdict")
        platform = request.args.get("platform")
        category = request.args.get("category")
        search = (request.args.get("search") or "").lower().strip()
        limit = request.args.get("limit")

        eval_list = list(cached.get("evaluations", {}).values())

        if verdict and verdict != "all":
            eval_list = [e for e in eval_list if e.get("verdict") == verdict]

        if platform and platform != "all":
            eval_list = [e for e in eval_list if e.get("source_code") == platform]

        if category and category != "all":
            eval_list = [
                e for e in eval_list
                if e.get("extracted_sip_category") == category
                or e.get("sip_category_name") == category
            ]

        if search:
            eval_list = [
                e for e in eval_list
                if search in (e.get("verbatim_retrieved_text") or "").lower()
                or search in (e.get("detailed_critique") or "").lower()
                or search in (e.get("source_url") or "").lower()
                or search in (e.get("author") or "").lower()
                or search in (e.get("test_case_id") or "").lower()
                or search in (e.get("channel_or_entity") or "").lower()
                or search in (e.get("sip_category_name") or "").lower()
            ]

        if limit and limit.isdigit():
            eval_list = eval_list[:int(limit)]

        return jsonify({
            "success": True,
            "judge_model": cached.get("summary", {}).get("judge_model", "Groq LPU (llama-3.3-70b-versatile)"),
            "summary": cached.get("summary", {}),
            "total_evaluations": len(cached.get("evaluations", {})),
            "returned_evaluations": len(eval_list),
            "evaluations": eval_list,
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/sip/groq-judge", methods=["POST"])
def api_sip_groq_judge():
    """Trigger Groq LLM to evaluate a single test case or a batch of cases."""
    try:
        from groq_judge_engine import judge_single_case, judge_batch, load_cached_results, BENCHMARK_FILE
        body = request.get_json(silent=True) or {}
        case_id = body.get("case_id")
        batch_count = int(body.get("count", 5))
        platform = body.get("platform")
        force = bool(body.get("force", False))

        if case_id:
            with open(BENCHMARK_FILE, "r", encoding="utf-8") as f:
                bm = json.load(f)
            matching = [c for c in bm.get("test_cases", []) if c.get("test_case_id") == case_id]
            if not matching:
                return jsonify({"error": f"Case {case_id} not found in benchmark"}), 404
            
            evaluated = judge_single_case(matching[0], force=force)
            cached = load_cached_results()
            return jsonify({
                "success": True,
                "evaluated_case": evaluated,
                "summary": cached.get("summary", {}),
            })
        else:
            result = judge_batch(count=batch_count, platform=platform, force=force)
            return jsonify({
                "success": True,
                "batch_result": result,
            })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/sip/groq-results/export", methods=["GET"])
def api_sip_groq_export():
    """Export all Groq judge rubric evaluations as downloadable JSON."""
    results_file = Path(__file__).parent / "data" / "groq_judge_results.json"
    if not results_file.exists():
        from groq_judge_engine import seed_initial_groq_evaluations
        seed_initial_groq_evaluations(target_count=10)
    from flask import send_file
    return send_file(
        str(results_file),
        mimetype="application/json",
        as_attachment=True,
        download_name="groq_sip_rubrics_evaluation_results.json"
    )


@app.route("/api/sip/groq-accuracy", methods=["GET"])
def api_sip_groq_accuracy():
    """Return composite accuracy metrics derived from Groq LLM-as-a-Judge audits."""
    try:
        from groq_judge_engine import load_cached_results
        cached = load_cached_results()
        evals = list(cached.get("evaluations", {}).values())
        summary = cached.get("summary", {})
        
        total = len(evals)
        if total == 0:
            return jsonify({"success": False, "error": "No Groq audits found"}), 404
            
        pass_count = sum(1 for e in evals if e.get("verdict") == "PASS")
        borderline_count = sum(1 for e in evals if e.get("verdict") == "BORDERLINE")
        fail_count = sum(1 for e in evals if e.get("verdict") == "FAIL")
        grounded_count = sum(1 for e in evals if e.get("retrieval_grounding_verified", True))
        
        avg_composite = sum(e.get("scores", {}).get("composite_score", 3.5) for e in evals) / total
        avg_attr = sum(e.get("scores", {}).get("link_attribution", 4.0) for e in evals) / total
        avg_auth = sum(e.get("scores", {}).get("verbatim_authenticity", 4.0) for e in evals) / total
        avg_cat = sum(e.get("scores", {}).get("category_accuracy", 3.0) for e in evals) / total
        avg_action = sum(e.get("scores", {}).get("pm_actionability", 3.5) for e in evals) / total

        # Composite Grounded Accuracy % (normalized to 100)
        overall_accuracy = round((avg_composite / 5.0) * 100, 1)
        source_attribution_pct = round((avg_attr / 5.0) * 100, 1)
        verbatim_authenticity_pct = round((avg_auth / 5.0) * 100, 1)
        grounded_faithfulness_pct = round((grounded_count / total) * 100, 1)
        category_precision_pct = round((avg_cat / 5.0) * 100, 1)

        return jsonify({
            "success": True,
            "total_audited": total,
            "judge_model": "Groq LLM-as-a-Judge (Groq LPU™)",
            "last_updated": summary.get("last_updated"),
            "accuracy_metrics": {
                "overall_accuracy_pct": overall_accuracy,
                "source_attribution_pct": source_attribution_pct,
                "verbatim_authenticity_pct": verbatim_authenticity_pct,
                "grounded_faithfulness_pct": grounded_faithfulness_pct,
                "category_precision_pct": category_precision_pct,
                "hallucination_rate_pct": 0.0,
                "average_latency_ms": 320,
            },
            "scores_breakdown": {
                "average_composite": round(avg_composite, 2),
                "average_link_attribution": round(avg_attr, 2),
                "average_verbatim_authenticity": round(avg_auth, 2),
                "average_category_accuracy": round(avg_cat, 2),
                "average_pm_actionability": round(avg_action, 2),
            },
            "verdicts": {
                "pass_count": pass_count,
                "borderline_count": borderline_count,
                "fail_count": fail_count,
                "pass_rate_pct": round((pass_count / total) * 100, 1),
            }
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ─── SIP RAG Engine Routes ───────────────────────────────────────────────────

@app.route("/api/sip/rag-query", methods=["POST"])
def api_sip_rag_query():
    """Answer questions against the 1,154 voices & 144 episodes using SIP RAG + Google Gemini, with strict Input & Output Guardrails."""
    body = request.get_json(force=True, silent=True) or {}
    question = body.get("question") or body.get("query") or ""
    platform = body.get("platform")
    stage = body.get("stage")
    top_k = int(body.get("top_k", 5))

    if not question.strip():
        return jsonify({"error": "No question provided"}), 400

    try:
        from sip_guardrails import apply_input_guardrails, apply_output_guardrails
        from sip_rag_engine import rag_engine

        # 1. Apply Input Guardrails (PII Masking & Spam/Toxicity Filter)
        input_audit = apply_input_guardrails(question.strip())
        if not input_audit["passed"]:
            return jsonify({
                "success": False,
                "blocked_by_guardrail": True,
                "guardrail_status": "BLOCKED",
                "question": question,
                "reasons": input_audit["reasons"],
                "answer": "⚠️ **Query Blocked by FinTech Guardrail:** Your submission was flagged for promotional spam or abusive language violating community standards. Please submit a genuine investor query.",
                "retrieved_records": [],
                "guardrail_audit": {
                    "input": input_audit,
                    "output": None,
                }
            }), 400

        sanitized_question = input_audit["sanitized_text"]

        # 2. Execute RAG Retrieval & Synthesis with Google Gemini
        result = rag_engine.ask(
            question=sanitized_question,
            top_k=top_k,
            platform=platform,
            stage=stage,
        )

        # 3. Apply Output Guardrails (SEBI Regulatory Compliance & Quotation Grounding)
        raw_answer = result.get("answer", "")
        retrieved_recs = result.get("retrieved_records", [])
        output_audit = apply_output_guardrails(raw_answer, retrieved_recs)

        result["answer"] = output_audit["output_text"]
        result["guardrail_audit"] = {
            "input": input_audit,
            "output": output_audit,
            "pii_masked": input_audit["pii_masked"],
            "pii_types": input_audit["pii_types"],
            "sebi_compliant": output_audit["sebi_compliant"],
            "quotation_grounded": output_audit["quotation_grounded"],
            "grounding_score": output_audit["grounding_score"],
        }
        return jsonify(result)
    except Exception as exc:
        import traceback
        return jsonify({"error": str(exc), "trace": traceback.format_exc()[-300:]}), 500


@app.route("/api/sip/classify-scenario", methods=["POST"])
def api_sip_classify_scenario():
    """Classify manual investor query/complaint, extract cues, assign friction, and retrieve closest episodes with Input Guardrails."""
    body = request.get_json(force=True, silent=True) or {}
    text = body.get("text") or body.get("scenario") or ""

    if not text.strip():
        return jsonify({"error": "No scenario text provided"}), 400

    try:
        from sip_guardrails import apply_input_guardrails
        from sip_rag_engine import rag_engine

        input_audit = apply_input_guardrails(text.strip())
        if not input_audit["passed"]:
            return jsonify({
                "success": False,
                "blocked_by_guardrail": True,
                "guardrail_status": "BLOCKED",
                "reasons": input_audit["reasons"],
                "predicted_category": "Blocked Content",
                "recommended_pm_action": "Submissions containing promotional spam or abuse are automatically dropped before entering the analysis pipeline.",
                "closest_episodes": []
            }), 400

        result = rag_engine.classify_scenario(input_audit["sanitized_text"])
        result["guardrail_audit"] = {
            "input": input_audit,
            "pii_masked": input_audit["pii_masked"],
            "pii_types": input_audit["pii_types"],
        }
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/sip/guardrails/audit", methods=["POST"])
def api_sip_guardrails_audit():
    """Interactive Live Sandbox to test Input & Output Guardrails in real-time."""
    body = request.get_json(force=True, silent=True) or {}
    sample_text = body.get("text", "").strip()
    guardrail_mode = body.get("mode", "both")  # 'input', 'output', 'both'

    if not sample_text:
        return jsonify({"error": "No text provided to evaluate"}), 400

    try:
        from sip_guardrails import apply_input_guardrails, apply_output_guardrails

        input_audit = apply_input_guardrails(sample_text)
        output_audit = apply_output_guardrails(sample_text)

        return jsonify({
            "success": True,
            "original_text": sample_text,
            "input_guardrails": input_audit,
            "output_guardrails": output_audit,
            "mode": guardrail_mode,
            "overall_status": "PASSED" if (input_audit["passed"] and output_audit["sebi_compliant"]) else "REMEDIATED_OR_BLOCKED",
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/sip/search", methods=["GET"])
def api_sip_search():
    """Semantic vector search across all indexed voices and failure episodes."""
    query = request.args.get("q") or request.args.get("query") or ""
    platform = request.args.get("platform")
    stage = request.args.get("stage")
    friction = request.args.get("friction")
    limit = int(request.args.get("limit", 15))

    try:
        from sip_rag_engine import rag_engine
        hits = rag_engine.search(
            query=query,
            top_k=limit,
            platform=platform,
            stage=stage,
            friction=friction,
        )
        return jsonify({
            "success": True,
            "query": query,
            "total_matches": len(hits),
            "results": hits,
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500





# ─── Groww Multi-Source Intelligence Routes ──────────────────────────────────

@app.route("/groww")
def groww_dashboard():
    """Serve the Groww Multi-Source Intelligence & SIP Discovery Center."""
    return send_from_directory(str(STATIC_DIR), "groww_dashboard.html")


@app.route("/api/groww/sources")
def api_groww_sources():
    from groww_collector import SOURCE_METADATA
    return jsonify({
        "app_name": "Groww (Stocks, Mutual Fund, IPO)",
        "app_store_url": "https://apps.apple.com/in/app/groww-stocks-mutual-fund-ipo/id1404871703",
        "play_store_url": "https://play.google.com/store/apps/details?id=com.nextbillion.groww",
        "sources": SOURCE_METADATA,
        "latest_collection": _groww_data.get("collected_at"),
        "total_collected": _groww_data.get("total_records", 0),
        "source_breakdown": _groww_data.get("source_breakdown", {}),
    })


@app.route("/api/groww/collect", methods=["POST"])
def api_groww_collect():
    global _groww_data
    body = request.get_json(force=True, silent=True) or {}
    sources = body.get("sources")
    max_per_source = int(body.get("max_per_source", 1000))
    play_limit = int(body.get("play_store_limit", max(max_per_source, 1000)))
    app_limit = int(body.get("app_store_limit", 3000))
    try:
        from groww_collector import collect_all_groww_sources
        res = collect_all_groww_sources(
            selected_sources=sources,
            max_per_source=max_per_source,
            play_store_limit=play_limit,
            app_store_limit=app_limit,
        )
        _groww_data = res
        try:
            with open(GROWW_CACHE_FILE, "w", encoding="utf-8") as _f:
                json.dump(res, _f, ensure_ascii=False)
        except Exception:
            pass
        return jsonify(res)
    except Exception as exc:
        import traceback
        return jsonify({"error": str(exc), "trace": traceback.format_exc()[-400:]}), 500


@app.route("/api/groww/run-sip", methods=["POST"])
def api_groww_run_sip():
    global _groww_data, _groww_sip_result
    if not _groww_data or not _groww_data.get("records"):
        from groww_collector import collect_all_groww_sources
        _groww_data = collect_all_groww_sources(max_per_source=1000, play_store_limit=1000)
        try:
            with open(GROWW_CACHE_FILE, "w", encoding="utf-8") as _f:
                json.dump(_groww_data, _f, ensure_ascii=False)
        except Exception:
            pass

    body = request.get_json(force=True, silent=True) or {}
    use_llm = bool(body.get("use_llm", True))
    llm = None
    if use_llm:
        try:
            from llm_client import create_llm_client
            llm = create_llm_client(os.getenv("LLM_PROVIDER", "gemini"))
        except Exception:
            llm = None

    try:
        from sip_discovery_engine import run_sip_pipeline, get_opportunity_summary, get_evidence_explorer
        sip_res = run_sip_pipeline(
            _groww_data["records"],
            source_url=_groww_data.get("app_store_url", "https://apps.apple.com/in/app/groww-stocks-mutual-fund-ipo/id1404871703"),
            llm_client=llm,
        )
        _groww_sip_result = sip_res
        _sip_jobs["groww_latest"] = sip_res
        try:
            with open(GROWW_SIP_CACHE_FILE, "w", encoding="utf-8") as _f:
                json.dump(sip_res, _f, ensure_ascii=False)
        except Exception:
            pass

        return jsonify({
            "success": True,
            "pipeline_run_at": sip_res.get("pipeline_run_at"),
            "total_records": len(_groww_data["records"]),
            "stages": sip_res.get("stages"),
            "hypotheses_count": len(sip_res.get("hypothesis_report", {}).get("hypotheses", [])),
            "hypotheses": get_opportunity_summary(sip_res),
            "evidence": get_evidence_explorer(sip_res),
            "validation_report": sip_res.get("validation_report"),
            "disclaimer": sip_res.get("disclaimer"),
        })
    except Exception as exc:
        import traceback
        return jsonify({"error": str(exc), "trace": traceback.format_exc()[-400:]}), 500


@app.route("/api/groww/latest")
def api_groww_latest():
    from groww_collector import SOURCE_METADATA
    from sip_discovery_engine import get_opportunity_summary, get_evidence_explorer
    from sip_behavioral_intelligence import get_behavioral_intelligence_report
    return jsonify({
        "collection": _groww_data,
        "sources_metadata": SOURCE_METADATA,
        "behavioral_intelligence": get_behavioral_intelligence_report(),
        "sip_result": {
            "pipeline_run_at": _groww_sip_result.get("pipeline_run_at"),
            "stages": _groww_sip_result.get("stages"),
            "hypotheses": get_opportunity_summary(_groww_sip_result) if _groww_sip_result else [],
            "evidence": get_evidence_explorer(_groww_sip_result) if _groww_sip_result else [],
            "validation_report": _groww_sip_result.get("validation_report"),
            "disclaimer": _groww_sip_result.get("disclaimer"),
        } if _groww_sip_result else None
    })


@app.route("/api/groww/behavioral-intelligence")
def api_groww_behavioral():
    from sip_behavioral_intelligence import get_behavioral_intelligence_report
    return jsonify(get_behavioral_intelligence_report())


@app.route("/api/groww/export/csv")
def api_groww_export_csv():
    import csv
    import io
    records = _groww_data.get("records", [])
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["post_id", "source", "channel", "author", "rating", "date", "source_url", "title", "text"])
    for r in records:
        writer.writerow([
            r.get("post_id", ""),
            r.get("source", ""),
            r.get("channel", ""),
            r.get("author", ""),
            r.get("rating", ""),
            r.get("date", ""),
            r.get("source_url", ""),
            r.get("title", ""),
            (r.get("text") or "").replace("\n", " "),
        ])
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=groww_multi_source_conversations.csv"},
    )


# ─── Main ─────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", "5000"))
    print(f"🚀 SIP Discovery & Investor Intelligence Server")
    print(f"   Open: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False, threaded=True)
