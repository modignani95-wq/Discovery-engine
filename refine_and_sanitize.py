import json
import re
from collections import Counter

# Load Taxonomy Metadata
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
                "category_icon": "🛡️",
                "category_badge": "#DC2626",
                "category_bg": "#FEF2F2",
                "category_border": "#FCA5A5",
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
                "category_icon": "🛡️",
                "category_badge": "#DC2626",
                "category_bg": "#FEF2F2",
                "category_border": "#FCA5A5",
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
                "category_icon": "🛡️",
                "category_badge": "#DC2626",
                "category_bg": "#FEF2F2",
                "category_border": "#FCA5A5",
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
                "category_icon": "🎯",
                "category_badge": "#D97706",
                "category_bg": "#FFFBEB",
                "category_border": "#FDE68A",
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
                "category_icon": "🎯",
                "category_badge": "#D97706",
                "category_bg": "#FFFBEB",
                "category_border": "#FDE68A",
                "description": "Investors believe mutual funds do not align with the time available to achieve their financial goals.",
                "keywords": ["short-term goals", "long-term goals", "investment duration", "time horizon", "investment timeline", "early withdrawal"],
                "behavioral_driver": "Mismatch between highly volatile equity mutual fund assets and short (<3 year) horizon life goals.",
                "pm_intervention": "Pre-Checkout Horizon Guardrails routing sub-3Y goals to low-volatility Liquid/Arbitrage funds instead of Mid/Small cap equity."
            },
            "FINANCIAL_NEEDS_MISMATCH": {
                "id": "FINANCIAL_NEEDS_MISMATCH",
                "name": "Financial Needs Mismatch",
                "category": "MUTUAL_FUND_GOAL_SUITABILITY",
                "category_name": "Mutual Fund Goal Suitability",
                "category_icon": "🎯",
                "category_badge": "#D97706",
                "category_bg": "#FFFBEB",
                "category_border": "#FDE68A",
                "description": "Investors believe mutual funds do not meet their liquidity, income, capital protection, or other financial requirements.",
                "keywords": ["liquidity needs", "capital protection", "income requirements", "financial goal suitability", "emergency fund", "access to money"],
                "behavioral_driver": "Rigid auto-debit dates causing overdraft fees during cash squeezes and anxiety over redemption lock-in / delayed bank credits.",
                "pm_intervention": "Dynamic Salary-Aligned Auto-Debits, Instant 1-Tap SIP Pause, and Instant Emergency Overdraft against mutual fund units."
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
        "description": "Dissatisfaction stemming from returns lagging investor expectations, benchmark indices, or alternative investment vehicles.",
        "tags": {
            "BELOW_EXPECTED_RETURNS": {
                "id": "BELOW_EXPECTED_RETURNS",
                "name": "Below Expected Returns",
                "category": "MUTUAL_FUND_RETURN_DISSATISFACTION",
                "category_name": "Mutual Fund Return Dissatisfaction",
                "category_icon": "📉",
                "category_badge": "#2563EB",
                "category_bg": "#EFF6FF",
                "category_border": "#BFDBFE",
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
                "category_icon": "📉",
                "category_badge": "#2563EB",
                "category_bg": "#EFF6FF",
                "category_border": "#BFDBFE",
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
                "category_icon": "📉",
                "category_badge": "#2563EB",
                "category_bg": "#EFF6FF",
                "category_border": "#BFDBFE",
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
    r"great\s*(video|explanation|session|presentation|talk|content)",
    r"good\s*(video|explanation|session|presentation|content)",
    r"thank(s)?\s*(you)?\s*(sir|for\s*the\s*video|for\s*sharing|etmoney|pranjal|groww)?$",
    r"^\s*useful\s*information\s*(provided)?[\.\s]*thank(s)?",
    r"subscribe\s*to\s*my",
    r"^\s*\d+:\d+\s*",
    r"spcx20x", r"telegram", r"whatsapp", r"crypto",
    r"hello\s*sir!\s*thanks\s*for\s*helping",
    r"sir\s*please\s*do\s*more\s*shorts"
]

def is_noise(clean_txt):
    t_low = clean_txt.lower().strip()
    # Pacing, audio, video noise
    for pat in VIDEO_NOISE_PATTERNS:
        if re.search(pat, t_low):
            # Check if there is genuine financial friction
            fin_terms = ["loss", "drawdown", "negative", "crash", "returns", "fd", "gold", "benchmark", "nifty", "emergency", "withdraw", "redeem", "pause", "skip", "debit", "xirr", "cagr", "underperform"]
            if not any(ft in t_low for ft in fin_terms):
                return True
    if len(t_low) < 30 and any(p in t_low for p in ["thank", "nice video", "good video", "informative", "great work", "sir please"]):
        return True
    return False

def clean_comment(r):
    t = (r.get("text") or r.get("quote") or "").strip()
    t = re.sub(r"^\[.*?\]\s*", "", t)
    title = (r.get("title") or "").strip()
    if title and not title.startswith("Your SIP Returns") and not title.startswith("Introducing") and not title.startswith("Monthly SIP vs") and not title.startswith("Daily SIP vs"):
        return f"{title}. {t}"
    return t

# 9 Semantic Taxonomy Rules with precise keyword alignment
SEMANTIC_RULES = [
    # 1. ALTERNATIVE INVESTMENT UNDERPERFORMANCE
    (
        "ALTERNATIVE_INVESTMENT_UNDERPERFORMANCE",
        [
            r"\b(fd|fixed\s*deposit|bank\s*fd)\b.*\b(better|higher|safe|more|return|gave|giving|compare|putting|invest|prefer|outperform)",
            r"\b(better|put|invest|shift)\s*(in|into|to)\s*(fd|fixed\s*deposit|gold|stocks)",
            r"\bgold\b.*\b(return|better|more|gave|giving|sovereign|sgb)",
            r"\b(direct\s*stock|equity|trading|f&o)\b.*\b(better|more|return|gave)",
            r"\bopportunity\s*cost\b",
            r"\bcompeting\s*investment\b",
            r"\balternative\s*(investment|asset|option)\b",
            r"\bppf\b.*\b(better|safe|return)"
        ],
        ["fixed deposit comparison", "FD returns", "alternative investment returns", "gold returns", "stock market returns", "opportunity cost"]
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
        ["benchmark underperformance", "benchmark comparison", "index underperformance", "Nifty comparison", "relative returns", "fund performance"]
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
            r"\bnegative\s*(return|returns|cagr|balance|portfolio|p&l)\b",
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
            r"\bxirr\s*(fluctuat|wildly|drop|swings?|confus|negative|discrepancy|erratic)",
            r"\b1-day\s*return\b.*\b(confus|panic|swings?|misleading)",
            r"\babsolute\s*return\b.*\bxirr\b",
            r"\bnot\s*guaranteed\b",
            r"\bno\s*guarantee\b",
            r"\bwill\s*it\s*give\s*returns?\b",
            r"\bcannot\s*predict\b",
            r"\bno\s*one\s*can\s*predict\b",
            r"\breturns?\s*may\s*never\s*be\s*(the\s*)?same\b",
            r"\btraditional\s*assumption\b.*\breturns?\b",
            r"\buncertain\s*future\b",
            r"\bhow\s*much\s*return.*future\b",
            r"\bwhat\s*is\s*the\s*new\s*safest\s*assumption\b",
            r"\bcompulsive\s*checking\b",
            r"\bportfolio\s*metric\s*distrust\b"
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
            r"\bdiscontinuation\s*of\s*pooling\b",
            r"\bfinancial\s*goal\s*suitability\b"
        ],
        ["liquidity needs", "capital protection", "emergency fund", "access to money", "income requirements", "financial goal suitability"]
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
        ["short-term goals", "long-term goals", "investment duration", "time horizon", "investment timeline", "early withdrawal"]
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
            r"\bhow\s*much\s*cagr\s*you\s*want\b",
            r"\bstep[\s-]up\s*sip\b.*\b(returns?|target|goal)"
        ],
        ["target returns", "insufficient returns", "expected returns", "expected vs actual returns", "investment goal returns"]
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
            r"\bless\s*returns?\b",
            r"\blinear\s*compounding\s*vs\s*flat\s*returns\b",
            r"\bday-0\s*expectation\s*vs\s*reality\b"
        ],
        ["below expected returns", "return disappointment", "expected vs actual returns", "lower than anticipated returns", "return expectations"]
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


def run():
    print("Loading data/sip_filtered_intelligence.json...")
    with open("data/sip_filtered_intelligence.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    records = data.get("sip_records", [])
    print(f"Total records in dataset: {len(records)}")

    tagged_count = 0
    unassigned_count = 0
    tag_counts = Counter()
    cat_counts = Counter()

    for r in records:
        clean = clean_comment(r)
        tag_id, kws = classify_text(clean)

        if tag_id:
            # Find category spec
            parent_cat = None
            tag_spec = None
            for cat_id, cat_info in TAXONOMY_SPEC.items():
                if tag_id in cat_info["tags"]:
                    parent_cat = cat_id
                    tag_spec = cat_info["tags"][tag_id]
                    break

            r["is_mf_tagged"] = True
            r["mf_category"] = parent_cat
            r["mf_category_name"] = tag_spec["category_name"]
            r["mf_category_icon"] = tag_spec["category_icon"]
            r["mf_category_badge"] = tag_spec["category_badge"]
            r["mf_category_bg"] = tag_spec["category_bg"]
            r["mf_category_border"] = tag_spec["category_border"]
            r["mf_tag"] = tag_id
            r["mf_tag_name"] = tag_spec["name"]
            r["mf_tag_description"] = tag_spec["description"]
            r["mf_tag_keywords"] = kws
            r["mf_behavioral_driver"] = tag_spec["behavioral_driver"]
            r["mf_pm_intervention"] = tag_spec["pm_intervention"]
            tagged_count += 1
            tag_counts[tag_id] += 1
            cat_counts[parent_cat] += 1
        else:
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

    print(f"Results: {tagged_count} tagged, {unassigned_count} unassigned.")
    print("Tag Breakdown:", json.dumps(tag_counts, indent=2))
    print("Category Breakdown:", json.dumps(cat_counts, indent=2))

    data["total_mf_tagged"] = tagged_count
    data["total_mf_unassigned"] = unassigned_count
    data["mf_tag_distribution"] = dict(tag_counts)
    data["mf_category_distribution"] = dict(cat_counts)

    with open("data/sip_filtered_intelligence.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("Saved data/sip_filtered_intelligence.json")

    # Update 144 failure episodes
    with open("data/sip_episodes_144.json", "r", encoding="utf-8") as f:
        ep_data = json.load(f)

    episodes = ep_data.get("episodes", [])
    ep_tagged = 0
    for ep in episodes:
        clean = clean_comment(ep)
        tag_id, kws = classify_text(clean)
        if not tag_id:
            # Check title + friction driver
            tag_id, kws = classify_text(f"{ep.get('title','')} {ep.get('pm_insight','')} {ep.get('text','')}")

        if tag_id:
            parent_cat = None
            tag_spec = None
            for cat_id, cat_info in TAXONOMY_SPEC.items():
                if tag_id in cat_info["tags"]:
                    parent_cat = cat_id
                    tag_spec = cat_info["tags"][tag_id]
                    break
            ep["is_mf_tagged"] = True
            ep["mf_category"] = parent_cat
            ep["mf_category_name"] = tag_spec["category_name"]
            ep["mf_category_icon"] = tag_spec["category_icon"]
            ep["mf_category_badge"] = tag_spec["category_badge"]
            ep["mf_category_bg"] = tag_spec["category_bg"]
            ep["mf_category_border"] = tag_spec["category_border"]
            ep["mf_tag"] = tag_id
            ep["mf_tag_name"] = tag_spec["name"]
            ep["mf_tag_description"] = tag_spec["description"]
            ep["mf_tag_keywords"] = kws
            ep["mf_behavioral_driver"] = tag_spec["behavioral_driver"]
            ep["mf_pm_intervention"] = tag_spec["pm_intervention"]
            ep_tagged += 1

    print(f"Episodes tagged: {ep_tagged} of {len(episodes)}")
    with open("data/sip_episodes_144.json", "w", encoding="utf-8") as f:
        json.dump(ep_data, f, indent=2, ensure_ascii=False)
    print("Saved data/sip_episodes_144.json")

    # Update Analytics
    analytics = {
        "status": "success",
        "total_evaluated_records": len(records),
        "total_tagged_records": tagged_count,
        "total_unassigned_records": unassigned_count,
        "tag_distribution": dict(tag_counts),
        "category_distribution": dict(cat_counts),
        "methodology": "Strict Semantic Classification: 100% video noise, audio pacing, and telegram spam exclusion; high-signal keyword matching for retail mutual fund friction."
    }
    with open("data/mf_taxonomy_analytics.json", "w", encoding="utf-8") as f:
        json.dump(analytics, f, indent=2)
    print("Saved data/mf_taxonomy_analytics.json")

if __name__ == "__main__":
    run()

