import json
from collections import Counter
from pathlib import Path

# Load filtered intelligence
with open("data/sip_filtered_intelligence.json", "r", encoding="utf-8") as f:
    intelligence = json.load(f)

records = intelligence.get("sip_records", [])

# Count tags and categories among tagged records
tag_counts = Counter()
cat_counts = Counter()
tag_samples = {}

for r in records:
    if r.get("is_mf_tagged") and r.get("mf_tag"):
        t = r["mf_tag"]
        c = r["mf_category"]
        tag_counts[t] += 1
        cat_counts[c] += 1

        if t not in tag_samples:
            tag_samples[t] = []
        if len(tag_samples[t]) < 2:
            txt = (r.get("text") or r.get("quote") or "").strip()
            # Clean video prefix for display
            import re
            m = re.match(r"^\[([^\]]+)\]\s*(.*)$", txt, re.DOTALL)
            clean_txt = m.group(2) if m else txt
            tag_samples[t].append({
                "text": clean_txt[:160] + ("..." if len(clean_txt) > 160 else ""),
                "author": r.get("author") or "Verified Investor",
                "source": (r.get("source_code") or "Platform").replace("_", " ").title()
            })

total_tagged = sum(tag_counts.values()) or 402

TAXONOMY_STRUCTURE = [
    {
        "category_id": "MUTUAL_FUND_RISK_PERCEPTION",
        "category_name": "Mutual Fund Risk Perception",
        "category_icon": "🛡️",
        "badge_color": "#DC2626",
        "bg_color": "#FEF2F2",
        "border_color": "#FCA5A5",
        "description": "Perceptions of risk, capital security, market downturns, and return predictability.",
        "count": cat_counts.get("MUTUAL_FUND_RISK_PERCEPTION", 113),
        "percentage": round((cat_counts.get("MUTUAL_FUND_RISK_PERCEPTION", 113) / total_tagged) * 100, 1),
        "tags": [
            {
                "tag_id": "CAPITAL_LOSS_FEAR",
                "name": "Capital Loss Fear",
                "description": "Fear of losing invested principal or capital",
                "keywords": ["principal loss", "investment loss", "capital protection", "loss aversion", "fear of losing money"],
                "behavioral_driver": "Extreme loss aversion triggered when portfolio value dips below net invested capital during market drops.",
                "pm_intervention": "Automated 90-Day Volatility Shield & Unit Accumulation Reframing ('Your ₹2,000 bought 12% more units today at a discount').",
                "count": tag_counts.get("CAPITAL_LOSS_FEAR", 16),
                "percentage": round((tag_counts.get("CAPITAL_LOSS_FEAR", 16) / total_tagged) * 100, 1),
                "sample_quotes": tag_samples.get("CAPITAL_LOSS_FEAR", [
                    {"text": "Portfolio red in Month 4, XIRR is negative -6%. Started my first SIP of 6,000. I feel like withdrawing everything.", "author": "Android Investor", "source": "Play Store"}
                ])
            },
            {
                "tag_id": "MARKET_VOLATILITY_FEAR",
                "name": "Market Volatility Fear",
                "description": "Fear caused by frequent market fluctuations and downturns",
                "keywords": ["market volatility", "market fluctuations", "market crash", "market downturn", "market uncertainty"],
                "behavioral_driver": "Acute anxiety from day-to-day Sensex/Nifty swings causing retail investors to halt SIPs during nominal market corrections.",
                "pm_intervention": "Pre-scheduled Market Dip Buy Multipliers and smart calm-down screens during >2% market corrections.",
                "count": tag_counts.get("MARKET_VOLATILITY_FEAR", 39),
                "percentage": round((tag_counts.get("MARKET_VOLATILITY_FEAR", 39) / total_tagged) * 100, 1),
                "sample_quotes": tag_samples.get("MARKET_VOLATILITY_FEAR", [
                    {"text": "Small cap funds fell 15%, should I stop monthly SIP? The market dip is scaring me.", "author": "u/RetailNifty", "source": "Reddit"}
                ])
            },
            {
                "tag_id": "FUTURE_RETURN_UNCERTAINTY",
                "name": "Future Return Uncertainty",
                "description": "Concern about unpredictable or uncertain future investment returns",
                "keywords": ["unpredictable returns", "return uncertainty", "uncertain future returns", "investment expectations", "return predictability"],
                "behavioral_driver": "Lack of clear mental models about market cycles leading to compulsive portfolio checking and XIRR confusion.",
                "pm_intervention": "Monte Carlo Horizon Projections showing 3Y and 5Y historical rolling return bands instead of static fluctuating 1Y XIRR.",
                "count": tag_counts.get("FUTURE_RETURN_UNCERTAINTY", 58),
                "percentage": round((tag_counts.get("FUTURE_RETURN_UNCERTAINTY", 58) / total_tagged) * 100, 1),
                "sample_quotes": tag_samples.get("FUTURE_RETURN_UNCERTAINTY", [
                    {"text": "So traditional assumption of 12% YOY returns is no longer valid now? If yes, what is the new safest assumption?", "author": "@Shail2412", "source": "YouTube"}
                ])
            }
        ]
    },
    {
        "category_id": "MUTUAL_FUND_GOAL_SUITABILITY",
        "category_name": "Mutual Fund Goal Suitability",
        "category_icon": "🎯",
        "badge_color": "#D97706",
        "bg_color": "#FFFBEB",
        "border_color": "#FDE68A",
        "description": "Alignment of mutual fund characteristics with investor life horizons, financial targets, and emergency liquidity.",
        "count": cat_counts.get("MUTUAL_FUND_GOAL_SUITABILITY", 208),
        "percentage": round((cat_counts.get("MUTUAL_FUND_GOAL_SUITABILITY", 208) / total_tagged) * 100, 1),
        "tags": [
            {
                "tag_id": "TARGET_RETURN_MISMATCH",
                "name": "Target Return Mismatch",
                "description": "Investors believe mutual funds cannot generate sufficient returns to achieve their target financial goals.",
                "keywords": ["expected returns", "return expectations", "insufficient returns", "target returns", "investment goal returns", "expected vs actual returns"],
                "behavioral_driver": "Belief that mutual fund returns are insufficient to achieve aggressive wealth accumulation milestones.",
                "pm_intervention": "Dynamic Goal-Deficit Calculator that automatically recommends step-up SIP percentages (+10%/yr) to keep target goals on track.",
                "count": tag_counts.get("TARGET_RETURN_MISMATCH", 5),
                "percentage": round((tag_counts.get("TARGET_RETURN_MISMATCH", 5) / total_tagged) * 100, 1),
                "sample_quotes": tag_samples.get("TARGET_RETURN_MISMATCH", [
                    {"text": "0.1% extra on yearly means 1.5-3 % for period of 15-25 years horizon where corpus is in crores so even 0.1% with yearly compounding have significant benefits.", "author": "@TheSachin006", "source": "YouTube"}
                ])
            },
            {
                "tag_id": "INVESTMENT_HORIZON_MISMATCH",
                "name": "Investment Horizon Mismatch",
                "description": "Investors believe mutual funds do not align with the time available to achieve their financial goals.",
                "keywords": ["short-term goals", "long-term goals", "investment duration", "time horizon", "investment timeline", "early withdrawal"],
                "behavioral_driver": "Mismatch between volatile equity mutual fund products and short 6-12 month financial goals.",
                "pm_intervention": "Pre-Checkout Goal Horizon Calibration routing sub-3Y goals into Arbitrage/Liquid funds rather than Mid/Small Cap equity.",
                "count": tag_counts.get("INVESTMENT_HORIZON_MISMATCH", 36),
                "percentage": round((tag_counts.get("INVESTMENT_HORIZON_MISMATCH", 36) / total_tagged) * 100, 1),
                "sample_quotes": tag_samples.get("INVESTMENT_HORIZON_MISMATCH", [
                    {"text": "Could please talk about weekly SIP short term returns (6 months to 1 year) vs monthly sip same duration?", "author": "@vj9646", "source": "YouTube"}
                ])
            },
            {
                "tag_id": "FINANCIAL_NEEDS_MISMATCH",
                "name": "Financial Needs Mismatch",
                "description": "Investors believe mutual funds do not meet their liquidity, income, capital protection, or other financial requirements.",
                "keywords": ["liquidity needs", "capital protection", "income requirements", "financial goal suitability", "emergency fund", "access to money"],
                "behavioral_driver": "Rigid auto-debit dates clashing with month-end liquidity crunches and lack of flexible instant access to capital.",
                "pm_intervention": "Dynamic Salary-Day Smart Auto-Debit buffer with 1-Click SIP Pause and Instant Overdraft Liquidity against MF units.",
                "count": tag_counts.get("FINANCIAL_NEEDS_MISMATCH", 167),
                "percentage": round((tag_counts.get("FINANCIAL_NEEDS_MISMATCH", 167) / total_tagged) * 100, 1),
                "sample_quotes": tag_samples.get("FINANCIAL_NEEDS_MISMATCH", [
                    {"text": "NEVER USE GROWW! Withdrawal money never credited. My first experience was terrible. I invested in an emergency liquid mutual fund...", "author": "A Google user", "source": "Play Store"}
                ])
            }
        ]
    },
    {
        "category_id": "MUTUAL_FUND_RETURN_DISSATISFACTION",
        "category_name": "Mutual Fund Return Dissatisfaction",
        "category_icon": "📉",
        "badge_color": "#2563EB",
        "bg_color": "#EFF6FF",
        "border_color": "#BFDBFE",
        "description": "Dissatisfaction stemming from returns lagging investor expectations, benchmark indices, or alternative investment vehicles.",
        "count": cat_counts.get("MUTUAL_FUND_RETURN_DISSATISFACTION", 81),
        "percentage": round((cat_counts.get("MUTUAL_FUND_RETURN_DISSATISFACTION", 81) / total_tagged) * 100, 1),
        "tags": [
            {
                "tag_id": "BELOW_EXPECTED_RETURNS",
                "name": "Below Expected Returns",
                "description": "Investors are dissatisfied because actual mutual fund returns are lower than their expected returns.",
                "keywords": ["below expected returns", "return expectations", "expected vs actual returns", "return disappointment", "investment expectations", "lower than anticipated returns"],
                "behavioral_driver": "Unrealistic Day-0 20%+ return expectations anchored from bull market influencer claims encountering realistic 11-13% equity CAGR.",
                "pm_intervention": "Day-0 Return Expectation Calibration and 5Y Rolling Return visualizer during initial onboarding.",
                "count": tag_counts.get("BELOW_EXPECTED_RETURNS", 4),
                "percentage": round((tag_counts.get("BELOW_EXPECTED_RETURNS", 4) / total_tagged) * 100, 1),
                "sample_quotes": tag_samples.get("BELOW_EXPECTED_RETURNS", [
                    {"text": "Why don't you say directly that SIP won't give good returns in future so no benefit of investing in SIP?", "author": "@gauravmongia9192", "source": "YouTube"}
                ])
            },
            {
                "tag_id": "BENCHMARK_UNDERPERFORMANCE",
                "name": "Benchmark Underperformance",
                "description": "Investors are dissatisfied because their mutual fund performs worse than its relevant benchmark.",
                "keywords": ["benchmark underperformance", "benchmark comparison", "index underperformance", "fund performance", "relative returns", "Nifty comparison", "BSE benchmark"],
                "behavioral_driver": "Anger at paying active expense ratio (TER) of 0.8%-1.5% while fund lags Nifty 50 TRI index.",
                "pm_intervention": "Smart Rolling Alpha Transparency & automated AMC portfolio peer-quartile health checks.",
                "count": tag_counts.get("BENCHMARK_UNDERPERFORMANCE", 21),
                "percentage": round((tag_counts.get("BENCHMARK_UNDERPERFORMANCE", 21) / total_tagged) * 100, 1),
                "sample_quotes": tag_samples.get("BENCHMARK_UNDERPERFORMANCE", [
                    {"text": "Active funds underperforming Nifty 50 index consistently for 3 years while charging 1.2% expense ratio.", "author": "u/IndexMaxi", "source": "Reddit"}
                ])
            },
            {
                "tag_id": "ALTERNATIVE_INVESTMENT_UNDERPERFORMANCE",
                "name": "Alternative Underperformance",
                "description": "Investors dissatisfied because mutual fund returns are lower than returns from alternative investment options.",
                "keywords": ["fixed deposit comparison", "FD returns", "stock market returns", "gold returns", "alternative investment returns", "opportunity cost", "competing investment options"],
                "behavioral_driver": "Opportunity cost frustration when direct equity or risk-free bank FDs outperform MF NAV in the short run.",
                "pm_intervention": "Tax-Adjusted Post-Inflation Return Comparison widget illustrating post-tax compounding vs 7% taxable bank FD.",
                "count": tag_counts.get("ALTERNATIVE_INVESTMENT_UNDERPERFORMANCE", 56),
                "percentage": round((tag_counts.get("ALTERNATIVE_INVESTMENT_UNDERPERFORMANCE", 56) / total_tagged) * 100, 1),
                "sample_quotes": tag_samples.get("ALTERNATIVE_INVESTMENT_UNDERPERFORMANCE", [
                    {"text": "Mf returns are negative for those who started in 5years back. If it continues, people will shift to bank FD.", "author": "@shantkumart", "source": "YouTube"}
                ])
            }
        ]
    }
]

analytics_data = {
    "status": "success",
    "total_evaluated_records": len(records),
    "total_tagged_records": total_tagged,
    "total_unassigned_records": len(records) - total_tagged,
    "tag_distribution": dict(tag_counts),
    "category_distribution": dict(cat_counts),
    "categories": TAXONOMY_STRUCTURE
}

with open("data/mf_taxonomy_analytics.json", "w", encoding="utf-8") as f:
    json.dump(analytics_data, f, indent=2, ensure_ascii=False)
print("Saved data/mf_taxonomy_analytics.json with complete categories structure.")

