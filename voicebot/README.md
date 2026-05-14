# Voice-Bot Transcript Issue Dashboard

Standalone module for analyzing **voice-bot** (Neha) call transcripts pulled from
the production DB. Fully isolated from the human-counsellor transcript-insights
pipeline in the parent project.

## Pipeline

```
MySQL DB ──▶ pull_calls.py ──▶ data/raw_calls.json
                                      │
                                      ▼
                              parse_calls.py
                                      │
                                      ▼
                            data/parsed_calls.json
                                      │
                                      ▼
                             detect_issues.py
                            (rules + GPT-4o-mini)
                                      │
                                      ▼
                              data/issues.json
                                      │
                                      ▼
                       FastAPI dashboard (port 8001)
```

## Setup

```powershell
# from repo root
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r voicebot/requirements.txt
```

Add to `.env` at repo root:

```
OPENAI_API_KEY="sk-..."

# SSH tunnel (optional — set if DB is only reachable via bastion)
RCB_SSH_HOST="192.168.x.x"
RCB_SSH_PORT=22
RCB_SSH_USER="..."
RCB_SSH_PASS="..."

# MySQL (host/port as seen FROM the bastion if tunneled, else direct)
RCB_DB_HOST="127.0.0.1"
RCB_DB_PORT=3310
RCB_DB_USER="..."
RCB_DB_PASS="..."
RCB_DB_NAME="counselling"

# Comma-separated counsellor_id list
RCB_COUNSELLOR_IDS="12345678"
```

## Usage

```powershell
# 1. Pull calls (incremental on call_sid)
python voicebot/scripts/pull_calls.py --limit 100

# Alternative: skip DB and use a local JSON/CSV dump
python voicebot/scripts/pull_calls.py --from-file path/to/dump.json

# 2. Parse the rich `info` JSON column (transcriptV2, latency, ASR confidence)
python voicebot/scripts/parse_calls.py

# 3. Detect issues (deterministic rules + LLM)
python voicebot/scripts/detect_issues.py

# 4. Run dashboard on port 8001 (does not collide with the human-call dashboard on 8000)
python -m uvicorn voicebot.app.main:app --port 8001 --reload
```

Open <http://localhost:8001>.

## Issue Categories

Detected per turn and rolled up per call:

| Category | Source |
|---|---|
| `unanswered_query` | LLM |
| `topic_deviation` | LLM |
| `repetition_loop` | rule + LLM |
| `asr_intent_breakdown` | rule (Deepgram confidence) + LLM |
| `student_frustration` | LLM |
| `hallucination` | LLM |
| `premature_recommendation` | rule (college mentioned before JEE % + 12th %) |
| `failed_handoff` | LLM |
| `tone_empathy` | LLM |
| `latency_perceived` | rule (turn > 3s, avg > 2.5s) |
| `name_violation` | rule (says any name other than "Neha") |
| `length_violation` | rule (>2 sentences or >1 question per turn) |
| `tool_name_leak` | rule |
| `shuddh_hindi` | rule (uses Devanagari for blocked words) |
| `closing_phrase_missing` | rule |
| `recommended_without_qualification` | rule |
| `early_dropoff` | rule |
| `user_confusion_marker` | rule |

Rule definitions are derived from the NON-NEGOTIABLE RULES in
`prompts/voice_bot_system_prompt.md`.

## Data Files

All written to `voicebot/data/` (gitignored):

- `raw_calls.json` — DB rows (one per call_sid)
- `parsed_calls.json` — normalized turns + metadata
- `issues.json` — detected issues per call
