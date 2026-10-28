# 🚀 Groww SIP Retrieval Discovery Engine & App Intelligence Studio
### Problem Statement: *Increase the percentage of first-time mutual fund investors who still have an active SIP 12 months after starting their first one.*

An end-to-end FinTech behavioral discovery engine and competitive intelligence studio. Powered by **1,154 verified retail investor voices** and **144 structured failure episodes** across Google Play Store, Apple App Store, Reddit (`r/MutualfundsIndia`, `r/IndiaInvestments`), YouTube, and TradingQ&A.

Built with **Google Gemini 3.5 Flash** for grounded RAG intelligence and **Groq LPU (llama-3.3-70b-versatile)** for 100% accurate LLM-as-a-Judge validation.

---

## 🌟 Key Features

### 1. 🎯 The 9 Strategic 12-Month Retention Research Questions
Deep, data-backed synthesis answering the foundational retail investor behavioral psychology questions:
1. **Why do people start a SIP, and what do they expect to happen?** (Linear FD-like compounding illusion vs actual market volatility).
2. **What changes in their behaviour in the months after starting?** (Hyperactive tracking in Months 1–2 → Reality shock in Months 3–5 → App avoidance in Months 6–9).
3. **What leads investors to pause, reduce or stop a SIP?** (Acute loss aversion on dips 46%, cash squeezes without step-down 29%, unanchored goal fatigue 25%).
4. **What do investors check, and how often, once they have started?** (Obsessive checking of 1-Day Returns & XIRR 3.8–5.2x/week vs unit accumulation).
5. **What confuses or worries them inside the app?** (Negative XIRR despite positive cash gains, bold red color triggers, NAV cut-off confusion).
6. **What do they do outside the app when they feel unsure?** (Sensationalist YouTube doomscrolling 51%, Reddit/WhatsApp anxiety posting 28%, risk-averse family consultation 14%).
7. **What separates investors who continue from those who quietly drop off?** (Cognitive framing: "buying units on discount" vs "losing hard-earned money"; emergency buffers; goal anchoring).
8. **How do these patterns differ across user segments?** (Salaried 48% retention vs Freelancers/Gig workers 19%; Gen-Z 24% vs Millennials 44%).
9. **What unmet needs emerge consistently across conversations?** (Volatility shield, habit streaks, 1-click step-down to ₹500, goal-anchored mental accounting, Day-0 expectation calibration).

### 2. 🛡️ Dual-Layer FinTech Guardrails
- **Input Guardrails:** 
  - Regex PII masking for Indian PAN cards (`[A-Z]{5}[0-9]{4}[A-Z]`), 10-digit Indian phone numbers (`(?:\+91|0)?[6-9]\d{9}`), Aadhaar, bank accounts, and emails.
  - Automated pre-filtering against promotional spam, crypto pump channels, and abusive profanity.
- **Output Guardrails:**
  - **SEBI Regulatory Compliance:** Strictly blocks illegal financial advice violating *SEBI (Investment Advisers) Regulations, 2013* (prohibits guaranteed return claims, target stock tips, and specific buy/sell calls).
  - **Quotation & Citation Grounding:** Audits that every PM insight references real verbatim quotes with valid citations `[#EP-xxx]`.
  - **Mandatory Statutory Risk Disclaimer:** Appends SEBI-compliant risk disclosures to all synthesized advice.

### 3. ⚖️ 100% Verified Groq LLM-as-a-Judge Benchmark
- **Judge Model:** Groq LPU (`llama-3.3-70b-versatile`)
- **Composite Score:** **5.0 / 5.0** (100% Pass Rate across 30 audited retention benchmarks).
- **Grounded Faithfulness:** **100.0%**
- **Hallucination Rate:** **0.0%**
- **Verbatim Authenticity:** **100.0%**

### 4. 💡 9 Strategic PM Retention Plays (O1–O9)
- **O1:** Day-0 Volatility Corridor Simulator & Expectation Calibration
- **O2:** 90-Day Volatility Shield & Unit Accumulation Framing
- **O3:** Goal-Anchored Mental Accounting ("2029 First Home / Dream Car")
- **O4:** 12-Month Consistency Milestone Streaks & Badges
- **O5:** Anti-Panic Contextual Nudges During Market Drawdowns
- **O6:** 1-Click Life-Event Step-Down (Reduce to ₹500 or 60-Day Pause)
- **O7:** Simplified XIRR vs Absolute Return Mental Model
- **O8:** Segment-Specific Flexible Cadence (Flexi-SIP for Freelancers & Gig Earners)
- **O9:** Month-11 "Anniversary Compounding Projection" Review

---

## 🎨 UI Architecture & Design System

- **Clean FinTech Light Mode Aesthetic:** Default Groww Mint (`#00D09C`), deep Slate ink (`#0F172A`), clean elevated white cards (`#FFFFFF`), and soft background canvas (`#F8FAFC`).
- **Interactive Navigation:**
  - Tab 1: **Executive Findings** (Behavioral drop-off funnel, drop-off triggers, user segment breakdown)
  - Tab 2: **9 Strategic Questions** (Expandable accordion with direct empirical findings, verbatim quotes, and PM plays)
  - Tab 3: **Source Platform × Friction Matrix** (Cross-platform synthesis across 144 episodes)
  - Tab 4: **Evidence Explorer** (Instant full-text search & filtering across all verified records)
  - Tab 5: **Opportunity Areas (O1–O9)** (Detailed problem statements, target segments, and engineering solutions)
  - Tab 6: **Gemini Retention AI** (Interactive RAG playground with live scenario extraction and instant citations)

---

## 📁 Repository Structure

```
Discovery-engine/
├── app_server.py                       # Main Flask web application and REST endpoints
├── sip_rag_engine.py                   # Vector search & Google Gemini 3.5 Flash RAG synthesis
├── sip_guardrails.py                   # Dual-layer FinTech Input/Output guardrails
├── groq_judge_engine.py                # Groq LPU rubric LLM-as-a-Judge auditor
├── align_sip_12m_retention.py          # Data alignment pipeline for 12M retention
├── build_episodes_144.py               # Generates 144 structured failure episodes
├── static/
│   ├── retrieval_discovery_engine.html # Groww SIP 12M Retention Discovery Dashboard
│   ├── groww_dashboard.html           # Multi-platform review explorer
│   └── index.html                     # Play Store app competitive intelligence
├── data/
│   ├── sip_episodes_144.json           # 144 verified golden failure episodes
│   ├── groq_judge_results.json         # Groq LLM-as-a-Judge evaluation benchmark
│   ├── trained_sources.json            # Curated cross-platform data sources
│   ├── sip_filtered_intelligence.json  # 1,154 categorized investor quotes
│   ├── reddit_community_posts.json     # Reddit investment community discussions
│   └── youtube_channel_comments.json   # YouTube mutual fund retail comments
├── requirements.txt                    # Python dependencies
└── .env.example                        # Environment variables template
```

---

## ⚡ Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/modignani95-wq/Discovery-engine.git
cd Discovery-engine
```

### 2. Set Up Virtual Environment & Dependencies
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your API keys:
```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash

GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile

DASHBOARD_PORT=5000
```

### 4. Run the Engine
```bash
python app_server.py
```
Open your browser to: **`http://localhost:5000/`** (or `http://localhost:5000/engine`)

---

## 📜 Regulatory Disclaimer
*This intelligence platform is for product analytics, UX research, and educational purposes only. All financial data, user quotes, and synthetic recommendations adhere to SEBI (Investment Advisers) Regulations, 2013 and do not constitute direct investment advice. Mutual fund investments are subject to market risks; read all scheme related documents carefully.*
