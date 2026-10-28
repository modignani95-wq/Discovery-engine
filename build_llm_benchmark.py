#!/usr/bin/env python3
"""
Builds the LLM Grounding & Evaluation Benchmark Dataset.
Pairs every unique Source Link with its retrieved comments, reviews, metadata,
and test criteria so any external LLM (GPT-4o, Claude 3.5 Sonnet, Gemini Pro)
can test and rank retrieval accuracy, quote faithfulness, and SIP categorization.
"""

import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_llm_benchmark")

BASE_DIR = Path(__file__).parent
SIP_FILTERED_FILE = BASE_DIR / "data" / "sip_filtered_intelligence.json"
BENCHMARK_FILE = BASE_DIR / "data" / "llm_evaluation_benchmark.json"

LLM_EVAL_SYSTEM_PROMPT = """You are an independent AI Evaluation Judge specializing in financial technology and investor research.
Your task is to evaluate and rank the retrieval accuracy, faithfulness, and SIP relevance of public comments and reviews retrieved by an automated research engine.

For each test case, you are provided:
1. Source URL (where data was retrieved from)
2. Platform & Channel / Entity Name
3. Verbatim Retrieved Comment / Review Text
4. Extracted SIP Category & Intent
5. Proposed PM 12-Month Retention Action

Please evaluate and score the item on a 1–5 scale across 4 core dimensions:
1. link_provenance_accuracy (1-5): Is the source URL valid, authentic, and properly attributed to the creator/platform?
2. content_faithfulness (1-5): Is the retrieved text authentic user feedback free of synthetic hallucinations or bot artifacts?
3. sip_relevance (1-5): Is the conversation directly pertinent to SIPs, mutual fund investing, or 12-month retention?
4. pm_action_utility (1-5): Does the proposed PM action logically solve the user's friction point?

Provide your final score as a JSON object matching this schema:
{
  "test_case_id": "...",
  "scores": {
    "link_provenance_accuracy": 5,
    "content_faithfulness": 5,
    "sip_relevance": 5,
    "pm_action_utility": 5
  },
  "overall_accuracy_pct": 100.0,
  "verdict": "PASS | WARN | FAIL",
  "hallucination_detected": false,
  "critique": "Brief 1-sentence evaluation"
}
"""

def main():
    logger.info("Building LLM Evaluation Benchmark from sip_filtered_intelligence.json...")
    if not SIP_FILTERED_FILE.exists():
        logger.error("sip_filtered_intelligence.json not found!")
        return

    with open(SIP_FILTERED_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = data.get("sip_records", [])
    logger.info(f"Loaded {len(records):,} filtered SIP records.")

    # Group by source_url to give both link-level and record-level benchmark views
    url_groups = {}
    test_cases = []

    for idx, r in enumerate(records, 1):
        url = r.get("source_url") or "https://groww.in"
        source_code = r.get("source_code", "other")
        platform = (
            "Apple App Store" if source_code == "app_store" else
            "Google Play Store" if source_code == "play_store" else
            "YouTube" if source_code == "youtube" else
            "Reddit" if source_code == "reddit" else
            "TradingQ&A" if source_code == "tradingqna" else
            "Social Media" if source_code == "social_media" else
            "Premier Investing Forum"
        )

        tc_id = f"SIP_EVAL_{idx:04d}"
        clean_text = re.sub(r"^\[[^\]]+\]\s*", "", r.get("text") or "").strip()

        tc = {
            "test_case_id": tc_id,
            "post_id": r.get("post_id", f"post_{idx}"),
            "platform": platform,
            "source_code": source_code,
            "channel_or_entity": r.get("channel") or r.get("source") or platform,
            "source_url": url,
            "author": r.get("author") or "Anonymous Investor",
            "date": r.get("date") or "",
            "rating": r.get("rating"),
            "title": r.get("title") or "",
            "verbatim_retrieved_text": clean_text,
            "full_context_text": r.get("text") or "",
            "extracted_sip_category": r.get("sip_category", "fund_allocation"),
            "sip_category_name": r.get("sip_category_name", "Fund Allocation"),
            "sip_user_intent": r.get("sip_user_intent", "Inquiry"),
            "sip_friction_level": r.get("sip_friction_level", "Informational"),
            "matched_keywords": r.get("sip_matched_terms", []),
            "pm_actionable_insight": r.get("pm_actionable_insight", ""),
            "evaluation_rubric": {
                "expected_topic": r.get("sip_category_name"),
                "expected_intent": r.get("sip_user_intent"),
                "verification_link": url
            }
        }
        test_cases.append(tc)

        if url not in url_groups:
            url_groups[url] = {
                "source_url": url,
                "platform": platform,
                "source_code": source_code,
                "channel_or_entity": tc["channel_or_entity"],
                "total_items_retrieved": 0,
                "items": []
            }
        url_groups[url]["total_items_retrieved"] += 1
        url_groups[url]["items"].append({
            "test_case_id": tc_id,
            "author": tc["author"],
            "date": tc["date"],
            "rating": tc["rating"],
            "title": tc["title"],
            "text": clean_text[:200] + ("..." if len(clean_text) > 200 else ""),
            "category": tc["sip_category_name"],
            "friction": tc["sip_friction_level"],
            "pm_insight": tc["pm_actionable_insight"]
        })

    benchmark_dataset = {
        "benchmark_name": "Groww SIP Intelligence LLM Grounding & Accuracy Benchmark",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_test_cases": len(test_cases),
        "total_unique_links": len(url_groups),
        "platform_breakdown": {
            "youtube": len([tc for tc in test_cases if tc["source_code"] == "youtube"]),
            "reddit": len([tc for tc in test_cases if tc["source_code"] == "reddit"]),
            "tradingqna": len([tc for tc in test_cases if tc["source_code"] == "tradingqna"]),
            "app_store": len([tc for tc in test_cases if tc["source_code"] == "app_store"]),
            "play_store": len([tc for tc in test_cases if tc["source_code"] == "play_store"]),
            "social_media": len([tc for tc in test_cases if tc["source_code"] == "social_media"]),
            "other_public": len([tc for tc in test_cases if tc["source_code"] == "other_public"]),
        },
        "evaluation_instructions": {
            "purpose": "Test and rank retrieval accuracy, source link attribution, and SIP classification using an external LLM.",
            "recommended_models": ["GPT-4o", "Claude 3.5 Sonnet", "Gemini 1.5 Pro", "DeepSeek-V3"],
            "scoring_scale": "1 (Poor/Hallucinated) to 5 (Perfect Grounding & High Accuracy)",
            "system_prompt": LLM_EVAL_SYSTEM_PROMPT
        },
        "links_summary": list(url_groups.values()),
        "test_cases": test_cases
    }

    with open(BENCHMARK_FILE, "w", encoding="utf-8") as f:
        json.dump(benchmark_dataset, f, ensure_ascii=False, indent=2)

    logger.info(f"Successfully wrote {len(test_cases):,} benchmark test cases across {len(url_groups):,} unique URLs to {BENCHMARK_FILE}")
    return benchmark_dataset

if __name__ == "__main__":
    main()
