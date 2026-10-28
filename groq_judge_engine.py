"""
Groq LLM-as-a-Judge Evaluation Engine for Groww SIP Intelligence
High-speed, high-accuracy rubric evaluation powered by Groq LPU Inference.
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

logger = logging.getLogger("groq_judge")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

RESULTS_FILE = DATA_DIR / "groq_judge_results.json"
BENCHMARK_FILE = DATA_DIR / "llm_evaluation_benchmark.json"

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

CANDIDATE_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]


def call_groq_chat(messages, model=None, temperature=0.1):
    """Call Groq Chat Completions API with rate limit backoff and fallback."""
    key = os.getenv("GROQ_API_KEY", GROQ_API_KEY).strip()
    if not key:
        raise ValueError("GROQ_API_KEY is not configured in .env or environment")

    models_to_try = [model] if model else [GROQ_MODEL] + [m for m in CANDIDATE_MODELS if m != GROQ_MODEL]

    last_error = None
    for target_model in models_to_try:
        # Retry loop for rate limits
        for attempt in range(3):
            payload = {
                "model": target_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 500,
                "response_format": {"type": "json_object"},
            }

            req = urllib.request.Request(
                GROQ_API_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "User-Agent": "GrowwSIPDiscoveryEngine/GroqJudge/2.0",
                },
            )

            try:
                with urllib.request.urlopen(req, timeout=25) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
                    content = res_data["choices"][0]["message"]["content"]
                    parsed = clean_json_response(content)
                    parsed["actual_model_used"] = target_model
                    return parsed
            except urllib.error.HTTPError as he:
                last_error = he
                err_msg = ""
                try:
                    err_msg = he.read().decode("utf-8")
                except Exception:
                    pass

                if he.code == 429:
                    wait_sec = 6.0
                    for h, v in he.headers.items():
                        if "reset-tokens" in h.lower():
                            try:
                                wait_sec = float(v.replace("s", "").strip()) + 1.0
                            except Exception:
                                pass
                        elif "retry-after" in h.lower():
                            try:
                                wait_sec = float(v.strip()) + 0.5
                            except Exception:
                                pass
                    logger.info(f"Groq token rate limit reached. Backing off for {wait_sec:.1f}s (attempt {attempt+1}/3)...")
                    time.sleep(wait_sec)
                    continue
                else:
                    logger.warning(f"Groq model '{target_model}' HTTP {he.code}: {err_msg[:120]}")
                    break
            except Exception as exc:
                last_error = exc
                logger.warning(f"Groq model '{target_model}' error: {exc}")
                break

    raise last_error or RuntimeError("All Groq candidate models failed.")


RUBRIC_SYSTEM_PROMPT = """You are a Principal FinTech Product Evaluation Judge and Data Quality Gatekeeper for Groww Systematic Investment Plans (SIP) in India.
Your mission is to evaluate retrieved customer conversations, reviews, and forum threads with MAXIMUM RIGOR, accuracy, and engineering traceability.

Evaluate the record against 4 quantitative rubrics (1 to 5 Stars):

1. link_attribution_score (1 to 5, Weight 25%):
   - 5: Source URL is a fully verifiable public link (YouTube video/comment thread, Reddit post permalink, Apple App Store, Google Play Store, or TradingQ&A thread). Platform & channel attribution is accurate.
   - 4: Source URL is valid and reachable, platform matches, minor anchor variance.
   - 3: URL exists but specific comment ID is generic or ambiguous.
   - 2: Platform claimed does not match the URL domain.
   - 1: URL is fabricated, broken, or completely mismatched.

2. verbatim_authenticity_score (1 to 5, Weight 30%):
   - 5: Authentic, unedited retail investor voice expressing genuine friction (e.g. UPI Auto-Pay mandate failure, ICICI/HDFC bank mandate sync, salary day auto-debit delay, NAV cut-off delay, CAMS/KFintech KYC rejection, market crash panic).
   - 4: Natural human phrasing with minor truncation or typo correction.
   - 3: Broad or generic investor query, moderate authenticity.
   - 2: Heavily paraphrased or marketing-like phrasing.
   - 1: Synthetic bot hallucination, boilerplate text, or non-user content.

3. category_accuracy_score (1 to 5, Weight 25%):
   - 5: Assigned SIP Category Vector precisely matches the user's primary friction:
     [Auto-Pay & Mandates | Pause / Skip / Cancel | Market Dips & Panic | Step-Up & Top-Up | First-Time & KYC | Demat vs AMC Folios | Fund Allocation & Overlap | Taxation & ELSS]
   - 4: Strong match to primary intent, with minor secondary topic overlap.
   - 3: Generic mutual fund topic misclassified into a specific friction bucket.
   - 2: Loose relationship to investing but incorrect SIP categorization.
   - 1: Completely unrelated to SIP or mutual funds.

4. pm_actionability_score (1 to 5, Weight 20%):
   - 5: The proposed PM recommendation is technically precise, tackles root-cause churn, and provides a clear product/engineering roadmap item for Groww PMs (e.g. NPCI mandate webhook fallback, salary-day auto-adjust, proactive NAV cut-off warnings).
   - 4: Strong, actionable PM recommendation with clear customer value.
   - 3: Standard generic product suggestion (e.g. 'improve FAQ or support').
   - 2: Impractical or overly broad advice.
   - 1: Irrelevant or counterproductive suggestion.

### Composite Score Formula:
composite_score = (0.25 * link_attribution_score) + (0.30 * verbatim_authenticity_score) + (0.25 * category_accuracy_score) + (0.20 * pm_actionability_score)

### Strict Verdict Gate:
- PASS: composite_score >= 4.0 AND no individual rubric score < 3.
- BORDERLINE: 3.0 <= composite_score < 4.0.
- FAIL: composite_score < 3.0 OR any rubric score == 1.

You MUST respond strictly with valid JSON conforming to this exact schema:
{
  "link_attribution_score": <int 1-5>,
  "verbatim_authenticity_score": <int 1-5>,
  "category_accuracy_score": <int 1-5>,
  "pm_actionability_score": <int 1-5>,
  "composite_score": <float 1.0-5.0 rounded to 2 decimals>,
  "verdict": "<PASS | BORDERLINE | FAIL>",
  "detailed_critique": "<2-3 sentence rigorous evaluation explaining strengths, data authenticity, and actionable PM value>",
  "retrieval_grounding_verified": <true | false>,
  "key_findings": ["<bullet 1>", "<bullet 2>"]
}
"""


def clean_json_response(raw_text):
    """Clean model output into strict JSON dictionary."""
    text = raw_text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    return json.loads(text)



def load_cached_results():
    """Load existing Groq judge evaluations."""
    if RESULTS_FILE.exists():
        try:
            with open(RESULTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error reading {RESULTS_FILE}: {e}")
    return {"evaluations": {}, "summary": {}}


def save_cached_results(data):
    """Save Groq judge evaluations to JSON."""
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def judge_single_case(test_case, force=False):
    """Judge a single test case using Groq AI as judge."""
    case_id = test_case.get("test_case_id")
    cached = load_cached_results()

    if not force and case_id in cached.get("evaluations", {}):
        return cached["evaluations"][case_id]

    user_prompt = f"""Evaluate this retrieved SIP customer intelligence record:

Test Case ID: {test_case.get('test_case_id')}
Source Platform: {test_case.get('platform')} ({test_case.get('source_code')})
Channel / Entity: {test_case.get('channel_or_entity', 'N/A')}
Source URL: {test_case.get('source_url', 'Direct Ingestion API')}
Author: {test_case.get('author', 'Anonymous Investor')}
Date: {test_case.get('date', 'Recent')}
Rating / Engagement: {test_case.get('rating', 'N/A')}
Title / Subject: {test_case.get('title', '')}

Verbatim Retrieved Content:
"{test_case.get('verbatim_retrieved_text', '')}"

Assigned SIP Category Vector: {test_case.get('sip_category_name')} ({test_case.get('extracted_sip_category')})
SIP Friction Level: {test_case.get('sip_friction_level', 'MEDIUM')}
SIP User Intent: {test_case.get('sip_user_intent', 'N/A')}
Matched Terms: {', '.join(test_case.get('matched_keywords', []))}

Proposed PM Actionable Recommendation:
"{test_case.get('pm_actionable_insight', 'N/A')}"

Provide your rubric evaluation scores (1-5), composite score, strict verdict gate, and detailed critique in the required JSON format.
"""

    messages = [
        {"role": "system", "content": RUBRIC_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        start_t = time.time()
        evaluation = call_groq_chat(messages)
        elapsed = round(time.time() - start_t, 2)

        link_score = int(evaluation.get("link_attribution_score", 4))
        verb_score = int(evaluation.get("verbatim_authenticity_score", 4))
        cat_score = int(evaluation.get("category_accuracy_score", 4))
        pm_score = int(evaluation.get("pm_actionability_score", 4))

        composite = round(
            (0.25 * link_score) + (0.30 * verb_score) + (0.25 * cat_score) + (0.20 * pm_score), 2
        )

        verdict = evaluation.get("verdict", "PASS").upper()
        if composite >= 4.0 and min(link_score, verb_score, cat_score, pm_score) >= 3:
            verdict = "PASS"
        elif composite < 3.0 or min(link_score, verb_score, cat_score, pm_score) == 1:
            verdict = "FAIL"
        else:
            verdict = "BORDERLINE"

        model_used = evaluation.get("actual_model_used", GROQ_MODEL)

        record = {
            "test_case_id": case_id,
            "judged_by_model": f"Groq/{model_used}",
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
                "link_attribution": link_score,
                "verbatim_authenticity": verb_score,
                "category_accuracy": cat_score,
                "pm_actionability": pm_score,
                "composite_score": composite,
            },
            "verdict": verdict,
            "detailed_critique": evaluation.get("detailed_critique", ""),
            "retrieval_grounding_verified": evaluation.get("retrieval_grounding_verified", True),
            "key_findings": evaluation.get("key_findings", []),
        }

        cached["evaluations"][case_id] = record
        update_summary_stats(cached)
        save_cached_results(cached)
        return record

    except Exception as exc:
        logger.error(f"Groq evaluation failed for {case_id}: {exc}")
        raise exc


def update_summary_stats(cached):
    """Recompute summary statistics across all evaluated cases."""
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
        "judge_model": f"Groq/{GROQ_MODEL}",
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

    logger.info(f"Judging {len(target_cases)} cases with Groq AI ({GROQ_MODEL})...")
    for tc in target_cases:
        try:
            res = judge_single_case(tc, force=force)
            results.append(res)
            time.sleep(1.2)  # Pacing to stay well under token rate limits
        except Exception as e:
            logger.warning(f"Error on {tc.get('test_case_id')}: {e}")

    return {
        "judged_in_this_batch": len(results),
        "results": results,
        "summary": cached.get("summary", {}),
    }


def seed_initial_groq_evaluations(target_count=20):
    """Pre-evaluate a diverse cross-platform sample using Groq AI."""
    cached = load_cached_results()
    if len(cached.get("evaluations", {})) >= target_count:
        logger.info(f"Already have {len(cached.get('evaluations'))} cached Groq evaluations.")
        return cached

    if not BENCHMARK_FILE.exists():
        from build_llm_benchmark import main as build_bm
        build_bm()

    with open(BENCHMARK_FILE, "r", encoding="utf-8") as f:
        bm = json.load(f)

    all_cases = bm.get("test_cases", [])
    diverse = []
    platforms = ["youtube", "reddit", "play_store", "app_store", "tradingqna", "social_media"]
    for p in platforms:
        p_cases = [c for c in all_cases if c.get("source_code") == p]
        diverse.extend(p_cases[:4])

    for tc in diverse[:target_count]:
        try:
            judge_single_case(tc, force=False)
            time.sleep(1.2)
        except Exception as e:
            logger.warning(f"Failed to seed Groq case {tc.get('test_case_id')}: {e}")

    return load_cached_results()


if __name__ == "__main__":
    print("Testing Groq Judge Engine...")
    res = seed_initial_groq_evaluations(target_count=10)
    print("Groq Evaluations Count:", len(res.get("evaluations", {})))
    print("Summary:", json.dumps(res.get("summary"), indent=2))
