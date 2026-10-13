# 📱 Google Play Store App Analyser & Competitive Intelligence Studio

An end-to-end competitive intelligence studio and agent that scrapes Google Play Store reviews, analyzes customer sentiment, evaluates PM dimension scorecards, compares **business models, company net worth & user personas**, and generates executive-ready PRDs and stakeholder reports — with a clean Google Material Design 3 interface.

---

## 🚀 Key Features

### 1. 🔍 Free Real-Time Play Store Scraping
- Scrapes reviews directly via Play Store package IDs (e.g., `com.pinterest`, `com.behance.behance`, `com.spotify.music`) or full Play Store URLs.
- Filter reviews by recency (last 90 days) with configurable depths (15, 50, 100, 200 reviews).
- Automatic icon and metadata extraction with multi-layer fallback resolution.

### 2. 💼 Business Models, Net Worth & User Personas (New)
- **Company Scale & Net Worth / Valuation:** Track and compare live market cap or enterprise valuations (e.g., Pinterest ~$21B+, Behance / Adobe ~$210B+, Spotify ~$65B+, Canva ~$26B+).
- **Business Model Archetype:** Categorizes revenue models (Ad-supported, Freemium SaaS, Marketplace commissions, In-App digital purchases).
- **Primary Revenue Streams:** Itemized percentage share and mechanics.
- **Pricing & Tier Structure:** Free vs Pro vs Enterprise breakdown with target audiences.
- **Main User Personas:** Distinct user cohorts detailing:
  - Role & Archetype
  - 🎯 **Jobs-to-be-Done (JTBD)**
  - ⚠️ **Key Pain Points**
  - 💳 **Willingness to Pay** (Low / Medium / High)
  - ✨ **Key Delighters**
- **Review Monetization Friction:** Identifies real user pushback regarding paywalls, ads, or subscription price changes.
- **Strategic Growth PM Opportunities:** Concrete recommendations to increase monetization without hurting user retention.

### 3. 📊 PM Dimension Scorecards & Competitive Scoring
- Ranks competitor apps from 0–100 across 5 core PM dimensions:
  - **UX Quality & Onboarding**
  - **Performance & Stability**
  - **Pricing & Fee Transparency**
  - **Customer Support Responsiveness**
  - **Mobile & Third-Party Integration**

### 4. 🔥 Pain Points Heatmap & Fee Transparency Audit
- Automatic severity tagging (High $\ge$ 15%, Medium 5–14%, Low < 5%) across negative review categories.
- Dedicated fee transparency score and pricing complaint extractor.

### 5. 🔍 Feature Parity & Delighters Matrix
- Cross-competitor feature satisfaction benchmark.
- Delighters gallery showcasing quotes users rave about.
- "Top Requested Features" wishlist extracted from customer reviews.

### 6. 📈 Sentiment Distribution & Velocity Tracking
- Interactive Chart.js visualizations for sentiment breakdown (Positive, Neutral, Negative %).
- 1★ to 5★ star distribution benchmarks.
- Monthly review volume and acceleration trajectory.

### 7. 🤖 Local TF-IDF + Gemini AI RAG Search
- High-speed local vector retrieval over customer reviews.
- Ask free-form questions (e.g., *"Which app has better customer support?"*) synthesized with real customer quote evidence.

### 8. 📄 Interactive PRD & Stakeholder Email Studio
- **1-Click PRD Generator:** Produces markdown Product Requirement Documents complete with problem statements, user stories, acceptance criteria, KPIs, and phased rollouts.
- **Stakeholder Email Drafter:** Tailors executive summaries for Leadership, Engineering, Design, or Growth teams.

---

## 🎨 Design & User Experience
- Built with **Google Material Design 3** aesthetics and Google Play Store colors (`#01875f` Play Green, clean `#f8f9fa` canvas, white elevated cards, and Google Sans / Roboto typography).
- Starts with a clean, distraction-free input screen — no preloaded mock data.
- Referrer-policy headers ensuring external app store icons load without CDN blocking.

---

## 📁 Project Architecture

```
agent-app-store-scrapper/
├── app_server.py             ← Main Flask server (REST API, SSE real-time streaming & web app)
├── pm_intelligence.py        ← Business models, net worth, personas, scorecards, PRDs & emails
├── rag_engine.py             ← TF-IDF retrieval + LLM synthesis engine
├── llm_client.py             ← Multi-provider LLM factory (Gemini, Groq, Mistral, Ollama, Claude)
├── database.py               ← Historical JSON time-series storage
├── skill_loader.py           ← Dynamic skill discovery and tool mapping
├── skills/
│   ├── play_store_scraper.py ← Google Play reviews and metadata scraper with alias resolver
│   ├── sentiment_analyzer.py ← LLM-driven sentiment categorization
│   ├── feature_extractor.py  ← Feature extraction and request detector
│   ├── competitive_scorer.py ← 0-100 algorithmic competitor scoring
│   ├── gap_finder.py         ← Market whitespace and feature gap detector
│   └── trend_analyzer.py     ← Directional sentiment trajectory
├── static/
│   ├── index.html            ← Full Google Material Design Intelligence Studio
│   └── dashboard.html        ← 5-tab historical trend viewer
├── requirements.txt          ← Python dependencies
└── start.sh                  ← Startup script
```

---

## ⚡ Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/modignani95-wq/Playstore-app-analyser.git
cd Playstore-app-analyser
```

### 2. Set Up Virtual Environment (Recommended)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Add your free Gemini API key (or Groq/Mistral):
```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
DASHBOARD_PORT=5000
```

### 5. Start the Application
```bash
python app_server.py
```
Open your browser at:
👉 **http://localhost:5000**

---

## ⚙️ Environment Configuration

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `gemini` | LLM backend: `gemini` / `groq` / `mistral` / `ollama` / `claude` |
| `GEMINI_API_KEY` | — | Required if using Google Gemini |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Model identifier |
| `GROQ_API_KEY` | — | Required if using Groq |
| `DASHBOARD_PORT` | `5000` | Local web server port |
| `MAX_REVIEWS_PER_APP` | `50` | Default review depth per app |

---

## 📄 License
MIT License. Free to use, customize, and extend.
