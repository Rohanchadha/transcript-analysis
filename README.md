# 📞 Shiksha Transcript Insights

**Turning 100 real counsellor calls into intelligence for building a smarter admissions voice bot.**

This project analyzes transcripts from Shiksha.com counsellor calls — extracting how human counsellors qualify students, pitch colleges, handle objections, and drive applications. The output feeds directly into building and evaluating an AI voice bot for college admissions.

---

## Architecture

```
Raw HTML Transcripts (100 calls, Hindi/Hinglish)
        │
        ▼
┌─────────────────────┐
│  parse_transcripts   │  → Turn-by-turn dialogue + word stats + metadata
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ analyze_transcripts  │  → GPT-4o-mini structured extraction:
│                     │     student profile, query buckets, tactics,
│                     │     objections, colleges, outcomes, call flow
└─────────┬───────────┘
          │
          ├──▶ Dashboard (FastAPI + Tailwind)
          │     8 tabs: Overview, Queries, Tactics, Objections,
          │     Call Flow, Explorer, Institute USPs, Bot Playbook
          │
          ├──▶ Golden Test Extraction
          │     query_tests, fact_tests, objection_tests
          │
          ├──▶ Institute USP Extraction
          │     200 institutes, pitch points, fees, placements
          │
          └──▶ Eval Framework
                Judge (GPT-4o-mini) + Rubric scoring
                against human counsellor reference responses
```

---

## Quick Start

```bash
# Clone and install
git clone https://github.com/Rohanchadha/transcript-analysis.git
cd transcript-analysis
pip install -r requirements.txt

# Run dashboard
python -m uvicorn app.main:app --reload --port 8000
# Open http://localhost:8000
```

The dashboard loads pre-computed analysis from `data/`. No API key needed to view.

---

## Pipeline Scripts

All scripts read from `data/` and support incremental processing (skip already-processed transcripts).

### 1. Parse Transcripts
```bash
python scripts/parse_transcripts.py
```
Reads HTML transcript files from `transcript/`, extracts speaker turns with timestamps, computes word stats and talk ratios. Links metadata from the CSV. Outputs `data/parsed_transcripts.json`.

### 2. Analyze Transcripts
```bash
$env:OPENAI_API_KEY = "sk-..."   # or use .env file
python scripts/analyze_transcripts.py
```
Sends each transcript through GPT-4o-mini (JSON mode, temp=0.3) to extract:
- **Student profile**: course interest, exam scores, category, location, budget, decision stage, caller type
- **Query buckets**: 10 categories (College Info, Fees, Exams, Placements, etc.)
- **Counsellor tactics**: 14 identified behaviors (Rapport Building, Tiered Recommendation, Urgency Creation, etc.)
- **Objections**: 10 types with handling strategies and resolution tracking
- **Colleges discussed**: name, location, fees, placements, recommendation status, student reaction
- **Call outcome**: application started, WhatsApp handoff, callback scheduled
- **Call flow phases**: 7 phases from Opening to Closing

Outputs `data/analysis_results.json`. Saves checkpoints every 5 transcripts.

### 3. Extract Institute USPs
```bash
python scripts/extract_institute_usps.py
```
Re-processes transcripts with a USP-focused prompt to extract detailed pitch intelligence per college:
- **Pitch points**: exact selling points with Hindi quotes + English translations
- **Fee details**: amount, type (management quota/scholarship/per year), course-specific
- **Placement details**: highest/avg packages, placement %, top recruiters
- **Differentiators**: hospital tie-ups, campus, rankings, accreditations
- **Recommendation context**: why counsellors pick this college

Outputs `data/institute_usps_raw.json` (per-call) and `data/institute_usps.json` (aggregated by institute, 200 unique institutes).

---

## Dashboard

**8 interactive tabs** powered by Chart.js + Tailwind CSS:

| Tab | What it shows |
|-----|--------------|
| **📊 Overview** | Total calls, durations, outcomes, courses, caller types, teams, counsellors |
| **❓ Query Buckets** | Student question taxonomy (10 categories + sub-categories) with real Hindi quotes |
| **🎯 Counsellor Playbook** | 14 tactics with usage %, examples, and bot tips |
| **🛡️ Objection Handling** | 10 objection types, resolution rates, counsellor scripts, bot suggestions |
| **🔄 Call Flow** | 7-phase funnel (Opening → Qualification → Discovery → Recommend → Handle → Apply → Close) |
| **🔍 Transcript Explorer** | Searchable call list — click any row to read full transcript + analysis |
| **🏫 Institute USPs** | 200 institutes with pitch points, fees, placements. Course filter pills, collapsible cards |
| **🤖 Bot Playbook** | Aggregated recommendations: call flow, top queries, college knowledge base, learnings |

---

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/overview` | Aggregate stats: calls, durations, distributions |
| `GET /api/query-buckets` | Query taxonomy with counts and examples |
| `GET /api/tactics` | Counsellor tactics with usage % and quotes |
| `GET /api/objections` | Objection types, resolution rates, examples |
| `GET /api/call-flow` | Phase occurrence percentages |
| `GET /api/colleges` | Top 25 colleges with fees, placements, reactions |
| `GET /api/calls` | Full call list with summaries |
| `GET /api/calls/{id}` | Single call: full transcript + analysis |
| `GET /api/bot-playbook` | Aggregated bot training data |
| `GET /api/institute-usps` | All 200 institutes with USP data |
| `GET /api/institute-usps/{name}` | Single institute lookup (supports alias matching) |

---

## Evaluation Framework

Test your voice bot against real human counsellor conversations.

### Golden Test Extraction
```bash
python eval/golden_tests/extract_test_cases.py
```
Extracts 3 test suites from analyzed calls:
- **Query tests**: Real student questions (Hindi) + reference counsellor responses
- **Fact tests**: College fee/placement claims → expected answers
- **Objection tests**: Student objections + handling strategies + resolution status

### Run Evaluation
```bash
$env:OPENAI_API_KEY = "sk-..."
$env:BOT_API_URL = "https://your-bot.example.com/chat"
python eval/run_eval.py [--type query|fact|objection] [--limit N]
```

### Scoring Rubric (GPT-4o-mini Judge)

| Dimension | Weight | What it measures |
|-----------|--------|-----------------|
| Factual Accuracy | 3.0 | College fees, placements, cutoffs correct? |
| Hallucination | 3.0 | Invented colleges, fees, or data? |
| Relevance | 2.0 | Answered the actual question? |
| Completeness | 2.0 | Covered what the human counsellor covered? |
| Tone & Empathy | 1.5 | Appropriate for anxious student/parent? |
| Actionability | 1.5 | Clear next step given? |
| Objection Acknowledgment* | 2.0 | Acknowledged concern before responding? |
| Conversation Continuation* | 2.0 | Kept conversation going? |

*Objection tests only. Scale: 1-5 per dimension. Weighted average → final score.

### Call Simulation
```bash
python eval/simulator/simulate_call.py
```
Generates synthetic student personas and call scenarios for edge-case testing.

---

## Data Assets

| Asset | Count | Description |
|-------|-------|-------------|
| Raw transcripts | 100 | Hindi/Hinglish counsellor calls (HTML with timestamps) |
| Analyzed calls | ~95 | Structured extraction (profile, tactics, objections, colleges) |
| Unique institutes | 200 | With pitch points, fees, placements from counsellor conversations |
| Counsellor tactics | 14 | Documented behaviors with examples and bot tips |
| Objection types | 10 | With resolution rates and handling scripts |
| Query categories | 10+ | With sub-categories and real Hindi quotes |
| Golden test cases | 3 suites | Query, fact, and objection tests from real calls |

---

## Deploy to Render

The project includes `render.yaml` for one-click deploy:

1. Push repo to GitHub
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo — Render auto-detects `render.yaml`
4. Deploy. Dashboard is live at `https://your-app.onrender.com`

Production uses `requirements-deploy.txt` (no OpenAI dependency — analysis is pre-computed).

---

## Tech Stack

- **Backend**: FastAPI + Jinja2
- **Frontend**: Tailwind CSS (CDN) + Chart.js + vanilla JS
- **LLM**: OpenAI GPT-4o-mini (JSON mode, temp=0.3)
- **Data**: Pre-computed JSON files (no database)
- **Deploy**: Render (free tier)
- **Language**: Python 3.12

---

## Project Structure

```
transcript-insights/
├── app/
│   ├── main.py                  # FastAPI app + aggregation logic
│   ├── templates/index.html     # Dashboard SPA
│   └── static/{css,js}/         # Tailwind overrides + dashboard JS
├── scripts/
│   ├── parse_transcripts.py     # HTML → structured turns
│   ├── analyze_transcripts.py   # GPT-4o-mini analysis
│   └── extract_institute_usps.py # Institute USP extraction
├── eval/
│   ├── run_eval.py              # Test runner + judge orchestration
│   ├── golden_tests/
│   │   └── extract_test_cases.py
│   ├── runner/
│   │   ├── judge.py             # GPT-4o-mini judge
│   │   └── rubric.py            # Scoring dimensions + weights
│   └── simulator/
│       └── simulate_call.py     # Synthetic call generation
├── data/
│   ├── parsed_transcripts.json
│   ├── analysis_results.json
│   ├── institute_usps.json      # Aggregated per-institute
│   └── institute_usps_raw.json  # Per-call extractions
├── transcript/                  # 100 raw HTML transcripts
├── render.yaml                  # Render deploy config
├── requirements.txt             # Dev dependencies
└── requirements-deploy.txt      # Production dependencies
```
