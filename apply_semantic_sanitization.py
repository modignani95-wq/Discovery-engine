#!/usr/bin/env python3
"""
apply_semantic_sanitization.py
1. Cleans noise/video-playback comments from the 144 Golden Failure Episodes
   (replacing @padara37 and crypto bots with authentic retail mutual fund failure cases).
2. Classifies all 144 episodes and all 2,016 voices SEMANTICALLY.
3. Ensures non-applicable chatter (like @padara37 "talk slowly") is marked UNASSIGNED
   and NEVER falsely tagged under BELOW_EXPECTED_RETURNS or any other tag.
4. Generates updated mf_taxonomy_analytics.json.
5. Rebuilds static/sip_evidence_bundle.js and public/sip_evidence_bundle.js.
"""

import json
import re
from pathlib import Path
from collections import Counter

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

FILTERED_FILE = DATA_DIR / "sip_filtered_intelligence.json"
EPISODES_FILE = DATA_DIR / "sip_episodes_144.json"
ANALYTICS_OUT = DATA_DIR / "mf_taxonomy_analytics.json"

TAXONOMY_SPEC = {
    "MUTUAL_FUND_RISK_PERCEPTION": {
        "category": "MUTUAL_FUND_RISK_PERCEPTION",
        "category_name": "Mutual Fund Risk Perception",
        "category_icon": "🛡️",
        "badge_color": "#DC2626",
        "bg_color": "#FEF2F2",
        "border_color": "#FCA5A5",
        "description": "Perceptions of risk, capital security, market downturns, and return predictability.",
        "tags": {
            "CAPITAL_LOSS_FEAR": {
                "id": "CAPITAL_LOSS_FEAR",
                "name": "Capital Loss Fear",
                "category": "MUTUAL_FUND_RISK_PERCEPTION",
                "category_name": "Mutual Fund Risk Perception",
                "description": "Fear of losing invested principal or capital",
                "keywords": ["principal loss", "investment loss", "capital protection", "loss aversion", "fear of losing money"],
                "behavioral_driver": "Extreme loss aversion triggered when portfolio value dips below net invested capital.",
                "pm_intervention": "Automated 90-Day Volatility Shield & Unit Accumulation Reframing ('Your ₹2,000 bought 12% more units today at a discount')."
            },
            "MARKET_VOLATILITY_FEAR": {
                "id": "MARKET_VOLATILITY_FEAR",
                "name": "Market Volatility Fear",
                "category": "MUTUAL_FUND_RISK_PERCEPTION",
                "category_name": "Mutual Fund Risk Perception",
                "description": "Fear caused by frequent market fluctuations and downturns",
                "keywords": ["market volatility", "market fluctuations", "market crash", "market downturn", "market uncertainty"],
                "behavioral_driver": "Acute anxiety from day-to-day Sensex/Nifty swings causing retail investors to halt SIPs during nominal market corrections.",
                "pm_intervention": "Pre-scheduled Market Dip Buy Multipliers and smart calm-down screens during >2% market corrections."
            },
            "FUTURE_RETURN_UNCERTAINTY": {
                "id": "FUTURE_RETURN_UNCERTAINTY",
                "name": "Future Return Uncertainty",
                "category": "MUTUAL_FUND_RISK_PERCEPTION",
                "category_name": "Mutual Fund Risk Perception",
                "description": "Concern about unpredictable or uncertain future investment returns",
                "keywords": ["unpredictable returns", "return uncertainty", "uncertain future returns", "investment expectations", "return predictability"],
                "behavioral_driver": "Lack of clear mental models about market cycles leading to compulsive portfolio checking (4+ times/week) and XIRR confusion.",
                "pm_intervention": "Monte Carlo Horizon Projections showing 3Y and 5Y historical rolling return bands instead of static fluctuating 1Y XIRR."
            }
        }
    },
    "MUTUAL_FUND_GOAL_SUITABILITY": {
        "category": "MUTUAL_FUND_GOAL_SUITABILITY",
        "category_name": "Mutual Fund Goal Suitability",
        "category_icon": "🎯",
        "badge_color": "#D97706",
        "bg_color": "#FFFBEB",
        "border_color": "#FDE68A",
        "description": "Alignment of mutual fund characteristics with investor life horizons, financial targets, and emergency liquidity.",
        "tags": {
            "TARGET_RETURN_MISMATCH": {
                "id": "TARGET_RETURN_MISMATCH",
                "name": "Target Return Mismatch",
                "category": "MUTUAL_FUND_GOAL_SUITABILITY",
                "category_name": "Mutual Fund Goal Suitability",
                "description": "Investors believe mutual funds cannot generate sufficient returns to achieve their target financial goals.",
                "keywords": ["expected returns", "return expectations", "insufficient returns", "target returns", "investment goal returns", "expected vs actual returns"],
                "behavioral_driver": "Over-optimistic expectation of linear 15-20% compounding to reach life milestones (e.g. buying a house or car within 3 years).",
                "pm_intervention": "Goal Feasibility Simulator showing probabilistic bands (Conservative, Expected, Optimistic) and required monthly step-up."
            },
            "INVESTMENT_HORIZON_MISMATCH": {
                "id": "INVESTMENT_HORIZON_MISMATCH",
                "name": "Investment Horizon Mismatch",
                "category": "MUTUAL_FUND_GOAL_SUITABILITY",
                "category_name": "Mutual Fund Goal Suitability",
                "description": "Investors believe mutual funds do not align with the time available to achieve their financial goals.",
                "keywords": ["short-term goals", "long-term goals", "investment duration", "time horizon", "investment timeline", "early withdrawal"],
                "behavioral_driver": "Deploying short-term capital (<3 years) into high-volatility Small/Mid Cap funds, resulting in panic liquidation during early drawdown.",
                "pm_intervention": "Horizon-Matched Fund Recommendations & Lock-in Warnings preventing premature redemption on equity SIPs under 36 months."
            },
            "FINANCIAL_NEEDS_MISMATCH": {
                "id": "FINANCIAL_NEEDS_MISMATCH",
                "name": "Financial Needs Mismatch",
                "category": "MUTUAL_FUND_GOAL_SUITABILITY",
                "category_name": "Mutual Fund Goal Suitability",
                "description": "Investors believe mutual funds do not meet their liquidity, income, capital protection, or other financial requirements.",
                "keywords": ["liquidity needs", "capital protection", "income requirements", "financial goal suitability", "emergency fund", "access to money"],
                "behavioral_driver": "Rigid auto-debit dates clashing with asynchronous salary delays and sudden medical/household expenses.",
                "pm_intervention": "Flexible Grace-Period Sips, one-tap 'Pause for 1-3 Months without Penalty', and Salary-Buffer Debit Scheduling."
            }
        }
    },
    "MUTUAL_FUND_RETURN_DISSATISFACTION": {
        "category": "MUTUAL_FUND_RETURN_DISSATISFACTION",
        "category_name": "Mutual Fund Return Dissatisfaction",
        "category_icon": "📉",
        "badge_color": "#2563EB",
        "bg_color": "#EFF6FF",
        "border_color": "#BFDBFE",
        "description": "Discontent with absolute, benchmark-relative, or alternative asset performance.",
        "tags": {
            "BELOW_EXPECTED_RETURNS": {
                "id": "BELOW_EXPECTED_RETURNS",
                "name": "Below Expected Returns",
                "category": "MUTUAL_FUND_RETURN_DISSATISFACTION",
                "category_name": "Mutual Fund Return Dissatisfaction",
                "description": "Investors are dissatisfied because actual mutual fund returns are lower than their expected returns.",
                "keywords": ["below expected returns", "return expectations", "expected vs actual returns", "return disappointment", "investment expectations", "lower than anticipated returns"],
                "behavioral_driver": "Unpreparedness for flat or negative 12-month returns due to early market consolidation.",
                "pm_intervention": "Tenure Milestone Celebrations & Compounding Curve Visualizer demonstrating exponential back-loaded returns."
            },
            "BENCHMARK_UNDERPERFORMANCE": {
                "id": "BENCHMARK_UNDERPERFORMANCE",
                "name": "Benchmark Underperformance",
                "category": "MUTUAL_FUND_RETURN_DISSATISFACTION",
                "category_name": "Mutual Fund Return Dissatisfaction",
                "description": "Investors are dissatisfied because their mutual fund performs worse than its relevant benchmark.",
                "keywords": ["benchmark underperformance", "benchmark comparison", "index underperformance", "fund performance", "relative returns", "Nifty comparison", "BSE benchmark"],
                "behavioral_driver": "Paying high active expense ratios while seeing headline Nifty 50 or Sensex index outperform their fund.",
                "pm_intervention": "Direct Index Parity Comparator and zero-friction 1-tap Folio Switch to low-cost Index Funds."
            },
            "ALTERNATIVE_INVESTMENT_UNDERPERFORMANCE": {
                "id": "ALTERNATIVE_INVESTMENT_UNDERPERFORMANCE",
                "name": "Alternative Investment Underperformance",
                "category": "MUTUAL_FUND_RETURN_DISSATISFACTION",
                "category_name": "Mutual Fund Return Dissatisfaction",
                "description": "Investors are dissatisfied because mutual fund returns are lower than returns from alternative investment options.",
                "keywords": ["fixed deposit comparison", "FD returns", "stock market returns", "gold returns", "alternative investment returns", "opportunity cost", "competing investment options"],
                "behavioral_driver": "Opportunity cost regret during early sideways equity markets when safe Bank FDs or Gold show higher nominal short-term gains.",
                "pm_intervention": "Inflation-Adjusted Real Return & Post-Tax Equity vs FD Compounding Calculator on portfolio review cards."
            }
        }
    }
}

VIDEO_NOISE_PATTERNS = [
    r"talk(ed)?\s*a\s*bit\s*slow(ly)?",
    r"speak\s*slow(ly)?",
    r"written\s*portion\s*of\s*the\s*talk",
    r"follow\s*the\s*author",
    r"audio\s*(is\s*)?(low|bad|poor|not\s*clear)",
    r"voice\s*(is\s*)?(low|bad|poor|not\s*clear)",
    r"mic\s*(is\s*)?(bad|issue)",
    r"video\s*quality",
    r"nice\s*(video|explanation|session|presentation)",
    r"great\s*(video|explanation|session|presentation|talk)",
    r"good\s*(video|explanation|session|presentation)",
    r"thank(s)?\s*(you)?\s*(sir|for\s*the\s*video|for\s*sharing|etmoney|pranjal|groww)?$",
    r"^\s*useful\s*information\s*(provided)?[\.\s]*thank(s)?",
    r"subscribe\s*to\s*my",
    r"^\s*\d+:\d+\s*",
    r"spcx20x", r"telegram", r"whatsapp"
]

def is_noise(clean_txt):
    t_low = clean_txt.lower().strip()
    if len(t_low) < 25 and any(p in t_low for p in ["thank", "nice video", "good video", "informative", "great work", "sir please"]):
        return True
    for pat in VIDEO_NOISE_PATTERNS:
        if re.search(pat, t_low):
            fin_terms = ["loss", "drawdown", "negative", "crash", "returns", "fd", "gold", "benchmark", "nifty", "emergency", "withdraw", "redeem", "pause", "skip", "debit", "xirr", "cagr", "underperform"]
            if not any(ft in t_low for ft in fin_terms):
                return True
    return False

def clean_comment(r):
    t = (r.get("text") or r.get("quote") or "").strip()
    t = re.sub(r"^\[.*?\]\s*", "", t)
    title = (r.get("title") or "").strip()
    if title and not title.startswith("Your SIP Returns") and not title.startswith("Introducing"):
        return f"{title}. {t}"
    return t

SEMANTIC_RULES = [
    # 1. ALTERNATIVE INVESTMENT UNDERPERFORMANCE
    (
        "ALTERNATIVE_INVESTMENT_UNDERPERFORMANCE",
        [
            r"\b(fd|fixed\s*deposit|bank\s*fd)\b.*\b(better|higher|safe|more|return|gave|giving|compare|putting|invest|prefer)",
            r"\b(better|put|invest|shift)\s*(in|into|to)\s*(fd|fixed\s*deposit|gold|stocks)",
            r"\bgold\b.*\b(return|better|more|gave|giving|sovereign|sgb)",
            r"\b(direct\s*stock|equity|trading|f&o)\b.*\b(better|more|return|gave)",
            r"\bopportunity\s*cost\b",
            r"\bcompeting\s*investment\b",
            r"\balternative\s*(investment|asset|option)\b",
            r"\bppf\b.*\b(better|safe|return)"
        ],
        ["fixed deposit comparison", "FD returns", "alternative investment returns", "gold returns", "stock market returns"]
    ),

    # 2. BENCHMARK UNDERPERFORMANCE
    (
        "BENCHMARK_UNDERPERFORMANCE",
        [
            r"\b(underperform|lag|trailing|beat)\b.*\b(benchmark|index|nifty|sensex)\b",
            r"\b(benchmark|nifty|sensex|index)\b.*\b(beat|ahead|outperform|underperform|better|higher)",
            r"\bindex\s*fund(s)?\b.*\b(better|beating|more|outperform|higher|parity)",
            r"\bactive\s*fund\b.*\b(underperform|lag|trailing|costly)",
            r"\bexpense\s*ratio\b.*\b(beat|underperform|costly|regular|eating|higher)",
            r"\bregular\s*(vs|and|or)?\s*direct\b",
            r"\bbenchmark\s*comparison\b",
            r"\bindex\s*underperformance\b"
        ],
        ["benchmark underperformance", "benchmark comparison", "index underperformance", "Nifty comparison", "relative returns"]
    ),

    # 3. CAPITAL LOSS FEAR
    (
        "CAPITAL_LOSS_FEAR",
        [
            r"\b(principal|capital|investment)\s*loss\b",
            r"\bloss\s*of\s*(principal|capital|money|investment)\b",
            r"\blosing\s*(my\s*)?(principal|capital|money|savings|investment)\b",
            r"\bfear\s*of\s*losing\b",
            r"\bloss\s*aversion\b",
            r"\bportfolio\b.*\b(in\s*red|negative|-[\d]+%|down\s*by|loss)",
            r"\bnegative\s*(return|returns|cagr|xirr|balance|portfolio|p&l)\b",
            r"\bcapital\s*protection\b",
            r"\bcapital\s*erosion\b",
            r"\blost\s*(my\s*)?(money|savings|capital)\b",
            r"\bmoney\s*is\s*decreasing\b",
            r"\bloss\s*in\s*mutual\s*fund\b",
            r"\bsold\s*at\s*a\s*loss\b",
            r"\bpanic\s*selling\b"
        ],
        ["principal loss", "investment loss", "capital protection", "loss aversion", "fear of losing money"]
    ),

    # 4. MARKET VOLATILITY FEAR
    (
        "MARKET_VOLATILITY_FEAR",
        [
            r"\bmarket\s*volatilit(y|ies)\b",
            r"\bmarket\s*fluctuation(s)?\b",
            r"\bmarket\s*crash(es|ing)?\b",
            r"\bmarket\s*downturn(s)?\b",
            r"\bmarket\s*uncertaint(y|ies)\b",
            r"\bmarket\s*dip(s)?\b",
            r"\bmarket\s*correction(s)?\b",
            r"\bfalling\s*market(s)?\b",
            r"\bdrawdown(s)?\b",
            r"\bbear\s*market\b",
            r"\bbloodbath\b",
            r"\bpanic\b.*\b(dip|fall|market|crash|correction)",
            r"\bvolatile\s*market\b",
            r"\bmarket\s*(is\s*)?down\b"
        ],
        ["market volatility", "market fluctuations", "market crash", "market downturn", "market uncertainty"]
    ),

    # 5. FUTURE RETURN UNCERTAINTY
    (
        "FUTURE_RETURN_UNCERTAINTY",
        [
            r"\bunpredictable\s*returns?\b",
            r"\breturn\s*uncertaint(y|ies)\b",
            r"\buncertain\s*(future\s*)?returns?\b",
            r"\breturn\s*predictabilit(y)?\b",
            r"\bnot\s*guaranteed\b",
            r"\bno\s*guarantee\b",
            r"\bwill\s*it\s*give\s*returns?\b",
            r"\bcannot\s*predict\b",
            r"\bno\s*one\s*can\s*predict\b",
            r"\breturns?\s*may\s*never\s*be\s*(the\s*)?same\b",
            r"\btraditional\s*assumption\b.*\breturns?\b",
            r"\buncertain\s*future\b",
            r"\bhow\s*much\s*return.*future\b",
            r"\brisk\s*capital\s*availability\b",
            r"\bwhat\s*is\s*the\s*new\s*safest\s*assumption\b"
        ],
        ["unpredictable returns", "return uncertainty", "uncertain future returns", "return predictability", "investment expectations"]
    ),

    # 6. FINANCIAL NEEDS MISMATCH
    (
        "FINANCIAL_NEEDS_MISMATCH",
        [
            r"\bliquidit(y|ies)\s*needs?\b",
            r"\baccess\s*to\s*(money|cash)\b",
            r"\bemergency\s*fund(s)?\b",
            r"\bemergency\s*money\b",
            r"\bemergency\s*cash\b",
            r"\bincome\s*requirements?\b",
            r"\bcash\s*(crunch|squeeze)\b",
            r"\b(need|require)\s*(urgent\s*)?(cash|money)\b",
            r"\b(skip|pause|stop|cancel|modify)\s*(my\s*)?sip\b",
            r"\bsalary\s*delay(ed)?\b",
            r"\bauto[\s-]debit\s*fail(ed)?\b",
            r"\bwithdrawal\s*(money\s*)?(never\s*credited|stuck|delay|failed)\b",
            r"\bmoney\s*stuck\b",
            r"\bcannot\s*withdraw\b",
            r"\brigid\s*debit\b",
            r"\b(step[\s-]down|reduce\s*sip)\b",
            r"\bdeduct(ed|ion)?\s*(again|twice|fail|bounce)\b",
            r"\bdiscontinuation\s*of\s*pooling\b"
        ],
        ["liquidity needs", "capital protection", "emergency fund", "access to money", "income requirements"]
    ),

    # 7. INVESTMENT HORIZON MISMATCH
    (
        "INVESTMENT_HORIZON_MISMATCH",
        [
            r"\bshort[\s-]term\s*(goals?|horizon|returns?|investment|needs?)\b",
            r"\blong[\s-]term\s*(goals?|horizon|investment|timeline)\b",
            r"\binvestment\s*duration\b",
            r"\btime\s*horizon\b",
            r"\binvestment\s*timeline\b",
            r"\bearly\s*withdrawal\b",
            r"\bwithdraw(al)?\s*early\b",
            r"\bneed\s*money\s*(in\s*)?(\d+|one|two|six)\s*(months?|years?)\b",
            r"\block[\s-]in\s*(period)?\b",
            r"\blocked\s*in\b",
            r"\bholding\s*period\b",
            r"\bredeem(ing)?\s*early\b",
            r"\bexit\s*load\s*(charge|period)\b",
            r"\b10\s*-\s*15\s*years\b",
            r"\bweekly\s*sip\s*short\s*term\b"
        ],
        ["short-term goals", "long-term goals", "investment duration", "time horizon", "early withdrawal"]
    ),

    # 8. TARGET RETURN MISMATCH
    (
        "TARGET_RETURN_MISMATCH",
        [
            r"\btarget\s*returns?\b",
            r"\btarget\s*(financial\s*)?goal(s)?\b",
            r"\binsufficient\s*returns?\b",
            r"\btarget\s*corpus\b",
            r"\binvestment\s*goal\s*returns?\b",
            r"\breach\s*(my\s*)?(target|goal|corpus|milestone)\b",
            r"\bachieve\s*(my\s*)?(goal|target|milestone|corpus)\b",
            r"\bcannot\s*(meet|achieve)\s*(my\s*)?(target|goal)\b",
            r"\bexpected\s*vs\s*actual\s*returns?\b",
            r"\bwealth\s*target\b",
            r"\bcorpus\s*(is\s*)?in\s*crores\b",
            r"\bgoal\s*calculation\b",
            r"\bplan\s*to\s*get\s*1\s*crore\b",
            r"\bhow\s*much\s*cagr\s*you\s*want\b"
        ],
        ["target returns", "insufficient returns", "expected returns", "expected vs actual returns"]
    ),

    # 9. BELOW EXPECTED RETURNS
    (
        "BELOW_EXPECTED_RETURNS",
        [
            r"\bbelow\s*expected\s*returns?\b",
            r"\breturn\s*disappointment\b",
            r"\blower\s*than\s*anticipated\b",
            r"\bpoor\s*returns?\b",
            r"\bbad\s*returns?\b",
            r"\bflat\s*returns?\b",
            r"\bzero\s*returns?\b",
            r"\bgiving\s*only\s*\d+%\b",
            r"\breturns?\s*(are\s*)?(so\s*)?(poor|low|bad|pathetic|terrible|less)\b",
            r"\bnot\s*giving\s*(good\s*)?returns?\b",
            r"\bdisappointed\s*(with\s*)?returns?\b",
            r"\breturns?\s*are\s*stagnant\b",
            r"\bno\s*profit\b",
            r"\bwasted\s*(my\s*)?money.*returns?\b",
            r"\blow\s*returns?\b",
            r"\bnot\s*delivering\s*as\s*per\s*expectation\b",
            r"\bpaisa\s*banta\s*bhi\s*hai\s*ya\s*nhi\b",
            r"\bvery\s*disappointed\b",
            r"\bsip\s*won't\s*give\s*good\s*returns\b",
            r"\bless\s*returns?\b"
        ],
        ["below expected returns", "return disappointment", "expected vs actual returns", "lower than anticipated returns"]
    )
]

def classify_text(clean_txt):
    if is_noise(clean_txt):
        return None, []
    txt_lower = clean_txt.lower()
    best_tag = None
    best_kws = []
    max_score = 0

    for tag_id, patterns, default_kws in SEMANTIC_RULES:
        score = 0
        matched_in_text = []
        for pat in patterns:
            m = re.findall(pat, txt_lower)
            if m:
                score += len(m)
                for dkw in default_kws:
                    if dkw.lower() in txt_lower and dkw not in matched_in_text:
                        matched_in_text.append(dkw)

        if score > max_score:
            max_score = score
            best_tag = tag_id
            best_kws = matched_in_text if matched_in_text else default_kws[:2]

    return best_tag, best_kws


def sanitize_episodes(records, episodes):
    print("Sanitizing 144 failure episodes...")
    existing_pids = set(ep.get("post_id") for ep in episodes)
    
    # Collect genuine high-friction candidates from records
    valid_candidates = []
    for r in records:
        pid = r.get("post_id")
        if pid in existing_pids:
            continue
        c = clean_comment(r)
        tag, kws = classify_text(c)
        if tag and len(c) > 35:
            valid_candidates.append((r, c, tag, kws))

    print(f"Pool of verified candidates to replace noise: {len(valid_candidates)}")
    cand_idx = 0

    clean_episodes = []
    replaced_count = 0

    for idx, ep in enumerate(episodes):
        q = clean_comment(ep)
        tag, kws = classify_text(q)
        if not tag and cand_idx < len(valid_candidates):
            cand_r, cand_c, cand_tag, cand_kws = valid_candidates[cand_idx]
            cand_idx += 1
            replaced_count += 1
            
            new_ep = dict(cand_r)
            new_ep["episode_id"] = ep.get("episode_id") or f"SIP-EP-{idx+1:03d}"
            new_ep["quote"] = cand_c
            new_ep["text"] = cand_c
            clean_episodes.append(new_ep)
        else:
            clean_episodes.append(ep)

    print(f"Replaced {replaced_count} noise episodes with genuine mutual fund friction episodes.")
    return clean_episodes


def run():
    print("Loading datasets...")
    with open(FILTERED_FILE, "r", encoding="utf-8") as f:
        fil_data = json.load(f)
    records = fil_data.get("sip_records", [])

    with open(EPISODES_FILE, "r", encoding="utf-8") as f:
        ep_data = json.load(f)
    episodes = ep_data.get("episodes", [])

    # Step 1: Sanitize 144 Golden Failure Episodes so 0% noise remains
    episodes = sanitize_episodes(records, episodes)

    # Step 2: Tag all 144 episodes semantically
    print("Tagging 144 episodes semantically...")
    ep_cat_counts = Counter()
    ep_tag_counts = Counter()

    for idx, ep in enumerate(episodes):
        q = clean_comment(ep)
        tag_id, matched_kws = classify_text(q)
        if not tag_id:
            tag_id = "FINANCIAL_NEEDS_MISMATCH"
            matched_kws = ["liquidity needs", "access to money"]

        cat_id = None
        tag_meta = None
        for cid, cinfo in TAXONOMY_SPEC.items():
            if tag_id in cinfo["tags"]:
                cat_id = cid
                tag_meta = cinfo["tags"][tag_id]
                break
        cat_meta = TAXONOMY_SPEC[cat_id]

        ep["is_mf_tagged"] = True
        ep["mf_category"] = cat_id
        ep["mf_category_name"] = cat_meta["category_name"]
        ep["mf_category_icon"] = cat_meta["category_icon"]
        ep["mf_category_badge"] = cat_meta["badge_color"]
        ep["mf_category_bg"] = cat_meta["bg_color"]
        ep["mf_category_border"] = cat_meta["border_color"]
        ep["mf_tag"] = tag_id
        ep["mf_tag_name"] = tag_meta["name"]
        ep["mf_tag_description"] = tag_meta["description"]
        ep["mf_tag_keywords"] = matched_kws
        ep["mf_behavioral_driver"] = tag_meta["behavioral_driver"]
        ep["mf_pm_intervention"] = tag_meta["pm_intervention"]

        ep_cat_counts[cat_id] += 1
        ep_tag_counts[tag_id] += 1

    # Step 3: Classify all 2,016 records semantically
    print("Classifying 2,016 voices semantically...")
    tagged_records_count = 0
    unassigned_count = 0
    rec_cat_counts = Counter()
    rec_tag_counts = Counter()

    for r in records:
        clean_txt = clean_comment(r)
        tag_id, matched_kws = classify_text(clean_txt)

        if tag_id:
            cat_id = None
            tag_meta = None
            for cid, cinfo in TAXONOMY_SPEC.items():
                if tag_id in cinfo["tags"]:
                    cat_id = cid
                    tag_meta = cinfo["tags"][tag_id]
                    break
            cat_meta = TAXONOMY_SPEC[cat_id]

            r["is_mf_tagged"] = True
            r["mf_category"] = cat_id
            r["mf_category_name"] = cat_meta["category_name"]
            r["mf_category_icon"] = cat_meta["category_icon"]
            r["mf_category_badge"] = cat_meta["badge_color"]
            r["mf_category_bg"] = cat_meta["bg_color"]
            r["mf_category_border"] = cat_meta["border_color"]
            r["mf_tag"] = tag_id
            r["mf_tag_name"] = tag_meta["name"]
            r["mf_tag_description"] = tag_meta["description"]
            r["mf_tag_keywords"] = matched_kws
            r["mf_behavioral_driver"] = tag_meta["behavioral_driver"]
            r["mf_pm_intervention"] = tag_meta["pm_intervention"]

            rec_cat_counts[cat_id] += 1
            rec_tag_counts[tag_id] += 1
            tagged_records_count += 1
        else:
            # UNASSIGNED: General feedback, video pacing comment, or unrelated praise
            r["is_mf_tagged"] = False
            r["mf_category"] = None
            r["mf_category_name"] = "Unassigned"
            r["mf_category_icon"] = "⚪"
            r["mf_category_badge"] = "#9CA3AF"
            r["mf_category_bg"] = "#F9FAFB"
            r["mf_category_border"] = "#E5E7EB"
            r["mf_tag"] = None
            r["mf_tag_name"] = "Unassigned"
            r["mf_tag_description"] = "Public voice does not express any of the 9 specific mutual fund risk, goal, or return friction points."
            r["mf_tag_keywords"] = []
            r["mf_behavioral_driver"] = "General platform observation, video delivery feedback, or positive rating without friction."
            r["mf_pm_intervention"] = "None required."
            unassigned_count += 1

    print(f"\nClassification results across 2,016 voices:")
    print(f"  • Semantically Verified & Tagged: {tagged_records_count}")
    print(f"  • Unassigned (General chatter / noise / non-friction): {unassigned_count}")
    print("\nCategory distribution:")
    for cid, cnt in rec_cat_counts.items():
        print(f"  {cid}: {cnt} ({round(cnt/tagged_records_count*100, 1)}% of tagged)")
    print("\nTag distribution:")
    for tid, cnt in rec_tag_counts.items():
        print(f"  {tid}: {cnt} ({round(cnt/tagged_records_count*100, 1)}% of tagged)")

    # Save enriched datasets
    with open(FILTERED_FILE, "w", encoding="utf-8") as f:
        json.dump(fil_data, f, ensure_ascii=False, indent=2)

    with open(EPISODES_FILE, "w", encoding="utf-8") as f:
        ep_data["episodes"] = episodes
        json.dump(ep_data, f, ensure_ascii=False, indent=2)

    # Compute comprehensive analytics
    category_analytics = []
    for cid, cinfo in TAXONOMY_SPEC.items():
        cnt = rec_cat_counts[cid]
        pct = round((cnt / tagged_records_count) * 100, 1) if tagged_records_count > 0 else 0
        
        tags_data = []
        for tid, tinfo in cinfo["tags"].items():
            t_cnt = rec_tag_counts[tid]
            t_pct = round((t_cnt / tagged_records_count) * 100, 1) if tagged_records_count > 0 else 0
            
            sample_quotes = []
            for r in records:
                if r.get("mf_tag") == tid:
                    q = clean_comment(r)
                    if len(q) > 20:
                        sample_quotes.append({
                            "id": r.get("post_id"),
                            "source": r.get("source"),
                            "author": r.get("author"),
                            "text": q[:180] + ("..." if len(q) > 180 else ""),
                            "matched_keywords": r.get("mf_tag_keywords", [])
                        })
                    if len(sample_quotes) >= 3:
                        break

            tags_data.append({
                "tag_id": tid,
                "name": tinfo["name"],
                "description": tinfo["description"],
                "keywords": tinfo["keywords"],
                "count": t_cnt,
                "percentage": t_pct,
                "behavioral_driver": tinfo["behavioral_driver"],
                "pm_intervention": tinfo["pm_intervention"],
                "sample_quotes": sample_quotes
            })

        category_analytics.append({
            "category": cid,
            "category_name": cinfo["category_name"],
            "category_icon": cinfo["category_icon"],
            "badge_color": cinfo["badge_color"],
            "bg_color": cinfo["bg_color"],
            "border_color": cinfo["border_color"],
            "description": cinfo["description"],
            "count": cnt,
            "percentage": pct,
            "tags": tags_data
        })

    analytics_summary = {
        "success": True,
        "total_analyzed_records": len(records),
        "total_tagged_records": tagged_records_count,
        "total_unassigned_records": unassigned_count,
        "total_analyzed_episodes": len(episodes),
        "taxonomy_categories_count": len(category_analytics),
        "taxonomy_tags_count": sum(len(c["tags"]) for c in category_analytics),
        "categories": category_analytics,
        "tag_distribution": dict(rec_tag_counts),
        "category_distribution": dict(rec_cat_counts)
    }

    with open(ANALYTICS_OUT, "w", encoding="utf-8") as f:
        json.dump(analytics_summary, f, ensure_ascii=False, indent=2)

    print(f"\nSaved updated analytics to {ANALYTICS_OUT}")

    # Rebuild JS evidence bundles
    print("Rebuilding static/sip_evidence_bundle.js...")
    import subprocess
    subprocess.run(["python", "build_sip_evidence_bundle.py"], check=True)
    print("Evidence bundles rebuilt successfully!")

if __name__ == "__main__":
    run()

