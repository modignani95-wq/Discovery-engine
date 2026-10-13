"""
Product Manager Competitive Intelligence Engine.
Analyzes reviews for growth PMs: scorecards, pain points, pricing complaints,
growth recommendations, PRD generation, and stakeholder emails.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional


PAIN_POINT_CATEGORIES = {
    "complexity": {
        "label": "Complexity & Onboarding",
        "description": "Steep learning curve, confusing navigation, friction in setup",
        "keywords": ["confusing", "complicated", "hard to", "complex", "cluttered", "overwhelming", "unintuitive", "steep learning", "difficult", "messy", "lost", "convoluted"],
        "icon": "🧩",
    },
    "pricing": {
        "label": "Pricing & Hidden Fees",
        "description": "Subscription costs, unexpected fees, deposit charges, paywalls",
        "keywords": ["fee", "cost", "price", "charge", "subscription", "expensive", "hidden", "rip off", "greedy", "paywall", "cancel", "refund", "billing", "annual", "monthly", "overpriced"],
        "icon": "💳",
    },
    "performance": {
        "label": "Performance & Stability",
        "description": "Crashes, freezing, slow load times, battery drain, errors",
        "keywords": ["crash", "freeze", "slow", "lag", "bug", "glitch", "error", "black screen", "stuck", "hang", "battery", "drain", "reload", "failed to load", "not working", "down"],
        "icon": "⚡",
    },
    "integration": {
        "label": "Mobile & Bank Integration",
        "description": "Plaid linking failures, biometric login issues, broken syncing",
        "keywords": ["link", "connect", "sync", "plaid", "bank", "account", "login", "biometric", "fingerprint", "face id", "notification", "widget", "transfer", "deposit", "connection"],
        "icon": "🔗",
    },
    "support": {
        "label": "Customer Support",
        "description": "Unresponsive agents, automated bots, unresolved tickets",
        "keywords": ["support", "customer service", "email", "chat", "ticket", "unresponsive", "no reply", "bot", "automated", "representative", "wait days", "helpless", "contact", "agent"],
        "icon": "🎧",
    },
    "ux": {
        "label": "UX & Navigation",
        "description": "Clunky controls, poor visual hierarchy, broken dark mode, cluttered layouts",
        "keywords": ["ui", "ux", "interface", "design", "navigation", "font", "dark mode", "button", "layout", "ugly", "clunky", "update ruined", "old version", "screen", "visual"],
        "icon": "🎨",
    },
}

DELIGHTER_KEYWORDS = [
    "love", "best", "great", "easy", "simple", "awesome", "favorite", "clean",
    "intuitive", "fast", "recommend", "helpful", "excellent", "peace of mind",
    "automated", "apy", "cash account", "growth", "smart", "smooth", "reliable"
]


def extract_pain_points_and_scorecard(app_name: str, reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze reviews across PM dimensions and compute scorecard & pain point breakdown."""
    total_reviews = max(len(reviews), 1)

    category_stats = {}
    for cat_key, cat_meta in PAIN_POINT_CATEGORIES.items():
        category_stats[cat_key] = {
            "key": cat_key,
            "label": cat_meta["label"],
            "description": cat_meta["description"],
            "icon": cat_meta["icon"],
            "count": 0,
            "negative_count": 0,
            "positive_count": 0,
            "quotes": [],
            "severity": "Low",
        }

    loved_quotes = []
    pricing_complaints = []

    for r in reviews:
        text = (r.get("text") or "").strip()
        lower = text.lower()
        rating = r.get("rating") or 3
        is_neg = rating <= 2
        is_pos = rating >= 4

        # Check delighters
        if is_pos and any(w in lower for w in DELIGHTER_KEYWORDS):
            if len(loved_quotes) < 8 and len(text) > 20:
                loved_quotes.append({
                    "quote": text[:250],
                    "rating": rating,
                    "date": r.get("date", "")[:10],
                    "author": r.get("author", "User"),
                })

        # Match pain point categories
        for cat_key, cat_meta in PAIN_POINT_CATEGORIES.items():
            matched = any(kw in lower for kw in cat_meta["keywords"])
            if matched:
                category_stats[cat_key]["count"] += 1
                if is_neg:
                    category_stats[cat_key]["negative_count"] += 1
                    if len(category_stats[cat_key]["quotes"]) < 5 and len(text) > 20:
                        category_stats[cat_key]["quotes"].append({
                            "quote": text[:250],
                            "rating": rating,
                            "date": r.get("date", "")[:10],
                            "author": r.get("author", "User"),
                        })
                elif is_pos:
                    category_stats[cat_key]["positive_count"] += 1

                # Pricing complaints tracking
                if cat_key == "pricing" and is_neg:
                    pricing_complaints.append({
                        "quote": text[:250],
                        "rating": rating,
                        "date": r.get("date", "")[:10],
                    })

    # Compute severities and scores
    scorecard = {}
    painpoints_list = []

    for cat_key, stats in category_stats.items():
        neg_ratio = stats["negative_count"] / total_reviews
        pos_ratio = stats["positive_count"] / total_reviews

        if neg_ratio >= 0.15:
            severity = "High"
        elif neg_ratio >= 0.05:
            severity = "Medium"
        else:
            severity = "Low"
        stats["severity"] = severity
        stats["percentage"] = round((stats["count"] / total_reviews) * 100, 1)
        stats["negative_percentage"] = round(neg_ratio * 100, 1)

        # Dimension score 1 - 10
        raw_score = 8.5 - (neg_ratio * 20.0) + (pos_ratio * 5.0)
        dim_score = round(max(2.0, min(9.8, raw_score)), 1)
        scorecard[cat_key] = dim_score
        painpoints_list.append(stats)

    ratings = [r.get("rating") for r in reviews if r.get("rating")]
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 4.0
    overall_score = round(sum(scorecard.values()) / len(scorecard), 1) if scorecard else 7.5
    scorecard["overall"] = overall_score

    # Pricing Analysis specifics
    pricing_cat = category_stats["pricing"]
    pricing_analysis = {
        "complaint_count": pricing_cat["negative_count"],
        "complaint_percentage": pricing_cat["negative_percentage"],
        "sentiment_score": scorecard.get("pricing", 7.0),
        "fee_transparency_rating": "High" if scorecard.get("pricing", 7) >= 7.5 else ("Moderate" if scorecard.get("pricing", 7) >= 5.5 else "Low / High Friction"),
        "top_complaints": pricing_complaints[:6],
    }

    return {
        "scorecard": scorecard,
        "painpoints": painpoints_list,
        "pricing_analysis": pricing_analysis,
        "loved_features": loved_quotes,
    }


def compute_velocity_and_trends(reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate 3-month review velocity, monthly volume, and sentiment trajectory."""
    from collections import defaultdict

    monthly_stats = defaultdict(lambda: {"count": 0, "sum_rating": 0, "pos": 0, "neg": 0})
    for r in reviews:
        d = r.get("date", "")[:7]  # YYYY-MM
        if not d:
            continue
        rating = r.get("rating") or 3
        monthly_stats[d]["count"] += 1
        monthly_stats[d]["sum_rating"] += rating
        if rating >= 4:
            monthly_stats[d]["pos"] += 1
        elif rating <= 2:
            monthly_stats[d]["neg"] += 1

    sorted_months = sorted(monthly_stats.keys())
    breakdown = []
    for m in sorted_months:
        item = monthly_stats[m]
        c = item["count"]
        avg = round(item["sum_rating"] / c, 2) if c else 0
        breakdown.append({
            "month": m,
            "count": c,
            "avg_rating": avg,
            "pos_pct": round((item["pos"] / c) * 100, 1) if c else 0,
            "neg_pct": round((item["neg"] / c) * 100, 1) if c else 0,
        })

    # Velocity trajectory
    velocity_delta = 0
    if len(breakdown) >= 2:
        last = breakdown[-1]["count"]
        prev = breakdown[-2]["count"]
        if prev > 0:
            velocity_delta = round(((last - prev) / prev) * 100, 1)

    weekly_velocity = round(len(reviews) / 12.0, 1) if reviews else 0.0

    return {
        "monthly_breakdown": breakdown,
        "weekly_velocity": weekly_velocity,
        "velocity_delta_pct": velocity_delta,
        "trajectory": "Accelerating" if velocity_delta > 10 else ("Decelerating" if velocity_delta < -10 else "Stable"),
    }


def generate_strategic_growth_recommendations(app_results: Dict[str, Any], llm_client=None) -> List[Dict[str, Any]]:
    """Generate rich growth recommendations with Why, Impact, Timeline, Evidence, Criticality, What this means."""
    recommendations = []

    for app_name, data in app_results.items():
        if data.get("error"):
            continue

        painpoints = data.get("painpoints", [])
        scorecard = data.get("scorecard", {})
        top_req = data.get("top_requested", [])
        meta = data.get("meta", {})

        # Find top 2 pain point categories
        sorted_pains = sorted(painpoints, key=lambda p: (p.get("negative_count", 0)), reverse=True)
        top_pain = sorted_pains[0] if sorted_pains else None
        second_pain = sorted_pains[1] if len(sorted_pains) > 1 else None

        # Recommendation 1: Address #1 Pain Point
        if top_pain and top_pain.get("negative_count", 0) > 0:
            evidence_quotes = [q.get("quote") for q in top_pain.get("quotes", [])][:2]
            p0_crit = "P0 - Critical" if top_pain["severity"] == "High" else "P1 - High"
            recommendations.append({
                "app_name": app_name,
                "title": f"Resolve {top_pain['label']} Drop-off Drivers",
                "category": top_pain["key"],
                "icon": top_pain["icon"],
                "criticality": p0_crit,
                "why": f"{top_pain['label']} represents {top_pain.get('negative_percentage', 0)}% of negative reviews, directly degrading user sentiment and causing churn in core flows.",
                "impact": "+15-20% 30-Day Retention, +0.3 App Store Rating increase",
                "timeline": "Quick Win (1-3 weeks)" if top_pain["key"] in ("performance", "ux") else "Mid-Term Sprint (4-6 weeks)",
                "evidence": evidence_quotes or [f"Users frequently cite {top_pain['description'].lower()}"],
                "what_this_means": f"Audit {top_pain['label'].lower()} workflows immediately. Implement proactive telemetry, inline retry mechanisms, and eliminate friction points highlighted in user reviews.",
            })

        # Recommendation 2: Address #2 Pain Point or Pricing
        if second_pain and second_pain.get("negative_count", 0) > 0:
            evidence_quotes = [q.get("quote") for q in second_pain.get("quotes", [])][:2]
            recommendations.append({
                "app_name": app_name,
                "title": f"Optimize {second_pain['label']} & User Transparency",
                "category": second_pain["key"],
                "icon": second_pain["icon"],
                "criticality": "P1 - High",
                "why": f"Repeated user friction around {second_pain['label']} erodes brand trust and creates negative word-of-mouth that caps organic acquisition.",
                "impact": "-30% Customer Support Tickets, +12% Organic Referrals",
                "timeline": "Sprint (2-4 weeks)",
                "evidence": evidence_quotes or [f"Negative reviews focus on {second_pain['description'].lower()}"],
                "what_this_means": f"Redesign the feedback loop for {second_pain['label']}. Make pricing/fees or mobile sync states self-serve and transparent before users become frustrated.",
            })

        # Recommendation 3: Capitalize on Top Requested Feature (Growth Lever)
        if top_req:
            req_name = top_req[0]
            recommendations.append({
                "app_name": app_name,
                "title": f"Ship High-Demand Capability: {req_name}",
                "category": "feature_gap",
                "icon": "🚀",
                "criticality": "P2 - Growth Lever",
                "why": f"'{req_name}' is the single most requested capability across recent user reviews. Competitors lacking this leave an open acquisition moat.",
                "impact": "+25% Feature Adoption, Competitive Differentiation",
                "timeline": "Q1 Roadmap (6-8 weeks)",
                "evidence": [f"Multiple active users explicitly requested: '{req_name}' in reviews"],
                "what_this_means": f"Spec a dedicated PRD for {req_name}. Run quick beta prototyping with high-value cohorts to validate engagement and retention lift.",
            })

    return recommendations


def generate_prd_markdown(app_name: str, app_data: Dict[str, Any], focus_feature: str = "", llm_client=None) -> str:
    """Generate a comprehensive Product Requirement Document (PRD) from review findings."""
    painpoints = app_data.get("painpoints", [])
    top_requested = app_data.get("top_requested", [])
    features = app_data.get("features", [])
    loved = app_data.get("loved_features", [])

    feature_target = focus_feature or (top_requested[0] if top_requested else "Core App Experience & Stability Overhaul")

    # High severity pain points for evidence
    evidence_items = []
    for p in painpoints:
        for q in p.get("quotes", [])[:2]:
            evidence_items.append(f"- **[{p['label']}]** \"{q.get('quote')}\" (Rating: {q.get('rating')}★)")

    if not evidence_items:
        evidence_items.append("- User reviews emphasize demand for improved reliability, clearer fee disclosure, and modern UX.")

    evidence_text = "\n".join(evidence_items[:6])

    # If LLM is available, generate an enriched PRD
    if llm_client:
        try:
            prompt = f"""Generate a professional, thorough Product Requirement Document (PRD) for mobile app: "{app_name}".
Feature / Initiative: "{feature_target}".

User Review Context:
- Avg Rating: {app_data.get('avg_rating')}
- Pain Points: {json.dumps([p['label'] for p in painpoints if p.get('severity') != 'Low'])}
- User Quotes:
{evidence_text}

Generate the PRD in standard Markdown with these sections:
# PRD: {feature_target}
## 1. Executive Summary & Problem Statement
## 2. Voice of Customer & Evidence (quote reviews)
## 3. User Personas & Target Audience
## 4. Goals & Non-Goals
## 5. Functional Requirements (P0, P1, P2)
## 6. UX & Design Principles
## 7. Technical & Non-Functional Requirements
## 8. Success Metrics & North Star KPIs
## 9. Phased Rollout Plan
Be specific, technical, and product-focused."""
            res = llm_client.complete("You are a Principal Product Manager writing an executive-ready PRD.", prompt)
            if res and len(res) > 200:
                return res
        except Exception:
            pass

    # High-quality fallback template
    return f"""# 📄 Product Requirement Document (PRD)

**Project Name:** {feature_target}  
**Target App:** {app_name}  
**Author:** Lead Growth Product Manager  
**Status:** In Review / Ready for Engineering Grooming  
**Target Release:** Next Minor Version (v2.4)  

---

## 1. Executive Summary & Problem Statement
User feedback over the last 90 days indicates critical drop-off and frustration centered around **{feature_target}**. While {app_name} retains high loyalty for its core strengths, negative reviews consistently cite friction that harms acquisition efficiency and 30-day retention.

This PRD defines the requirements to eliminate core friction, address user demand, and establish a competitive advantage over key alternatives.

---

## 2. Voice of the Customer (Review Evidence)
Direct quotes captured from Google Play Store user reviews:

{evidence_text}

---

## 3. Goals & Non-Goals

### Goals
- **Eliminate Drop-Off:** Reduce user-reported errors and task abandonments by at least **40%**.
- **Boost App Store Rating:** Increase Google Play Store rolling 90-day rating from **{app_data.get('avg_rating', 4.0)}★ to 4.8★**.
- **Accelerate Retention:** Improve D30 user retention for newly onboarded cohorts by **+15%**.

### Non-Goals
- Full architectural rewrite of legacy backend services (this release focuses on client-side resilience and API orchestration).
- Introducing unrequested third-party advertising or monetization paywalls.

---

## 4. User Personas
- **The Everyday Mobile User:** Demands immediate, frictionless navigation and zero app freezing. Expects bank connections to stay active without periodic credential drops.
- **The Financial Growth Optimizer:** Sensitive to fee transparency and account performance metrics; wants clear disclosures and self-serve controls.

---

## 5. Functional Requirements

| Priority | Requirement | User Story | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| **P0** | **Inline Telemetry & Auto-Retry** | As a user, if a connection or API fails, I see clear retry options rather than a frozen screen. | System displays informative error banner with 1-tap retry; logs incident to Sentry/Datadog. |
| **P0** | **Transparent Fee / Cost Ledger** | As a customer, I want to see an itemized breakdown of any applicable charges. | A dedicated breakdown view within settings detailing schedule, APY/fees, and renewal dates. |
| **P1** | **Biometric Fast-Auth Recovery** | As an active user, I want reliable fingerprint/Face ID unlock without repetitive password prompts. | Biometric prompt invokes within <300ms; graceful fallback to 2FA SMS/Email on 3 failures. |
| **P2** | **Dark Mode & Contrast Polish** | As an evening user, I want seamless system dark mode without illegible text elements. | 100% WCAG AA contrast compliance across all primary screens. |

---

## 6. Non-Functional Requirements
- **Performance:** App launch to interactive time must remain under **1.8 seconds** on median Android devices.
- **Reliability:** Crash-free session rate must exceed **99.8%**.
- **Security:** Zero plaintext storage of credentials or tokens; full adherence to biometric Keystore standards.

---

## 7. Success Metrics & KPIs
1. **North Star:** +18% increase in 60-day active user retention.
2. **Quality Metric:** 50% decrease in 1-star reviews citing bugs/crashes within 30 days of release.
3. **CSAT:** Internal CSAT score improvement from 72% to 88% on support tickets.

---

## 8. Rollout & Phasing Plan
- **Phase 1 (Alpha / Internal):** Dogfooding with employee cohort (1 week).
- **Phase 2 (Staged Rollout):** 5% rollout to Play Store beta testers; monitor crash rates and error spikes (3 days).
- **Phase 3 (General Availability):** 25% → 50% → 100% rollout over 7 days.
"""


def generate_stakeholder_email_text(app_results: Dict[str, Any], audience: str = "exec", llm_client=None) -> Dict[str, str]:
    """Generate ready-to-send executive stakeholder emails."""
    app_names = [name for name, d in app_results.items() if not d.get("error")]
    apps_str = ", ".join(app_names)

    # Collect key stats
    overview_lines = []
    top_pain_points = []
    for name in app_names:
        d = app_results[name]
        score = d.get("competitive_score", 85)
        rating = d.get("avg_rating", "N/A")
        sent = d.get("sentiment", {})
        pos = round(sent.get("positive", 70))
        overview_lines.append(f"- **{name}:** {rating}★ ({d.get('review_count')} reviews in 90d) | Competitive Score: **{score}/100** | {pos}% Positive")

        pains = d.get("painpoints", [])
        if pains:
            severe = [p['label'] for p in pains if p.get('severity') in ('High', 'Medium')]
            if severe:
                top_pain_points.append(f"- **{name}:** Key friction points in {', '.join(severe[:2])}")

    overview_summary = "\n".join(overview_lines)
    pain_summary = "\n".join(top_pain_points) if top_pain_points else "- Sentiment remains positive across competitors with isolated stability issues."

    if audience == "exec":
        subject = f"Executive Competitive Briefing: App Store Intelligence ({apps_str})"
        body = f"""Hi Leadership Team,

Here is our executive summary of Google Play Store competitive intelligence across {apps_str} over the last 90 days.

### 📊 Competitive Snapshot
{overview_summary}

### ⚠️ Critical Market Observations
{pain_summary}

### 🎯 Strategic Takeaways
1. **User Retention Bottlenecks:** Analysis of 1★ and 2★ reviews shows that customer churn is driven primarily by stability, onboarding friction, and fee transparency rather than lack of secondary features.
2. **Moat Opportunity:** Competitors are leaving whitespace in self-serve tools and responsive customer resolution. Closing these gaps will drive immediate organic rating lift.
3. **Action Plan:** Product and Engineering have scoped targeted P0/P1 fixes to capitalize on competitor vulnerabilities.

Full interactive dashboard and PRD generator available at: http://localhost:5000

Best regards,  
Growth & Product Intelligence Team"""

    elif audience == "eng":
        subject = f"Engineering Impact Report: Play Store Stability & Bug Analysis ({apps_str})"
        body = f"""Hi Engineering Team,

We've synthesized real user reviews from the past 3 months across {apps_str} to isolate stability, performance, and API friction points.

### 🛠️ Priority Technical Insights
{pain_summary}

### 🔍 Identified Hotspots
- **App Crashes & Freezes:** Users report intermittent cold-start crashes and unhandled network errors during bank/account sync.
- **Retry Mechanisms:** Users express high frustration when failed actions produce infinite loading spinners without informative retry states.

### 📋 Recommended Engineering Action Items
- Set up Sentry alert thresholds specifically for startup crashes on recent Android versions.
- Implement client-side timeout guards (8s max) for third-party integrations with graceful offline banners.

Full data and user review quotes available at: http://localhost:5000

Best regards,  
Product Operations"""

    elif audience == "design":
        subject = f"Product & UX Intelligence: User Feedback Highlights ({apps_str})"
        body = f"""Hi Design & Product Team,

Here is our synthesized review feedback regarding user experience, navigation, and feature appreciation across {apps_str}.

### 🎨 What Users Love (Delighters)
- Clean, uncluttered dashboards with immediate account summaries.
- Automatic notifications that provide actionable updates rather than marketing spam.

### 🧩 UX Gaps & Friction Points
{pain_summary}

### 💡 Design Focus Areas
- Streamline first-time onboarding: minimize multi-step forms before initial value delivery.
- Audit typography contrast and dark-mode rendering to address accessibility feedback.

Full review explorer: http://localhost:5000

Best,  
Product Design Lead"""

    else:  # growth
        subject = f"Growth & Acquisition Intelligence: Play Store Competitive Landscape ({apps_str})"
        body = f"""Hi Growth & Marketing Team,

Here is our competitive teardown of Google Play Store sentiment and growth opportunities across {apps_str}.

### 🚀 Performance & Sentiment Benchmarks
{overview_summary}

### 💡 Acquisition Angles & Positioning
- Users actively compare {apps_str} based on transparency and ease of setup.
- Highlight transparent fee structures and rock-solid reliability in upcoming growth campaigns to exploit competitor friction.

Best regards,  
Growth Lead"""

    return {"subject": subject, "body": body}


KNOWN_APP_BUSINESS_INTEL = {
    "pinterest": {
        "company_name": "Pinterest, Inc.",
        "net_worth": "$21.5 Billion (Market Cap / NYSE: PINS)",
        "annual_revenue": "$3.1+ Billion ARR",
        "funding_stage": "Public Company (NYSE: PINS)",
        "business_model_type": "Ad-Supported & Visual Search E-Commerce Engine",
        "primary_revenue_streams": [
            {"name": "Promoted Pins & Performance Ads", "share_pct": "82%", "description": "Native CPC/CPM auction ads embedded directly into user discovery feeds and search results."},
            {"name": "Shoppable Product Pins & Merchant Affiliate", "share_pct": "14%", "description": "Direct checkout integrations, merchant catalogs, and e-commerce affiliate referral fees."},
            {"name": "Brand Partnerships & Sponsored Trend Badges", "share_pct": "4%", "description": "High-impact takeover campaigns and seasonal event curation sponsorships."},
        ],
        "pricing_tiers": [
            {"tier": "Consumer Tier", "price": "100% Free", "target": "Everyday visual discovery users, pinners, and hobbyists."},
            {"tier": "Pinterest Business / Ads Manager", "price": "Dynamic Bidding (Min $0.10 CPC)", "target": "Direct-to-consumer (DTC) brands, retailers, and digital marketers."},
        ],
        "target_personas": [
            {
                "name": "The Lifestyle Curator & Home Planner",
                "archetype": "High-Intent Consumer",
                "jtbd": "Save inspirational recipes, home decor ideas, and DIY event boards for future purchase intent.",
                "pain_points": "Excessive intrusive advertising cluttering search results and non-relevant sponsored pins.",
                "willingness_to_pay": "Low (Prefers free access, tolerates targeted ads)",
                "key_delighter": "Infinite visual recommendations and clean moodboard organization.",
            },
            {
                "name": "The E-Commerce Brand Marketer",
                "archetype": "B2B Advertiser",
                "jtbd": "Drive top-of-funnel discovery to high-AOV retail checkout with visually engaging catalog pins.",
                "pain_points": "Rising cost-per-click and tracking attribution across multi-device conversions.",
                "willingness_to_pay": "High ($1,000 - $50,000+/mo in ad spend)",
                "key_delighter": "Audiences with purchase intent browsing before making shopping decisions.",
            },
        ],
        "monetization_friction": "Users frequently complain about feed saturation with sponsored ads and fake shop links overtaking organic creative content.",
        "strategic_opportunity": "Refine native shopping UX to make ads feel like organic product recommendations while preserving creative discovery.",
    },
    "behance": {
        "company_name": "Adobe Inc. (Parent Company)",
        "net_worth": "$210+ Billion (Adobe Market Cap / NASDAQ: ADBE)",
        "annual_revenue": "$21.4 Billion (Adobe Consolidated ARR)",
        "funding_stage": "Acquired subsidiary of Adobe Inc.",
        "business_model_type": "Freemium Creative Showcase, Creative Cloud Upsell & Freelance Marketplace",
        "primary_revenue_streams": [
            {"name": "Adobe Creative Cloud Pro Subscriptions", "share_pct": "65%", "description": "Funnel for Adobe CC suite (Photoshop, Illustrator, InDesign) and Behance Pro premium perks."},
            {"name": "Behance Pro Subscriptions ($9.99/mo)", "share_pct": "20%", "description": "Custom portfolio domains, 0% platform platform fee on freelance contracts, advanced analytics, and premium badge."},
            {"name": "Freelance Hiring & Project Commissions", "share_pct": "15%", "description": "Transaction and processing fees charged on freelance job board contracts and client billings."},
        ],
        "pricing_tiers": [
            {"tier": "Basic Member", "price": "Free", "target": "Art students, hobbyist creators, and casual portfolio viewers."},
            {"tier": "Behance Pro", "price": "$9.99 / month", "target": "Independent freelancers, creative directors, and full-time digital artists."},
            {"tier": "Adobe Creative Cloud All Apps", "price": "$59.99 / month", "target": "Professional agencies, studios, and enterprise design teams."},
        ],
        "target_personas": [
            {
                "name": "The Freelance Designer & Portfolio Builder",
                "archetype": "Independent Creative Professional",
                "jtbd": "Showcase high-resolution case studies to win client commissions and freelance inquiries.",
                "pain_points": "Difficult mobile project uploads, unhandled sign-in bugs with Adobe ID, and slow messaging notifications.",
                "willingness_to_pay": "Medium ($10 - $60/month for verified exposure & software)",
                "key_delighter": "Community appreciation (appreciations/curated gallery features) and direct job opportunities.",
            },
            {
                "name": "The Design Recruiter & Creative Director",
                "archetype": "Talent Acquirer / Employer",
                "jtbd": "Scout verified graphic designers, 3D illustrators, and UX architects worldwide.",
                "pain_points": "Hard to filter candidates by hourly rate and availability status.",
                "willingness_to_pay": "High (Subscribes to enterprise recruitment plans)",
                "key_delighter": "Rich, multi-page case study layouts showing detailed creative process.",
            },
        ],
        "monetization_friction": "Users dislike paywalls placed on portfolio customization and bugs around Adobe ID authentication gating account features.",
        "strategic_opportunity": "Fix mobile project uploading and biometric recovery; expand 0-fee client invoice generation directly within mobile.",
    },
    "spotify": {
        "company_name": "Spotify Technology S.A.",
        "net_worth": "$65+ Billion (Market Cap / NYSE: SPOT)",
        "annual_revenue": "$16.2 Billion ARR",
        "funding_stage": "Public Company (NYSE: SPOT)",
        "business_model_type": "Freemium Streaming Audio & Podcast Advertising",
        "primary_revenue_streams": [
            {"name": "Premium Paid Subscriptions", "share_pct": "87%", "description": "Ad-free recurring monthly subscriptions (Individual, Duo, Family, Student)."},
            {"name": "Ad-Supported Streaming & Audio Ads", "share_pct": "13%", "description": "Programmatic audio, video takeovers, and sponsored playlist insertions for free tier users."},
        ],
        "pricing_tiers": [
            {"tier": "Spotify Free", "price": "$0 (Ad-supported)", "target": "Casual music listeners willing to accept shuffle limitations."},
            {"tier": "Spotify Premium Individual", "price": "$11.99 / month", "target": "Daily commuters, students, and music power users."},
            {"tier": "Spotify Premium Family", "price": "$19.99 / month", "target": "Multi-user households with up to 6 individual profiles."},
        ],
        "target_personas": [
            {
                "name": "The Daily Commuter & Music Lover",
                "archetype": "Mass Consumer",
                "jtbd": "Seamless offline music playback, personalized Discover Weekly playlists, and background listening.",
                "pain_points": "Subscription price hikes and intrusive podcast recommendations cluttering the music tab.",
                "willingness_to_pay": "High ($11.99/mo for uninterrupted playback)",
                "key_delighter": "Spotify Wrapped and unmatched algorithmic music recommendations.",
            },
        ],
        "monetization_friction": "Recent subscription price increases and aggressive prompts urging free users to upgrade when trying to skip songs.",
        "strategic_opportunity": "Offer lower-cost audio-only tiers or student/family bundle flexibility to capture price-sensitive cohorts.",
    },
    "canva": {
        "company_name": "Canva Pty Ltd",
        "net_worth": "$26 Billion (Private Valuation)",
        "annual_revenue": "$2.3+ Billion ARR",
        "funding_stage": "Late-Stage Private (Pre-IPO)",
        "business_model_type": "Freemium Cloud Graphic Design SaaS & Print-on-Demand",
        "primary_revenue_streams": [
            {"name": "Canva Pro & Enterprise Subscriptions", "share_pct": "75%", "description": "Premium brand kits, AI magic studio tools, background remover, and cloud storage."},
            {"name": "Canva Print & Physical Merchandise", "share_pct": "18%", "description": "Direct print-on-demand fulfillment for business cards, flyers, apparel, and signage."},
            {"name": "Creator Marketplace Royalty Split", "share_pct": "7%", "description": "Commissions split with designers selling premium stock elements and templates."},
        ],
        "pricing_tiers": [
            {"tier": "Canva Free", "price": "$0", "target": "Casual social media creators and school students."},
            {"tier": "Canva Pro", "price": "$14.99 / month", "target": "Small business owners, solo marketers, and social media managers."},
            {"tier": "Canva for Teams / Enterprise", "price": "$30.00 / month (3 users)", "target": "Corporate marketing departments and agency collaboration teams."},
        ],
        "target_personas": [
            {
                "name": "The Small Business Owner & Solo Marketer",
                "archetype": "Non-Designer Professional",
                "jtbd": "Create professional social media flyers, menus, and banners in under 10 minutes without Photoshop.",
                "pain_points": "Accidentally selecting Pro elements on free tier and facing export paywalls.",
                "willingness_to_pay": "Medium-High ($15/mo saves hiring expensive agency)",
                "key_delighter": "One-click background remover, brand kits, and thousands of ready-to-use templates.",
            },
        ],
        "monetization_friction": "Increasing paywalling of previously free templates and AI Magic Studio credits.",
        "strategic_opportunity": "Introduce pay-as-you-go micro-transactions for single asset exports to monetize one-off users.",
    },
    "duolingo": {
        "company_name": "Duolingo, Inc.",
        "net_worth": "$8.2 Billion (Market Cap / NASDAQ: DUOL)",
        "annual_revenue": "$720+ Million ARR",
        "funding_stage": "Public Company (NASDAQ: DUOL)",
        "business_model_type": "Gamified Freemium EdTech & English Test Certification",
        "primary_revenue_streams": [
            {"name": "Super Duolingo / Duolingo Max Subscriptions", "share_pct": "78%", "description": "Unlimited hearts, ad-free experience, mistake review, and GPT-4 AI conversation practice."},
            {"name": "In-App Purchases (Gems, Streaks, Hearts)", "share_pct": "10%", "description": "Consumable gems to restore broken streaks and freeze loss penalties."},
            {"name": "Duolingo English Test (DET)", "share_pct": "8%", "description": "$59 online proctored English language certification accepted by 4,000+ universities."},
            {"name": "Free-tier Programmatic Ads", "share_pct": "4%", "description": "Short interstitial video ads shown between completed lessons."},
        ],
        "pricing_tiers": [
            {"tier": "Duolingo Free", "price": "$0 (Heart-limited)", "target": "Casual language learners."},
            {"tier": "Super Duolingo", "price": "$12.99 / month", "target": "Committed learners who want unlimited hearts and no ads."},
            {"tier": "Duolingo Max", "price": "$29.99 / month", "target": "Serious students wanting AI roleplay conversations and grammar explanations."},
        ],
        "target_personas": [
            {
                "name": "The Casual Habitual Learner",
                "archetype": "Consumer Habit Learner",
                "jtbd": "Build a daily 5-minute Spanish or Japanese habit without high classroom stress.",
                "pain_points": "Losing all hearts after making 3 mistakes and having lessons blocked.",
                "willingness_to_pay": "Low-to-Medium ($10-13/mo or tolerates ads)",
                "key_delighter": "Streak notifications, friendly gamification, and bite-sized lessons.",
            },
        ],
        "monetization_friction": "Heavy backlash over the heart system that blocks learning when making mistakes, forcing subscription upgrades.",
        "strategic_opportunity": "Offer soft practice modes that restore hearts through mini-quizzes rather than strictly gating sessions behind paywalls.",
    },
}


def generate_business_models_and_personas(app_results: Dict[str, Any], llm_client=None) -> Dict[str, Any]:
    """
    Generate business model teardown, company net worth / market cap,
    and user persona breakdowns for each analyzed app.
    """
    apps_data: Dict[str, Any] = {}
    app_names = [name for name, d in app_results.items() if not d.get("error")]

    for name in app_names:
        clean_key = name.lower()
        matched_intel = None

        # 1. Match known pre-baked intelligence
        for k, v in KNOWN_APP_BUSINESS_INTEL.items():
            if k in clean_key:
                matched_intel = dict(v)
                matched_intel["app_name"] = name
                break

        # 2. If not pre-baked and LLM is available, generate dynamic intelligence
        if not matched_intel and llm_client:
            try:
                prompt = f"""You are a Silicon Valley Product Manager and Tech Investment Analyst.
Analyze the business model and user personas for mobile app: "{name}".
Output a strict JSON object with this EXACT structure (no extra text):
{{
  "app_name": "{name}",
  "company_name": "Operating Company or Parent",
  "net_worth": "Estimated Market Cap or Private Valuation (e.g. $5 Billion)",
  "annual_revenue": "Estimated ARR or revenue scale",
  "funding_stage": "Public / Late-Stage Private / Subsidiary",
  "business_model_type": "Primary business model description (e.g. Freemium SaaS, Ad-supported, Transactional)",
  "primary_revenue_streams": [
    {{"name": "Stream 1", "share_pct": "70%", "description": "How they charge users or advertisers"}},
    {{"name": "Stream 2", "share_pct": "30%", "description": "Secondary monetization tier"}}
  ],
  "pricing_tiers": [
    {{"tier": "Free / Basic", "price": "$0", "target": "Casual users"}},
    {{"tier": "Premium / Pro", "price": "$9.99/mo", "target": "Power users"}}
  ],
  "target_personas": [
    {{
      "name": "Persona Title (e.g. The Everyday Creator)",
      "archetype": "User Category",
      "jtbd": "Core job to be done",
      "pain_points": "Key frustrations",
      "willingness_to_pay": "Low / Medium / High",
      "key_delighter": "What they love about the app"
    }},
    {{
      "name": "Persona Title 2",
      "archetype": "User Category 2",
      "jtbd": "Secondary job to be done",
      "pain_points": "Secondary friction",
      "willingness_to_pay": "High",
      "key_delighter": "Core value driver"
    }}
  ],
  "monetization_friction": "How monetization impacts user review complaints (ads, paywalls, price changes)",
  "strategic_opportunity": "Actionable product opportunity for a PM to improve conversion or retention"
}}"""
                raw = llm_client.complete("You are an expert tech financial and product management analyst. Return valid JSON only.", prompt)
                from llm_client import parse_json_response
                parsed = parse_json_response(raw)
                if isinstance(parsed, dict) and "business_model_type" in parsed:
                    matched_intel = parsed
                    matched_intel["app_name"] = name
            except Exception as e:
                print(f"Could not generate dynamic business model for {name}: {e}")

        # 3. Graceful fallback template if LLM is unavailable or for novel apps
        if not matched_intel:
            app_meta = app_results[name].get("meta", {})
            developer = app_meta.get("developer") or "Tech Publisher"
            matched_intel = {
                "app_name": name,
                "company_name": developer,
                "net_worth": "Estimated $500M - $5B+ Enterprise Value",
                "annual_revenue": "Estimated $100M+ Scale",
                "funding_stage": "Established Mobile Ecosystem Publisher",
                "business_model_type": "Freemium & In-App Digital Monetization",
                "primary_revenue_streams": [
                    {"name": "In-App Purchases & Digital Goods", "share_pct": "60%", "description": "Unlocks premium tools, enhanced credits, and feature extensions."},
                    {"name": "Subscription Membership Tier", "share_pct": "30%", "description": "Recurring monthly/annual tiers offering ad-free usage and priority access."},
                    {"name": "Programmatic Mobile Ads", "share_pct": "10%", "description": "Native in-feed advertising banners and video placements."},
                ],
                "pricing_tiers": [
                    {"tier": "Free Tier", "price": "$0", "target": "New and casual mobile users."},
                    {"tier": "Pro / Premium", "price": "$4.99 - $14.99 / mo", "target": "Power users needing unrestricted functionality."},
                ],
                "target_personas": [
                    {
                        "name": "The Everyday Mobile Power User",
                        "archetype": "Primary Consumer",
                        "jtbd": f"Accomplish core {name} tasks quickly with high reliability.",
                        "pain_points": "Intrusive paywalls and sudden subscription renewals.",
                        "willingness_to_pay": "Medium (Prefers value transparency)",
                        "key_delighter": "Fast app performance and intuitive layout.",
                    },
                    {
                        "name": "The High-Intent Professional",
                        "archetype": "B2B / Creator Cohort",
                        "jtbd": f"Leverage {name} workflows for professional output and sharing.",
                        "pain_points": "Account linking friction and sync errors.",
                        "willingness_to_pay": "High ($10-$20/mo)",
                        "key_delighter": "Cross-platform cloud sync and rich export options.",
                    },
                ],
                "monetization_friction": "Users express frustration when essential features are migrated behind paywalls without prior notice.",
                "strategic_opportunity": f"Create transparent pricing tiers and clear feature breakdowns to boost D30 conversion for {name}.",
            }

        apps_data[name] = matched_intel

    # Build Comparative Matrix
    matrix = []
    for name, data in apps_data.items():
        matrix.append({
            "app_name": name,
            "company": data.get("company_name", ""),
            "net_worth": data.get("net_worth", ""),
            "revenue": data.get("annual_revenue", ""),
            "model_type": data.get("business_model_type", ""),
            "primary_stream": data.get("primary_revenue_streams", [{}])[0].get("name", "Freemium"),
            "core_personas": ", ".join([p.get("name", "") for p in data.get("target_personas", [])]),
            "monetization_risk": data.get("monetization_friction", "")[:120] + "...",
        })

    # Summary synthesis
    summary_lines = []
    for name, data in apps_data.items():
        summary_lines.append(f"- **{name} ({data.get('company_name')}):** Valuation/Net Worth at **{data.get('net_worth')}**. Driven primarily by *{data.get('business_model_type')}*.")
    summary_text = "\n".join(summary_lines)

    return {
        "apps": apps_data,
        "matrix": matrix,
        "summary": summary_text,
    }
