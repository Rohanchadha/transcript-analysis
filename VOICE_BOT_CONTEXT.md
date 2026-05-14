# Voice Bot Project — Context Snapshot

> Quick orientation doc. As of May 2026.

---

## 1. The North Star

Build an **AI admissions voice bot** ("Neha") for Shiksha.com that speaks like a real human counsellor on a phone call — warm, Hinglish, conversational — and moves students through the admissions funnel (qualify → recommend → handle objections → push application / counselling-call).

---

## 2. Bot Personas & Prompt Tracks (`prompts/`)

| Track | Purpose | Status |
|---|---|---|
| `recommend_colleges/` | Cold/lukewarm leads — qualify (JEE/12th) then recommend colleges | v1, v2a/b/c experiments |
| `shortlist_bot/` | Warm leads who **already** have a B.Tech shortlist — confirm shortlist → nudge primary application (currently GNIOT) → expand → counselling call | active focus, on **v1.02-urgency** |
| `voice_bot_system_prompt.md` | Top-level non-negotiable rules (name = Neha, length, language, no tool-name leaks, etc.) | source of truth for `voicebot/` rule-based detectors |

**Persona is constant across tracks:** Neha, female counsellor from Delhi, Roman-script Hinglish, one question per turn, ≤2 sentences, no bullet lists, sounds spoken.

**Versioning convention:** every prompt version pairs a `vN_system_prompt.md` with a `vN_call_flow.md`, logged in `CHANGELOG.md` with hypothesis + changes + eval results. Don't edit old versions — fork to a new `vN`.

---

## 3. Lead Cohorts & Routing

Every lead is classified into one of Shiksha's internal **cohorts** based on their prior responses. The cohort determines which call flow / nodes the bot uses, and a per-lead **`HOT` flag** is set when the cohort's hot-marking condition is met.

| # | Cohort | Definition | Hot-marking logic |
|---|---|---|---|
| 1 | **Shortlist Responders** | Responded on ≥ 2 colleges (at least 1 client college) | NA — already hot |
| 2 | **Client Responders** | Responded on a client college | `baseCourseConfirmed = TRUE` |
| 3 | **College Responders (Private)** | Responded on a private college | `baseCourseConfirmed = TRUE` |
| 4 | **College Responders (Government)** | Responded on a government college | `openToPrivateColleges = TRUE` |
| 5 | **Exam Responders (Private)** | Responded on a private exam | `baseCourseConfirmed = TRUE` |
| 6 | **Exam Responders (Government)** | Responded on a government exam | `openToPrivateColleges = TRUE` |

**Implications for prompts:**
- The two flags above (`baseCourseConfirmed`, `openToPrivateColleges`) are the *gates* the bot has to drive each cohort through — they're what turn a lead HOT.
- Government-cohort leads (4 & 6) need a soft pivot to private options before they can convert.
- Cohort should be passed in via `USER CONTEXT` so the bot can pick the right opener / flow without asking redundant qualifying questions.

---

## 4. Lead Score → Priority

Every lead also carries a **Lead Score**:

| Score | Priority | Behavioural difference |
|---|---|---|
| **≥ 70** | High priority | Full flow — including the **Free Human Counselling Call** offer |
| **< 70** | Low priority | Same flow, **but never offer the Free Human Counselling Call** |

This is the only flow-level branch the bot needs to make on score. Everything else (qualification, recommendations, objection handling) is identical across priorities.

---

## 5. Active Experiment: `shortlist_bot/v1.02-urgency`

- **Audience:** warm B.Tech leads who responded to specific institutes already.
- **Flow:** Open → confirm shortlist (mandatory `get_preferred_institutes` call) → nudge GNIOT application (emit `application_step_completed` token *once*) → new target colleges → recommendations → counselling call.
- **Hypothesis being tested:** adding urgency cues without breaking conversational warmth.
- **Known caveats:** GNIOT hardcoded as application target (should be parameterised); no light qualification step (by design — audience already committed).

---

## 6. Eval Setup (`eval/`)

- **Golden tests:** queries, facts, objections.
- **Judge:** GPT-4o-mini, structured rubric.
- **Dimensions:** factual accuracy (×3), hallucination (×3), relevance (×2), completeness (×2), tone & empathy (×1.5), actionability (×1.5). Objection tests add: acknowledgment (×2), conversation continuation (×2).
- Run with `python eval/run_eval.py`; reports land in `eval/reports/`.

---

## 7. Issue Detection on Live Bot Calls (`voicebot/`)

Independent FastAPI app + scripts. Pulls bot-call logs from prod MySQL (with optional SSH tunnel via `RCB_*` env vars), parses, detects ~18 issue categories per turn — mix of deterministic rules (latency, name violation, length violation, tool-name leak, premature recommendation) and LLM judgments (hallucination, frustration, failed handoff, tone).

This is what tells us *"the prompt change shipped on Tuesday is causing more topic_deviation"* without waiting for an eval rerun.

Dashboard runs on **port 8001**.

---

## 8. Success Targets (from `goals.md`)

- Factual accuracy ≥ 4.0 / 5; hallucination ≥ 4.5 / 5
- Tone & empathy ≥ 4.0; actionability ≥ 4.0; objection acknowledgment ≥ 4.0
- Latency < 2s per turn
- Application-push and WhatsApp-handoff rates comparable to median human counsellor

---

## 9. Where Things Live (TL;DR)

```
prompts/                ← bot system prompts (the product)
  recommend_colleges/   ← cold-lead track
  shortlist_bot/        ← warm-lead track (active)
  voice_bot_system_prompt.md  ← global non-negotiables

eval/                   ← golden tests + judge + reports

voicebot/               ← live bot-call issue dashboard (port 8001)
  scripts/              ← pull_calls, parse_calls, detect_issues
  data/                 ← raw_calls, parsed_calls, issues (gitignored)

goals.md                ← roadmap + thesis
```

---

## 10. Operating Principles (Rohan-flavoured)

- **Sharp MVP > feature creep.** Demo-ability matters — the "aha moment" is the bot sounding like Neha, not a fancy admin UI.
- **Buyer ≠ user.** Admission managers configure; counsellors hand off; students/parents are on the call. Design for all three.
- **First pilot is Shiksha.** "First sales call is a Slack message." Don't over-engineer for hypothetical customers.
- **Voice-first.** Not a chatbot retrofitted to TTS. Prompt rules (length, one-question-per-turn, Roman Hinglish) reflect that.
