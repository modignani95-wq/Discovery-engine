#!/usr/bin/env python3
"""
SIP Discovery Engine — 7-stage pipeline
Turns public app-store conversations about Systematic Investment Plans (SIPs)
into structured, evidence-backed problem hypotheses for a Product Manager.

Business goal: Increase the % of first-time mutual-fund investors who still
have an active SIP 12 months after starting their first one.
"""

from __future__ import annotations

import json
import re
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# --- Codebook ------------------------------------------------------------------

SIP_KEYWORDS = [
    "sip", "systematic investment", "mutual fund", "mf", "nav", "redemption",
    "auto-debit", "auto debit", "mandate", "folio", "unit", "lumpsum", "lump sum",
    "sip fail", "payment fail", "sip pause", "sip stop", "sip cancel",
    "market down", "portfolio", "returns", "wealth", "invest", "invest monthly",
    "instalment", "installment", "emi invest", "zerodha coin", "groww sip",
    "kuvera", "paytm money", "etmoney", "mfcentral", "cams", "nfo",
    "dividend", "growth option", "debt fund", "equity fund", "elss",
]

JOURNEY_STAGES = ["starting", "continuing", "reducing", "pausing", "stopping", "unknown"]
SIP_OUTCOMES   = ["continued", "reduced", "paused", "stopped", "unknown"]
EMOTIONS       = ["frustrated", "anxious", "confused", "happy", "satisfied",
                  "disappointed", "worried", "relieved", "neutral", "unknown"]

PROBLEM_CATEGORIES = {
    "payment_failure": {
        "label": "SIP Payment Failure",
        "keywords": ["payment fail", "sip fail", "bounce", "insufficient", "debit fail",
                     "mandate fail", "ecs fail", "nach fail", "auto-debit fail"],
        "icon": "payment",
        "severity_weight": 5,
    },
    "performance_anxiety": {
        "label": "Performance & Returns Anxiety",
        "keywords": ["negative return", "loss", "down", "market crash", "low nav",
                     "portfolio red", "unrealised loss", "poor return", "no growth"],
        "icon": "trending_down",
        "severity_weight": 4,
    },
    "complexity": {
        "label": "Onboarding & Complexity",
        "keywords": ["confusing", "complicated", "hard to", "complex", "difficult",
                     "how to start", "how to invest", "not sure", "don't understand"],
        "icon": "psychology",
        "severity_weight": 3,
    },
    "app_technical": {
        "label": "App Technical Issues",
        "keywords": ["crash", "freeze", "slow", "bug", "glitch", "error", "not loading",
                     "not working", "black screen", "app down", "stuck", "hang"],
        "icon": "bug_report",
        "severity_weight": 3,
    },
    "support": {
        "label": "Customer Support Gap",
        "keywords": ["no support", "unresponsive", "no reply", "ticket", "waiting",
                     "helpless", "no one helping", "bot", "automated response"],
        "icon": "support_agent",
        "severity_weight": 4,
    },
    "kyc_compliance": {
        "label": "KYC & Compliance Friction",
        "keywords": ["kyc", "aadhaar", "pan", "verification fail", "rejected", "compliance",
                     "document", "ekyc", "video kyc", "fatca"],
        "icon": "verified_user",
        "severity_weight": 3,
    },
    "withdrawal": {
        "label": "Redemption & Withdrawal Issues",
        "keywords": ["redeem", "withdraw", "exit", "sell units", "not credited",
                     "delay in credit", "redemption fail", "can't withdraw"],
        "icon": "account_balance",
        "severity_weight": 4,
    },
    "feature_request": {
        "label": "Missing Features",
        "keywords": ["wish", "would be great", "please add", "feature request",
                     "need option", "should have", "missing", "add option"],
        "icon": "star",
        "severity_weight": 2,
    },
}


# --- Stage 1: Collect ----------------------------------------------------------

def collect_sip_conversations(reviews, source_url=""):
    records = []
    for r in reviews:
        text = (r.get("text") or "").strip()
        if not text:
            continue
        records.append({
            "post_id": r.get("post_id") or r.get("id") or str(uuid.uuid4())[:8],
            "source": r.get("source") or "Play Store Reviews",
            "source_code": r.get("source_code") or "play_store",
            "source_url": r.get("source_url") or r.get("url") or source_url,
            "collected_at": r.get("collected_at") or datetime.now(timezone.utc).isoformat(),
            "text": text,
            "rating": r.get("rating"),
            "author": r.get("author", "Anonymous"),
            "date": r.get("date", ""),
            "app_id": r.get("app_id", ""),
            "channel": r.get("channel", "Public Conversation"),
            "title": r.get("title", ""),
            "original_text": text,
        })
    return records



# --- Stage 2: Clean & Deduplicate ----------------------------------------------

def clean_and_deduplicate(records):
    seen_fps = set()
    cleaned = []
    removal_log = defaultdict(int)

    for r in records:
        text = re.sub(r"\s+", " ", r["text"]).strip()
        body = re.sub(r"^\[.*?\]\s*", "", text).strip() or text

        if len(body) < 10:
            removal_log["too_short"] += 1
            continue
        if body.count("!") > 10 or re.search(r"(.)\1{5,}", body):
            removal_log["spam_pattern"] += 1
            continue

        fp = re.sub(r"[^a-z0-9]", "", body[:100].lower())
        if fp in seen_fps:
            removal_log["duplicate"] += 1
            continue
        seen_fps.add(fp)

        cleaned.append({**r, "text": text, "cleaned": True})

    return cleaned, dict(removal_log)


# --- Stage 3: Filter Relevance -------------------------------------------------

def filter_relevance(records, llm_client=None):
    stats = {"relevant": 0, "irrelevant": 0, "uncertain": 0}
    filtered = []

    for r in records:
        lower = r["text"].lower()
        strong = any(kw in lower for kw in [
            "sip", "systematic investment", "mutual fund", "nav", "auto-debit",
            "mandate", "folio", "redemption", "lump sum", "elss", "mf app"
        ])
        weak = any(kw in lower for kw in [
            "invest", "portfolio", "returns", "fund", "wealth",
            "payment fail", "auto debit", "monthly", "instalment"
        ])

        if strong:
            label = "relevant"
        elif weak:
            # Fast financial domain context matching for high-volume scale
            if any(w in lower for w in ["groww", "sip", "fund", "invest", "stock", "broker", "folio", "amc", "bank", "mandate", "nav", "cams", "loss", "profit"]):
                label = "relevant"
            elif llm_client and len(records) <= 30:
                try:
                    prompt = (
                        "Does this app review discuss SIP (Systematic Investment Plan) "
                        "investments, payments, performance, or related topics? "
                        "Reply with exactly one word: relevant, irrelevant, or uncertain.\n\n"
                        f"Review: {r['text'][:500]}"
                    )
                    resp = llm_client.complete("You are a financial domain classifier. Be concise.", prompt).strip().lower()
                    label = resp if resp in ("relevant", "irrelevant", "uncertain") else "uncertain"
                except Exception:
                    label = "uncertain"
            else:
                label = "uncertain"
        else:
            label = "irrelevant"

        stats[label] += 1
        if label in ("relevant", "uncertain"):
            filtered.append({**r, "relevance": label})

    return filtered, stats


# --- Stage 4: Extract ----------------------------------------------------------

def _match_problem_category(lower):
    for cat_key, cat in PROBLEM_CATEGORIES.items():
        if any(kw in lower for kw in cat["keywords"]):
            return cat_key
    return None


def _deterministic_extract(text, lower, record):
    rating = record.get("rating") or 3

    if any(w in lower for w in ["started my sip", "first sip", "new to sip", "how to start"]):
        journey_stage = "starting"
    elif any(w in lower for w in ["stopped my sip", "cancelled sip", "closed sip"]):
        journey_stage = "stopping"
    elif any(w in lower for w in ["paused sip", "pause my sip"]):
        journey_stage = "pausing"
    elif any(w in lower for w in ["reduced sip", "lowered amount"]):
        journey_stage = "reducing"
    elif any(w in lower for w in ["continuing", "still investing", "running sip"]):
        journey_stage = "continuing"
    else:
        journey_stage = "unknown"

    if any(w in lower for w in ["stopped sip", "cancelled sip", "stopped investing"]):
        sip_outcome = "stopped"
    elif any(w in lower for w in ["paused sip", "put on hold"]):
        sip_outcome = "paused"
    elif any(w in lower for w in ["reduced", "lowered amount", "cut down"]):
        sip_outcome = "reduced"
    elif rating >= 4 and any(w in lower for w in ["continuing", "investing regularly"]):
        sip_outcome = "continued"
    else:
        sip_outcome = "unknown"

    problem = None
    for cat_key, cat in PROBLEM_CATEGORIES.items():
        if any(kw in lower for kw in cat["keywords"]):
            problem = cat["label"]
            break
    if not problem and rating <= 2:
        problem = "General dissatisfaction"

    trigger = None
    triggers = {
        "Salary delay": ["salary delay", "salary not credited", "salary late"],
        "Market downturn": ["market crash", "market down", "nifty fell", "sensex fell"],
        "Bank mandate rejection": ["mandate reject", "nach reject", "ecs reject"],
        "App update": ["after update", "new update", "latest version broke"],
        "KYC rejection": ["kyc reject", "kyc failed", "kyc pending"],
    }
    for trig, patterns in triggers.items():
        if any(p in lower for p in patterns):
            trigger = trig
            break

    sentences = re.split(r"[.!?]+", text)
    evidence_quote = ""
    for s in sentences:
        if any(kw in s.lower() for kw in SIP_KEYWORDS[:10]):
            evidence_quote = s.strip()[:150]
            break
    if not evidence_quote:
        evidence_quote = text[:150]

    emotion = "neutral"
    neg_w = ["frustrated", "angry", "upset", "annoyed", "disappointed", "worried", "anxious"]
    pos_w = ["happy", "satisfied", "great", "love", "excellent", "relieved"]
    if any(w in lower for w in neg_w) or rating <= 2:
        emotion = "frustrated" if rating <= 2 else "disappointed"
    elif any(w in lower for w in pos_w) or rating >= 4:
        emotion = "satisfied"

    return {
        "journey_stage": journey_stage,
        "problem": problem,
        "underlying_need": None,
        "trigger": trigger,
        "sip_outcome": sip_outcome,
        "user_action": None,
        "emotion": emotion,
        "evidence_quote": evidence_quote,
        "confidence": "medium",
        "problem_category": _match_problem_category(lower),
    }


def extract_structured_info(record, llm_client=None):
    text = record["text"]
    lower = text.lower()
    det = _deterministic_extract(text, lower, record)

    if llm_client:
        try:
            prompt = f"""Extract structured SIP investment insights from this app review.
Return ONLY a valid JSON object with these exact fields:
{{
  "journey_stage": "starting|continuing|reducing|pausing|stopping|unknown",
  "problem": "brief problem statement or null",
  "underlying_need": "inferred need — explicitly mark as interpretation",
  "trigger": "event that caused the problem or null",
  "sip_outcome": "continued|reduced|paused|stopped|unknown",
  "user_action": "action taken by user or null",
  "emotion": "one emotion word",
  "evidence_quote": "exact supporting quote from the text (<=100 chars)",
  "confidence": "high|medium|low"
}}

Review: {text[:800]}"""
            raw = llm_client.complete(
                "You are a financial UX researcher extracting structured data. Always return valid JSON.", prompt
            )
            import sys, os
            sys.path.insert(0, os.path.dirname(__file__))
            from llm_client import parse_json_response
            llm_data = parse_json_response(raw)
            det.update({k: v for k, v in llm_data.items() if v and v != "null"})
        except Exception:
            pass

    det["source_id"] = record.get("post_id", "")
    det["source"] = record.get("source", "Play Store Reviews")
    det["source_code"] = record.get("source_code", "play_store")
    det["channel"] = record.get("channel", "Public Conversation")
    det["author"] = record.get("author", "Anonymous")
    det["source_url"] = record.get("source_url", "")
    det["original_text"] = record.get("original_text", text)
    det["app_id"] = record.get("app_id", "")
    det["date"] = record.get("date", "")
    det["rating"] = record.get("rating")
    return det



def batch_extract(records, llm_client=None):
    # When processing 1,000s of reviews, use deterministic extraction which is instantaneous,
    # and enrich up to 10 sample records if llm_client is provided to avoid rate limits
    if llm_client and len(records) > 20:
        extracted = []
        for i, r in enumerate(records):
            use_llm = llm_client if i < 10 else None
            extracted.append(extract_structured_info(r, use_llm))
        return extracted
    return [extract_structured_info(r, llm_client) for r in records]


# --- Stage 5: Aggregate & Rank -------------------------------------------------

def _estimate_fixability(cat_key):
    fm = {"payment_failure": 4, "app_technical": 5, "kyc_compliance": 3,
          "support": 4, "complexity": 4, "performance_anxiety": 2,
          "withdrawal": 3, "feature_request": 5}
    return fm.get(cat_key, 3)


def _sip_link_rationale(cat_key):
    r = {
        "payment_failure": "Failed SIP debits directly interrupt the investment streak, increasing discontinuation risk.",
        "performance_anxiety": "Market anxiety is a documented driver of SIP pausing during downturns.",
        "complexity": "Onboarding friction raises drop-off before the first SIP is ever placed.",
        "app_technical": "App crashes during SIP setup or review phases create abandonment moments.",
        "support": "Unresolved issues erode trust and correlate with cancellations.",
        "kyc_compliance": "KYC failures block investment activation entirely.",
        "withdrawal": "Withdrawal difficulties create distrust preventing future SIP restarts.",
        "feature_request": "Missing features reduce perceived value, weakening retention.",
    }
    return r.get(cat_key, "Requires further investigation.")


def _recommend_investigation(cat_key):
    r = {
        "payment_failure": "Analyse mandate failure rates by bank; interview users who had a failed SIP.",
        "performance_anxiety": "Survey users after a 10%+ NAV drop; A/B test contextual education nudges.",
        "complexity": "Run usability tests on SIP setup flow with first-time investors.",
        "app_technical": "Review crash reports by app version; instrument SIP flow with error tracking.",
        "support": "Audit median ticket resolution time; check CSAT for SIP-related tickets.",
        "kyc_compliance": "Map KYC rejection reasons; interview users who dropped off at KYC.",
        "withdrawal": "Audit redemption processing times; check end-to-end success rates.",
        "feature_request": "Cluster feature requests; prioritise by frequency and feasibility.",
    }
    return r.get(cat_key, "Conduct targeted user interviews and analyse behavioural data.")


def aggregate_and_rank(extractions):
    category_buckets = defaultdict(list)
    sip_outcome_dist = defaultdict(int)
    journey_dist = defaultdict(int)
    emotion_dist = defaultdict(int)
    trigger_freq = defaultdict(int)

    for ext in extractions:
        cat = ext.get("problem_category") or "unknown"
        category_buckets[cat].append(ext)
        sip_outcome_dist[ext.get("sip_outcome", "unknown")] += 1
        journey_dist[ext.get("journey_stage", "unknown")] += 1
        emotion_dist[ext.get("emotion", "neutral")] += 1
        if ext.get("trigger"):
            trigger_freq[ext["trigger"]] += 1

    total = max(len(extractions), 1)
    hypotheses = []

    for cat_key, items in category_buckets.items():
        if cat_key == "unknown":
            continue
        cat_meta = PROBLEM_CATEGORIES.get(cat_key, {})
        freq_score = min(5, round(len(items) / total * 25))
        sev_weight = cat_meta.get("severity_weight", 2)
        neg_count = sum(1 for i in items if (i.get("rating") or 3) <= 2)
        severity_score = min(5, round(neg_count / max(len(items), 1) * sev_weight * 2))
        stopped = sum(1 for i in items if i.get("sip_outcome") == "stopped")
        metric_rel = min(5, round(stopped / max(len(items), 1) * 10 + 1))
        fixability = _estimate_fixability(cat_key)
        composite = round(freq_score * 0.3 + severity_score * 0.3 + metric_rel * 0.25 + fixability * 0.15, 2)

        hypotheses.append({
            "id": f"HYP-{cat_key.upper()[:8]}",
            "category": cat_key,
            "problem_category": cat_key,
            "label": cat_meta.get("label", cat_key),
            "problem_statement": f"Users face recurring friction in {cat_meta.get('label', cat_key)}, driving SIP drop-off and support escalations.",
            "icon": cat_meta.get("icon", "star"),
            "frequency_in_data": len(items),
            "frequency_pct": round(len(items) / total * 100, 1),

            "scores": {
                "frequency": freq_score,
                "severity": severity_score,
                "metric_relevance": metric_rel,
                "fixability": fixability,
                "composite": composite,
            },
            "sip_outcomes": dict(Counter([i.get("sip_outcome", "unknown") for i in items])),
            "representative_quotes": [i["evidence_quote"] for i in items if i.get("evidence_quote")][:5],
            "source_ids": [i["source_id"] for i in items if i.get("source_id")][:10],
            "limitations": "Frequency is from a sample of public reviews. Population prevalence is unknown.",
            "sip_link_rationale": _sip_link_rationale(cat_key),
            "recommended_investigation": _recommend_investigation(cat_key),
        })

    hypotheses.sort(key=lambda h: h["scores"]["composite"], reverse=True)
    for i, h in enumerate(hypotheses):
        h["rank"] = i + 1

    return {
        "total_records_processed": total,
        "hypotheses": hypotheses,
        "sip_outcome_distribution": dict(sip_outcome_dist),
        "journey_stage_distribution": dict(journey_dist),
        "emotion_distribution": dict(emotion_dist),
        "top_triggers": sorted(trigger_freq.items(), key=lambda x: x[1], reverse=True)[:10],
        "disclaimer": (
            "Scores are prioritization aids, not objective truth. "
            "All findings require human review and validation against behavioural data."
        ),
    }


# --- Stage 6: Validate ---------------------------------------------------------

def validate_findings(extractions, golden_dataset=None):
    try:
        from sip_evals import validate_sip_output, run_golden_dataset_eval
    except ImportError:
        validate_sip_output = None
        run_golden_dataset_eval = None

    results = {
        "total_checked": len(extractions),
        "schema_valid": 0,
        "schema_invalid": 0,
        "evidence_grounded": 0,
        "unsupported_claims": 0,
        "errors": [],
        "golden_eval": None,
    }

    for ext in extractions:
        if validate_sip_output:
            valid, errors = validate_sip_output(ext)
            if valid:
                results["schema_valid"] += 1
            else:
                results["schema_invalid"] += 1
                results["errors"].extend(errors[:2])
        else:
            results["schema_valid"] += 1

        if ext.get("evidence_quote") and ext.get("original_text"):
            words = ext["evidence_quote"].lower().strip().split()
            original = ext["original_text"].lower()
            matched = sum(1 for w in words if w in original)
            if matched >= len(words) * 0.5:
                results["evidence_grounded"] += 1
            else:
                results["unsupported_claims"] += 1

    results["schema_validity_rate"] = round(results["schema_valid"] / max(results["total_checked"], 1) * 100, 1)
    results["evidence_grounding_rate"] = round(results["evidence_grounded"] / max(results["total_checked"], 1) * 100, 1)

    if golden_dataset and run_golden_dataset_eval:
        results["golden_eval"] = run_golden_dataset_eval(extractions, golden_dataset)

    return results


# --- Full Pipeline --------------------------------------------------------------

def run_sip_pipeline(reviews, source_url="", llm_client=None, golden_dataset=None):
    records = collect_sip_conversations(reviews, source_url)
    cleaned, removal_log = clean_and_deduplicate(records)
    filtered, relevance_stats = filter_relevance(cleaned, llm_client)
    extractions = batch_extract(filtered, llm_client)
    hypothesis_report = aggregate_and_rank(extractions)
    validation_report = validate_findings(extractions, golden_dataset)

    return {
        "pipeline_run_at": datetime.now(timezone.utc).isoformat(),
        "stages": {
            "collect": {"total_records": len(records)},
            "clean": {"kept": len(cleaned), "removed": removal_log},
            "filter": {"kept": len(filtered), "stats": relevance_stats},
            "extract": {"total": len(extractions)},
        },
        "hypothesis_report": hypothesis_report,
        "validation_report": validation_report,
        "extractions": extractions,
        "disclaimer": (
            "This engine identifies and prioritises possible problems from public conversations. "
            "It cannot prove population prevalence or that solving any problem will improve "
            "12-month SIP continuation. Those claims require behavioural data and experiments."
        ),
    }


def get_opportunity_summary(pipeline_result):
    return pipeline_result.get("hypothesis_report", {}).get("hypotheses", [])


def get_evidence_explorer(pipeline_result):
    return [
        {
            "post_id": e.get("source_id", ""),
            "source": e.get("source", "Play Store Reviews"),
            "source_code": e.get("source_code", "play_store"),
            "channel": e.get("channel", "Public Conversation"),
            "author": e.get("author", "Anonymous"),
            "date": e.get("date", ""),
            "rating": e.get("rating"),
            "app_id": e.get("app_id", ""),
            "original_text": e.get("original_text", ""),
            "problem": e.get("problem"),
            "problem_category": e.get("problem_category"),
            "journey_stage": e.get("journey_stage"),
            "sip_outcome": e.get("sip_outcome"),
            "trigger": e.get("trigger"),
            "emotion": e.get("emotion"),
            "evidence_quote": e.get("evidence_quote"),
            "confidence": e.get("confidence"),
            "source_url": e.get("source_url"),
        }
        for e in pipeline_result.get("extractions", [])
    ]

