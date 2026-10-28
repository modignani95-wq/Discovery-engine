#!/usr/bin/env python3
"""
SIP Evaluations Module (sip_evals.py)
Deterministic code-based checks + evaluation helpers for the SIP Discovery Engine.
Inspired by the DeepEval evaluation framework described in the spec.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

# --- Constants -----------------------------------------------------------------

REQUIRED_FIELDS = {"journey_stage", "problem", "trigger", "sip_outcome", "evidence_quote", "source_id"}
ALLOWED_JOURNEY_STAGES = {"starting", "continuing", "reducing", "pausing", "stopping", "unknown"}
ALLOWED_SIP_OUTCOMES   = {"continued", "reduced", "paused", "stopped", "unknown"}
ALLOWED_CONFIDENCE     = {"high", "medium", "low"}
MAX_QUOTE_LENGTH       = 300


# --- Code-Based Validation Checks (Stage 6) ------------------------------------

def validate_sip_output(output: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Deterministic schema + integrity check for a single extracted record.
    Returns (is_valid, list_of_errors).
    """
    errors = []

    if not isinstance(output, dict):
        return False, ["Output must be a dict"]

    # Required fields present
    missing = REQUIRED_FIELDS - set(output.keys())
    if missing:
        errors.append(f"Missing required fields: {missing}")

    # journey_stage valid
    js = output.get("journey_stage")
    if js and js not in ALLOWED_JOURNEY_STAGES:
        errors.append(f"Invalid journey_stage: {js!r}. Must be one of {ALLOWED_JOURNEY_STAGES}")

    # sip_outcome valid
    so = output.get("sip_outcome")
    if so and so not in ALLOWED_SIP_OUTCOMES:
        errors.append(f"Invalid sip_outcome: {so!r}. Must be one of {ALLOWED_SIP_OUTCOMES}")

    # confidence valid (optional)
    conf = output.get("confidence")
    if conf and conf not in ALLOWED_CONFIDENCE:
        errors.append(f"Invalid confidence: {conf!r}. Must be one of {ALLOWED_CONFIDENCE}")

    # evidence_quote length
    eq = output.get("evidence_quote") or ""
    if len(eq) > MAX_QUOTE_LENGTH:
        errors.append(f"evidence_quote too long ({len(eq)} chars, max {MAX_QUOTE_LENGTH})")

    # source_id present and non-empty
    sid = output.get("source_id")
    if not sid:
        errors.append("source_id must be a non-empty string")

    # Hallucination guard: sip_outcome = stopped without a problem
    if output.get("sip_outcome") == "stopped" and not output.get("problem"):
        errors.append("sip_outcome='stopped' claimed without any problem field - potential hallucination")

    return len(errors) == 0, errors


def validate_batch(outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Run validate_sip_output on a batch and return aggregate stats."""
    results = []
    for out in outputs:
        valid, errors = validate_sip_output(out)
        results.append({"valid": valid, "errors": errors, "source_id": out.get("source_id", "?")})

    total = len(results)
    passed = sum(1 for r in results if r["valid"])
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / max(total, 1) * 100, 1),
        "failures": [r for r in results if not r["valid"]][:20],
    }


# --- Golden Dataset Evaluation -------------------------------------------------

GOLDEN_DATASET = [
    {
        "input": "My salary was delayed, so my SIP payment failed. I don't know whether I need to restart it.",
        "expected": {
            "problem": "SIP payment failure",
            "trigger": "Salary delay",
            "sip_outcome": "unknown",
        },
    },
    {
        "input": "Market is down 15% and I am thinking of stopping my SIP. Too much loss already.",
        "expected": {
            "problem": "Performance & Returns Anxiety",
            "trigger": "Market downturn",
            "sip_outcome": "unknown",
        },
    },
    {
        "input": "KYC verification keeps failing. I submitted documents 3 times and my SIP never started.",
        "expected": {
            "problem": "KYC & Compliance Friction",
            "trigger": "KYC rejection",
            "sip_outcome": "unknown",
        },
    },
    {
        "input": "Great app! My SIP has been running smoothly for 2 years. Very satisfied.",
        "expected": {
            "problem": None,
            "trigger": None,
            "sip_outcome": "continued",
        },
    },
    {
        "input": "App keeps crashing whenever I try to set up a new SIP. Very frustrating.",
        "expected": {
            "problem": "App Technical Issues",
            "trigger": None,
            "sip_outcome": "unknown",
        },
    },
    {
        "input": "Customer support never responds. My SIP mandate was rejected and no one is helping me fix it.",
        "expected": {
            "problem": "Customer Support Gap",
            "trigger": "Bank mandate rejection",
            "sip_outcome": "unknown",
        },
    },
    {
        "input": "I paused my SIP because I lost my job. Will restart once I get a new one.",
        "expected": {
            "problem": "SIP payment failure",
            "trigger": None,
            "sip_outcome": "paused",
        },
    },
    {
        "input": "Redemption took 10 days! I needed the money urgently and it was stuck.",
        "expected": {
            "problem": "Redemption & Withdrawal Issues",
            "trigger": None,
            "sip_outcome": "unknown",
        },
    },
]


def run_golden_dataset_eval(
    extractions: List[Dict[str, Any]],
    golden_dataset: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Compare extracted outputs against the golden dataset using field-level matching.
    Uses soft matching (keyword overlap) since LLM outputs vary in phrasing.
    """
    dataset = golden_dataset or GOLDEN_DATASET
    matched_results = []

    # Build a lookup by source text approximation (match by shared keywords)
    ext_by_quote = {}
    for ext in extractions:
        q = (ext.get("evidence_quote") or ext.get("original_text") or "").lower()
        ext_by_quote[q[:50]] = ext

    for case in dataset:
        input_text = case["input"].lower()
        expected = case["expected"]

        # Try to find a matching extraction
        best_ext = None
        best_score = 0
        for ext in extractions:
            orig = (ext.get("original_text") or "").lower()
            # Word overlap
            words_in = set(input_text.split())
            words_orig = set(orig.split())
            overlap = len(words_in & words_orig) / max(len(words_in), 1)
            if overlap > best_score:
                best_score = overlap
                best_ext = ext

        if not best_ext or best_score < 0.2:
            matched_results.append({
                "input": case["input"][:100],
                "status": "no_match",
                "expected": expected,
                "actual": None,
                "field_scores": {},
            })
            continue

        field_scores = {}
        for field, exp_val in expected.items():
            actual_val = best_ext.get(field)
            if exp_val is None:
                field_scores[field] = "pass" if not actual_val else "warn_extra"
            elif actual_val is None:
                field_scores[field] = "fail_missing"
            else:
                # Soft keyword match
                exp_lower = str(exp_val).lower()
                act_lower = str(actual_val).lower()
                exp_words = set(exp_lower.split())
                act_words = set(act_lower.split())
                overlap = len(exp_words & act_words) / max(len(exp_words), 1)
                field_scores[field] = "pass" if overlap >= 0.4 else "fail_mismatch"

        pass_count = sum(1 for s in field_scores.values() if s in ("pass", "warn_extra"))
        total_fields = len(field_scores)
        matched_results.append({
            "input": case["input"][:100],
            "status": "matched",
            "expected": expected,
            "actual": {f: best_ext.get(f) for f in expected},
            "field_scores": field_scores,
            "field_pass_rate": round(pass_count / max(total_fields, 1) * 100, 1),
        })

    overall_pass = sum(
        r.get("field_pass_rate", 0)
        for r in matched_results if r["status"] == "matched"
    )
    matched_count = sum(1 for r in matched_results if r["status"] == "matched")

    return {
        "dataset_size": len(dataset),
        "matched": matched_count,
        "unmatched": len(dataset) - matched_count,
        "avg_field_pass_rate": round(overall_pass / max(matched_count, 1), 1),
        "case_results": matched_results,
        "disclaimer": (
            "This uses soft keyword matching against a small reference dataset. "
            "A passing score does not guarantee correctness on all future data. "
            "Human review of failures is required."
        ),
    }


# --- Relevance Precision/Recall Eval -------------------------------------------

def eval_relevance_classifier(
    predictions: List[Dict[str, Any]],
    ground_truth: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Compute precision, recall, F1 for the relevance filter stage.
    predictions and ground_truth: lists of dicts with 'post_id' and 'relevance' (relevant|irrelevant|uncertain)
    """
    gt_map = {r["post_id"]: r["relevance"] for r in ground_truth}
    tp = fp = fn = tn = 0
    for pred in predictions:
        pid = pred.get("post_id")
        p_label = "relevant" if pred.get("relevance") in ("relevant", "uncertain") else "irrelevant"
        g_label = gt_map.get(pid, "irrelevant")
        if p_label == "relevant" and g_label == "relevant":
            tp += 1
        elif p_label == "relevant" and g_label == "irrelevant":
            fp += 1
        elif p_label == "irrelevant" and g_label == "relevant":
            fn += 1
        else:
            tn += 1

    precision = round(tp / max(tp + fp, 1) * 100, 1)
    recall    = round(tp / max(tp + fn, 1) * 100, 1)
    f1 = round(2 * precision * recall / max(precision + recall, 1), 1)
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    }


# --- Evaluation Report Builder -------------------------------------------------

def build_eval_report(
    pipeline_result: Dict[str, Any],
    model_version: str = "unknown",
    prompt_version: str = "v1",
) -> Dict[str, Any]:
    """Build a structured evaluation report after a pipeline run."""
    stages = pipeline_result.get("stages", {})
    validation = pipeline_result.get("validation_report", {})
    hypothesis = pipeline_result.get("hypothesis_report", {})
    golden = validation.get("golden_eval") or {}

    return {
        "report_generated_at": pipeline_result.get("pipeline_run_at", ""),
        "model_version": model_version,
        "prompt_version": prompt_version,
        "dataset_summary": {
            "total_collected": stages.get("collect", {}).get("total_records", 0),
            "after_cleaning": stages.get("clean", {}).get("kept", 0),
            "after_filtering": stages.get("filter", {}).get("kept", 0),
            "total_extracted": stages.get("extract", {}).get("total", 0),
        },
        "relevance_filter_stats": stages.get("filter", {}).get("stats", {}),
        "extraction_validation": {
            "schema_validity_rate": validation.get("schema_validity_rate", 0),
            "evidence_grounding_rate": validation.get("evidence_grounding_rate", 0),
            "errors_sample": validation.get("errors", [])[:5],
        },
        "golden_eval_summary": {
            "dataset_size": golden.get("dataset_size", 0),
            "matched": golden.get("matched", 0),
            "avg_field_pass_rate": golden.get("avg_field_pass_rate", 0),
        } if golden else None,
        "hypothesis_summary": {
            "total_hypotheses": len(hypothesis.get("hypotheses", [])),
            "top_hypothesis": hypothesis.get("hypotheses", [{}])[0].get("label") if hypothesis.get("hypotheses") else None,
            "sip_outcome_dist": hypothesis.get("sip_outcome_distribution", {}),
        },
        "known_limitations": [
            "Frequency scores are based on a sample of public reviews, not population data.",
            "LLM extraction confidence estimates are not calibrated probabilities.",
            "Golden dataset is small (8 examples) and should be expanded.",
            "No behavioural data to validate SIP continuation claims.",
        ],
        "release_decision": "REVIEW_REQUIRED",
        "notes": "Run human review on failures before treating scores as production-ready.",
    }
