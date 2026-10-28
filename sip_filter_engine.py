#!/usr/bin/env python3
"""
SIP Filter Engine: Classifies, Filters, and Structures all Multi-Source Conversations
specifically for SIP (Systematic Investment Plan) Intelligence & Retention.

Filters out off-topic comments (generic pleasantries, unrelated stocks, bot spam)
and isolates high-signal conversations regarding:
- SIP Setup & Auto-Pay Mandate Failures
- SIP Pause, Skip & Cancellation Behavior
- Performance Anxiety & Negative XIRR Panic (Loss Aversion)
- Step-Up / Top-Up SIP Execution & Limits
- First-Time Onboarding & KYC
- Demat Folios vs AMC Direct Folios
- Asset Allocation & Fund Overlap
- Taxation & Locked-in Units (ELSS)
"""

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sip_filter_engine")

DATA_DIR = Path(__file__).parent / "data"
OUTPUT_FILE = DATA_DIR / "sip_filtered_intelligence.json"

# Strict SIP domain indicators
SIP_CORE_TERMS = [
    r"\bsip\b", r"\bsips\b", r"\bsystematic investment\b", r"\bmutual fund\b",
    r"\bmutual funds\b", r"\bautopay\b", r"\bauto-pay\b", r"\bauto debit\b",
    r"\bauto-debit\b", r"\bmandate\b", r"\bnach\b", r"\bstep-up\b", r"\bstep up\b",
    r"\btop-up sip\b", r"\bsip pause\b", r"\bpause sip\b", r"\bsip cancel\b",
    r"\bcancel sip\b", r"\bskip sip\b", r"\bstop sip\b", r"\bstopped my sip\b",
    r"\bxirr\b", r"\bnav\b", r"\bfolio\b", r"\bfoli\b", r"\bamc\b", r"\bcams\b",
    r"\bkfintech\b", r"\belss\b", r"\bindex fund\b", r"\bsmall cap\b", r"\bmid cap\b",
    r"\bflexi cap\b", r"\blumpsum\b", r"\blump sum\b", r"\bfirst time invest\b",
    r"\bmonthly invest\b", r"\b500 rs\b", r"\brs 500\b", r"\b1000 per month\b",
    r"\bportfolio red\b", r"\bmarket dip\b", r"\bmarket crash\b", r"\brupee cost\b",
    r"\bbounce fee\b", r"\binstalment\b", r"\binstallment\b", r"\bcoin vs groww\b"
]

SIP_CATEGORIES = {
    "autopay_mandate": {
        "id": "autopay_mandate",
        "name": "Auto-Pay & Bank Mandate",
        "icon": "payments",
        "badge_color": "#ef4444",
        "bg_color": "rgba(239, 68, 68, 0.12)",
        "keywords": [
            "autopay", "auto-pay", "auto debit", "auto-debit", "mandate", "nach",
            "bank debit", "deduction", "bounce", "penalty", "failed mandate",
            "icici", "hdfc", "sbi", "otp", "debit failed", "twice", "double debit"
        ],
        "pm_theme": "Friction in automated bank deductions causes immediate distrust and penalty fees."
    },
    "pause_skip_cancel": {
        "id": "pause_skip_cancel",
        "name": "SIP Pause, Skip & Cancellation",
        "icon": "pause_circle",
        "badge_color": "#f97316",
        "bg_color": "rgba(249, 115, 22, 0.12)",
        "keywords": [
            "pause", "skip sip", "cancel", "stop", "stopped my sip", "cancelled",
            "delete sip", "halt", "job switch", "emergency", "temporary", "holding"
        ],
        "pm_theme": "Users wishing to temporarily pause often delete SIPs completely due to hidden pause options."
    },
    "step_up": {
        "id": "step_up",
        "name": "Step-Up & Top-Up SIP",
        "icon": "trending_up",
        "badge_color": "#06b6d4",
        "bg_color": "rgba(6, 182, 212, 0.12)",
        "keywords": [
            "step-up", "step up", "top up", "top-up", "increment", "annual increase",
            "10%", "salary hike", "mandate limit", "exceed", "raise amount"
        ],
        "pm_theme": "Step-up SIPs fail silently or trigger bank bounce when instalments exceed the original mandate ceiling."
    },
    "performance_anxiety": {
        "id": "performance_anxiety",
        "name": "Market Dips & Loss Aversion",
        "icon": "show_chart",
        "badge_color": "#8b5cf6",
        "bg_color": "rgba(139, 92, 246, 0.12)",
        "keywords": [
            "loss", "red", "negative", "xirr", "down", "market crash", "panic",
            "fall", "bleeding", "dip", "psychological", "fear", "notifications",
            "first time loss", "bear market", "-4%", "-6%", "-10%"
        ],
        "pm_theme": "First-time investors panic seeing negative returns in months 3-6; alarmist push notifications trigger churn."
    },
    "first_time_onboarding": {
        "id": "first_time_onboarding",
        "name": "First-Time Onboarding & KYC",
        "icon": "person_add",
        "badge_color": "#10b981",
        "bg_color": "rgba(16, 185, 129, 0.12)",
        "keywords": [
            "first time", "beginner", "how to start", "kyc", "pan", "aadhaar",
            "college", "student", "22yo", "23yo", "first salary", "direct vs regular",
            "expense ratio", "500", "minimum"
        ],
        "pm_theme": "Beginners need reassurance regarding regulatory safety (AMFI/SEBI) and simple minimums (₹500)."
    },
    "demat_vs_amc": {
        "id": "demat_vs_amc",
        "name": "Demat vs AMC Folios & Tracking",
        "icon": "account_balance",
        "badge_color": "#3b82f6",
        "bg_color": "rgba(59, 130, 246, 0.12)",
        "keywords": [
            "demat", "non-demat", "folio", "cams", "kfintech", "cas", "bse star",
            "coin", "amc direct", "units", "transfer", "statement", "shut down"
        ],
        "pm_theme": "Confusion around what happens if the fintech shuts down (units are safe with AMC/CAMS)."
    },
    "fund_allocation": {
        "id": "fund_allocation",
        "name": "Fund Allocation & Overlap",
        "icon": "pie_chart",
        "badge_color": "#ec4899",
        "bg_color": "rgba(236, 72, 153, 0.12)",
        "keywords": [
            "small cap", "index fund", "nifty 50", "flexi cap", "parag parikh",
            "overlap", "diversification", "multi asset", "etf", "how many funds",
            "portfolio review", "allocation"
        ],
        "pm_theme": "Beginners over-diversify into 8+ overlapping funds or over-concentrate in high-volatility small caps."
    },
    "taxation_redemption": {
        "id": "taxation_redemption",
        "name": "Taxation & Locked Units",
        "icon": "receipt_long",
        "badge_color": "#f59e0b",
        "bg_color": "rgba(245, 158, 11, 0.12)",
        "keywords": [
            "tax", "ltcg", "stcg", "elss", "80c", "lock-in", "3 years", "redeem",
            "withdrawal", "exit load", "1.25 lakh", "itr"
        ],
        "pm_theme": "ELSS SIPs lock each instalment separately for 36 months, catching first-time redeemers by surprise."
    }
}


def is_sip_relevant(text: str, title: str = "") -> Tuple[bool, List[str]]:
    combined = f"{title} {text}".lower()
    matched_terms = []
    for pattern in SIP_CORE_TERMS:
        if re.search(pattern, combined):
            matched_terms.append(pattern.replace(r"\b", ""))
    return (len(matched_terms) > 0), matched_terms


def classify_sip_category(text: str, title: str = "") -> Tuple[str, Dict[str, Any]]:
    combined = f"{title} {text}".lower()
    best_cat = "fund_allocation"  # Default fallback
    max_score = 0

    for cat_key, cat_data in SIP_CATEGORIES.items():
        score = 0
        for kw in cat_data["keywords"]:
            if kw in combined:
                score += 1
                if kw in ("autopay", "auto-pay", "pause", "step-up", "xirr", "bounce", "demat", "elss"):
                    score += 2  # Strong indicator
        if score > max_score:
            max_score = score
            best_cat = cat_key

    return best_cat, SIP_CATEGORIES[best_cat]


def determine_friction_and_intent(text: str, lower: str, category_key: str) -> Tuple[str, str, str]:
    # Friction level
    high_churn_words = ["stopped my sip", "cancelled sip", "delete sip", "closed account", "charged 590", "bounce fee", "scam", "lost money", "uninstall"]
    medium_friction_words = ["delayed", "not working", "stuck", "confused", "cannot find", "failed", "freeze", "error", "processing", "panic", "fear"]
    
    if any(w in lower for w in high_churn_words):
        friction_level = "Critical Churn Risk"
        friction_color = "#ef4444"
    elif any(w in lower for w in medium_friction_words):
        friction_level = "Moderate Friction"
        friction_color = "#f59e0b"
    elif any(w in lower for w in ["how to", "which", "suggest", "guide", "query", "question", "advice"]):
        friction_level = "Investor Inquiry"
        friction_color = "#06b6d4"
    else:
        friction_level = "Informational & Learning"
        friction_color = "#10b981"

    # User Intent
    if category_key == "autopay_mandate":
        intent = "Mandate Setup / Payment Debit Friction"
        pm_insight = "Introduce bank pre-debit notifications (T-24h) and multi-bank fallback to prevent ₹590 NACH bounce penalties."
    elif category_key == "pause_skip_cancel":
        intent = "Evaluating Churn or Liquidity Relief"
        pm_insight = "Prominently surface 'Pause for 1–3 Months' and 'Skip Next Instalment' instead of forcing users to delete their SIP."
    elif category_key == "performance_anxiety":
        intent = "Loss Aversion / Market Correction Anxiety"
        pm_insight = "Replace alarmist 'Market down 400 pts' push notifications with contextual educational nudges highlighting rupee-cost averaging."
    elif category_key == "step_up":
        intent = "Compounding Optimization / Limit Check"
        pm_insight = "Automatically validate existing bank mandate max ceilings before allowing investors to activate annual step-ups."
    elif category_key == "demat_vs_amc":
        intent = "Safety & Unit Custody Inquiry"
        pm_insight = "Provide clear 'Your units are held safely with AMC & tracked on CAMS' badge to alleviate platform failure fears."
    elif category_key == "first_time_onboarding":
        intent = "First-Time SIP Initiation"
        pm_insight = "Offer simplified 1-click curated starter baskets (e.g. Nifty 50 Index + Parag Parikh Flexi) with ₹500 minimums."
    elif category_key == "taxation_redemption":
        intent = "Tax Liability / Lock-in Awareness"
        pm_insight = "Display clear maturity timelines for each ELSS instalment to prevent user shock when partial redemption is rejected."
    else:
        intent = "Asset Allocation & Strategy Optimization"
        pm_insight = "Add an in-app portfolio overlap analyzer to warn users against holding multiple identical large-cap funds."

    return friction_level, intent, pm_insight


def filter_and_enrich_sip_dataset(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Evaluates all raw records, filters exclusively to SIP-relevant items,
    and enriches with category, friction level, intent, and actionable PM takeaways.
    """
    sip_items = []
    category_counts = {k: 0 for k in SIP_CATEGORIES}
    source_counts = {}
    friction_counts = {}

    for r in records:
        text = r.get("text") or ""
        title = r.get("title") or ""
        lower = f"{title} {text}".lower()

        # Exclude bot messages like AutoModerator
        author = str(r.get("author", "")).lower()
        if "automoderator" in author or "bot" in author:
            continue

        is_rel, matched_kws = is_sip_relevant(text, title)
        if not is_rel:
            continue

        cat_key, cat_meta = classify_sip_category(text, title)
        category_counts[cat_key] += 1

        friction_level, intent, pm_insight = determine_friction_and_intent(text, lower, cat_key)
        friction_counts[friction_level] = friction_counts.get(friction_level, 0) + 1

        src_code = r.get("source_code", "other")
        source_counts[src_code] = source_counts.get(src_code, 0) + 1

        enriched_item = {
            **r,
            "is_sip_related": True,
            "sip_category": cat_key,
            "sip_category_name": cat_meta["name"],
            "sip_category_icon": cat_meta["icon"],
            "sip_badge_color": cat_meta["badge_color"],
            "sip_bg_color": cat_meta["bg_color"],
            "sip_matched_terms": matched_kws[:5],
            "sip_friction_level": friction_level,
            "sip_user_intent": intent,
            "pm_actionable_insight": pm_insight,
        }
        sip_items.append(enriched_item)

    logger.info(f"SIP Filter Complete: {len(sip_items)} relevant items found from {len(records)} total records.")

    result = {
        "success": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_evaluated": len(records),
        "total_sip_relevant": len(sip_items),
        "relevance_rate_pct": round((len(sip_items) / max(len(records), 1)) * 100, 1),
        "categories_metadata": SIP_CATEGORIES,
        "category_breakdown": category_counts,
        "source_breakdown": source_counts,
        "friction_breakdown": friction_counts,
        "sip_records": sip_items
    }

    DATA_DIR.mkdir(exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved {OUTPUT_FILE.name} with {len(sip_items)} enriched SIP conversations.")

    return result


if __name__ == "__main__":
    cache_path = Path(__file__).parent / "groww_cache.json"
    if cache_path.exists():
        with open(cache_path, "r", encoding="utf-8") as f:
            cdata = json.load(f)
            filter_and_enrich_sip_dataset(cdata.get("records", []))
    else:
        print("groww_cache.json not found!")
