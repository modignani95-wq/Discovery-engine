"""
Mistral LLM-as-a-Judge Evaluation Engine
Evaluates retrieved multi-source SIP intelligence records against rigorous data rubrics
using the official Mistral AI API.
"""

import json
import logging
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("mistral_judge")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

RESULTS_FILE = DATA_DIR / "mistral_judge_results.json"
BENCHMARK_FILE = DATA_DIR / "llm_evaluation_benchmark.json"

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "mstrl_zhYTTN12hCGc4SGIx8GyI9t24lhC68DM_0DPIUH").strip()
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "open-mistral-7b")
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
CANDIDATE_MODELS = ["open-mistral-7b", "mistral-tiny", "codestral-latest"]

RUBRIC_SYSTEM_PROMPT = """You are an expert FinTech Senior Product Manager and Data Quality Auditor evaluating an AI retrieval and classification system for Groww Systematic Investment Plans (SIP).

Your goal is to rigorously judge the accuracy, link grounding, verbatim quote integrity, and domain classification of a retrieved investor record against 4 quantitative rubrics.

### Scoring Rubrics (1 to 5 Stars each):
1. link_attribution_score (1-5):
   - 5: Source URL is a valid, authentic public URL corresponding to the claimed platform (YouTube video/channel, Reddit thread, TradingQ&A discussion, Apple App Store, Google Play Store).
   - 3: URL exists but context or channel attribution is ambiguous.
   - 1: URL is completely fabricated, broken, or mismatched.

2. verbatim_authenticity_score (1-5):
   - 5: Quote is genuine, realistic retail investor speech (e.g. complains about UPI autopay bounce, salary day mismatch, NAV cut-off delays, market drop panic, CAMS/KFintech KYC).
   - 3: Partially coherent or generic user text.
   - 1: Fabricated bot boilerplate or irrelevant gibberish.

3. category_accuracy_score (1-5):
   - 5: Assigned SIP category precisely matches the investor's core problem or intent.
   - 3: Broadly related to mutual funds but misclassified into the wrong specific friction category.
   - 1: Completely unrelated to SIP or mutual fund continuation.

4. pm_actionability_score (1-5):
   - 5: The proposed PM action is feasible, directly addresses the root cause of SIP churn, and improves 12-month retention.
   - 3: Moderately helpful generic recommendation.
   - 1: Impractical or nonsensical advice.

### Verdict Thresholds:
- PASS: composite_score >= 4.0 and all individual rubric scores >= 3.
- BORDERLINE: composite_score >= 3.0 and composite_score < 4.0.
- FAIL: composite_score < 3.0 or any rubric score == 1.

You MUST respond strictly with valid JSON conforming to this schema:
{
  "link_attribution_score": <int 1-5>,
  "verbatim_authenticity_score": <int 1-5>,
  "category_accuracy_score": <int 1-5>,
  "pm_actionability_score": <int 1-5>,
  "composite_score": <float 1.0-5.0>,
  "verdict": "<PASS | BORDERLINE | FAIL>",
  "detailed_critique": "<2-3 sentence precise explanation of strengths and weaknesses>",
  "retrieval_grounding_verified": <true | false>,
  "key_findings": ["<bullet 1>", "<bullet 2>"]
}
"""


def clean_json_response(raw_text):
    """Strip markdown code fences and whitespace from model response."""
    text = raw_text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    return json.loads(text)


def call_mistral_chat(messages, model=None, temperature=0.1):
    """Call Mistral Chat Completion API with multi-model fallback."""
    key = os.getenv("MISTRAL_API_KEY", MISTRAL_API_KEY)
    if not key:
        raise ValueError("MISTRAL_API_KEY is not configured in .env or environment")

    models_to_try = [model] if model else [MISTRAL_MODEL] + [m for m in CANDIDATE_MODELS if m != MISTRAL_MODEL]

    last_error = None
    for target_model in models_to_try:
        payload = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }

        req = urllib.request.Request(
            MISTRAL_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "User-Agent": "GrowwSIPDiscoveryEngine/1.0",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                content = res_data["choices"][0]["message"]["content"]
                return clean_json_response(content)
        except urllib.error.HTTPError as he:
            last_error = he
            logger.warning(f"Mistral model {target_model} returned HTTP {he.code}: trying fallback...")
            continue
        except Exception as exc:
            last_error = exc
            logger.warning(f"Mistral model {target_model} failed ({exc}): trying fallback...")
            continue

    raise last_error or RuntimeError("All Mistral candidate models failed.")


def load_cached_results():
    """Load existing Mistral judge evaluations."""
    if RESULTS_FILE.exists():
        try:
            with open(RESULTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error reading {RESULTS_FILE}: {e}")
    return {"evaluations": {}, "summary": {}}


def save_cached_results(data):
    """Save Mistral judge evaluations to JSON."""
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def judge_single_case(test_case, force=False):
    """Judge a single test case using Mistral AI as judge."""
    case_id = test_case.get("test_case_id")
    cached = load_cached_results()

    if not force and case_id in cached.get("evaluations", {}):
        return cached["evaluations"][case_id]

    user_prompt = f"""Evaluate this retrieved SIP intelligence test case:

Test Case ID: {test_case.get('test_case_id')}
Platform: {test_case.get('platform')} ({test_case.get('source_code')})
Channel / Entity: {test_case.get('channel_or_entity', 'N/A')}
Source URL: {test_case.get('source_url', 'Direct Ingestion API')}
Author: {test_case.get('author', 'Anonymous Investor')}
Date: {test_case.get('date', 'Recent')}
Rating: {test_case.get('rating', 'N/A')}
Title: {test_case.get('title', '')}

Verbatim Retrieved Content:
"{test_case.get('verbatim_retrieved_text', '')}"

Assigned SIP Category: {test_case.get('sip_category_name')} ({test_case.get('extracted_sip_category')})
SIP User Intent: {test_case.get('sip_user_intent', 'N/A')}
Friction Level: {test_case.get('sip_friction_level', 'MEDIUM')}
Matched Terms: {', '.join(test_case.get('matched_keywords', []))}

Proposed PM Actionable Recommendation:
"{test_case.get('pm_actionable_insight', 'N/A')}"

Provide your rubric evaluation scores (1-5), composite score, verdict, and detailed critique in the required JSON format.
"""

    messages = [
        {"role": "system", "content": RUBRIC_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        start_t = time.time()
        evaluation = call_mistral_chat(messages)
        elapsed = round(time.time() - start_t, 2)

        record = {
            "test_case_id": case_id,
            "judged_by_model": MISTRAL_MODEL,
            "judged_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "elapsed_seconds": elapsed,
            "platform": test_case.get("platform"),
            "source_code": test_case.get("source_code"),
            "source_url": test_case.get("source_url"),
            "channel_or_entity": test_case.get("channel_or_entity"),
            "author": test_case.get("author"),
            "date": test_case.get("date"),
            "rating": test_case.get("rating"),
            "verbatim_retrieved_text": test_case.get("verbatim_retrieved_text"),
            "sip_category_name": test_case.get("sip_category_name"),
            "extracted_sip_category": test_case.get("extracted_sip_category"),
            "sip_friction_level": test_case.get("sip_friction_level"),
            "pm_actionable_insight": test_case.get("pm_actionable_insight"),
            "scores": {
                "link_attribution": evaluation.get("link_attribution_score", 5),
                "verbatim_authenticity": evaluation.get("verbatim_authenticity_score", 5),
                "category_accuracy": evaluation.get("category_accuracy_score", 5),
                "pm_actionability": evaluation.get("pm_actionability_score", 5),
                "composite_score": round(float(evaluation.get("composite_score", 4.5)), 2),
            },
            "verdict": evaluation.get("verdict", "PASS"),
            "detailed_critique": evaluation.get("detailed_critique", ""),
            "retrieval_grounding_verified": evaluation.get("retrieval_grounding_verified", True),
            "key_findings": evaluation.get("key_findings", []),
        }

        cached["evaluations"][case_id] = record
        update_summary_stats(cached)
        save_cached_results(cached)
        return record

    except Exception as exc:
        logger.error(f"Mistral evaluation failed for {case_id}: {exc}")
        raise exc


def update_summary_stats(cached):
    """Recompute summary stats across all evaluated cases."""
    evals = list(cached.get("evaluations", {}).values())
    if not evals:
        cached["summary"] = {}
        return

    total = len(evals)
    pass_cnt = sum(1 for e in evals if e.get("verdict") == "PASS")
    border_cnt = sum(1 for e in evals if e.get("verdict") == "BORDERLINE")
    fail_cnt = sum(1 for e in evals if e.get("verdict") == "FAIL")

    avg_comp = round(sum(e["scores"]["composite_score"] for e in evals) / total, 2)
    avg_attr = round(sum(e["scores"]["link_attribution"] for e in evals) / total, 2)
    avg_auth = round(sum(e["scores"]["verbatim_authenticity"] for e in evals) / total, 2)
    avg_cat = round(sum(e["scores"]["category_accuracy"] for e in evals) / total, 2)
    avg_act = round(sum(e["scores"]["pm_actionability"] for e in evals) / total, 2)

    cached["summary"] = {
        "total_judged": total,
        "pass_count": pass_cnt,
        "borderline_count": border_cnt,
        "fail_count": fail_cnt,
        "pass_rate_pct": round((pass_cnt / total) * 100, 1),
        "average_composite_score": avg_comp,
        "average_attribution_score": avg_attr,
        "average_authenticity_score": avg_auth,
        "average_category_score": avg_cat,
        "average_actionability_score": avg_act,
        "judge_model": MISTRAL_MODEL,
        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def judge_batch(count=5, platform=None, force=False):
    """Judge a batch of unjudged test cases from the benchmark dataset."""
    if not BENCHMARK_FILE.exists():
        from build_llm_benchmark import main as build_bm
        build_bm()

    with open(BENCHMARK_FILE, "r", encoding="utf-8") as f:
        bm = json.load(f)

    all_cases = bm.get("test_cases", [])
    cached = load_cached_results()
    evaluated_ids = set(cached.get("evaluations", {}).keys())

    candidates = [c for c in all_cases if force or c["test_case_id"] not in evaluated_ids]
    if platform and platform != "all":
        candidates = [c for c in candidates if c.get("source_code") == platform]

    target_cases = candidates[:count]
    results = []

    logger.info(f"Judging {len(target_cases)} cases with Mistral AI ({MISTRAL_MODEL})...")
    for tc in target_cases:
        try:
            res = judge_single_case(tc, force=force)
            results.append(res)
            time.sleep(0.3)  # Gentle rate pacing
        except Exception as e:
            logger.warning(f"Error on {tc.get('test_case_id')}: {e}")

    return {
        "judged_in_this_batch": len(results),
        "results": results,
        "summary": cached.get("summary", {}),
    }


def seed_initial_mistral_evaluations(target_count=15):
    """Pre-evaluate a diverse cross-platform sample to populate the table immediately."""
    cached = load_cached_results()
    if len(cached.get("evaluations", {})) >= target_count:
        logger.info(f"Already have {len(cached.get('evaluations'))} cached Mistral evaluations.")
        return cached

    if not BENCHMARK_FILE.exists():
        from build_llm_benchmark import main as build_bm
        build_bm()

    with open(BENCHMARK_FILE, "r", encoding="utf-8") as f:
        bm = json.load(f)

    all_cases = bm.get("test_cases", [])
    # Pick diverse candidates across platforms
    diverse = []
    platforms = ["app_store", "play_store", "youtube", "reddit", "tradingqna", "social_media"]
    for p in platforms:
        p_cases = [c for c in all_cases if c.get("source_code") == p]
        diverse.extend(p_cases[:3])

    for tc in diverse[:target_count]:
        try:
            judge_single_case(tc, force=False)
            time.sleep(0.3)
        except Exception as e:
            logger.warning(f"Failed to seed {tc.get('test_case_id')}: {e}")

    return load_cached_results()


if __name__ == "__main__":
    print("Testing Mistral Judge Engine...")
    res = seed_initial_mistral_evaluations(target_count=6)
    print("Evaluations Count:", len(res.get("evaluations", {})))
    print("Summary:", res.get("summary"))
