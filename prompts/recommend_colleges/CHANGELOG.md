# recommend_colleges — CHANGELOG

> **Intent:** B.Tech aspirants (cold/exploring leads). Collect JEE Main + 12th + location → recommend 2 colleges → offer free counselling call.
>
> **Audience temperature:** Cold / discovery-stage. May or may not have a prior shortlist.
>
> **Bot persona:** Neha, female counsellor from Delhi, conversational Hinglish.

---

## Version log

Each version pairs a system prompt + call flow diagram. Use this log to track what changed and why so A/B test results stay interpretable.

### Template (copy for each new version)

```
### vN — YYYY-MM-DD — <one-line summary>

**Files:** vN_system_prompt.md, vN_call_flow.md
**Based on:** vN-1
**Hypothesis:** What you're testing / why this variant exists.

**Changes vs previous:**
- ...
- ...

**Known limitations / open questions:**
- ...

**Eval results:** (link to eval/reports/... or paste headline metrics)
```

---

### v1 — 2026-05-01 — Initial production prompt

**Files:** [v1_system_prompt.md](v1_system_prompt.md), [v1_call_flow.md](v1_call_flow.md)
**Based on:** —
**Hypothesis:** Baseline. A structured 5-step Hinglish flow with score-based branching can convert cold B.Tech leads to a counselling-call booking without sounding like a form.

**Key design choices:**
- B.Tech-only qualification (JEE Main + 12th); no CUET/BITSAT/state CETs.
- Single fixed opener (no personalisation from USER CONTEXT) — small model couldn't reliably follow conditional opener variants.
- Score-based branching (Cases A/B/C) with thresholds: A<85, B>95 JEE / >90 12th, C mixed.
- "Result not out" → ask expected score; "didn't give exam" → skip silently, no preaching.
- Removed shortlist-confirmation step (was Step 5 in earlier drafts) — felt redundant with recommendations.
- Soft backup pitch when user is uninterested before close.
- 5 steps total: Open → Qualify → Recommend → New target colleges → Counselling call.

**Known limitations / open questions:**
- Step 4 (new target colleges) sits awkwardly between Recommendations and Counselling-call offer. Worth testing if dropping/merging it improves conversion.
- USER CONTEXT richer fields (`Previously shown interest in`, `Exam previously responded to`) currently unused in opener — may revisit if model can be steered reliably.
- Section 8 examples reference older threshold labels in some cases.

**Eval results:** TBD
