# shortlist_bot — CHANGELOG

> **Intent:** Warm leads who already have a B.Tech shortlist. Confirm / update shortlist → nudge primary application (currently GNIOT Greater Noida) → optional new colleges → more recommendations → counselling-call conversion.
>
> **Audience temperature:** Warm / engaged. Already responded to specific institutes.
>
> **Bot persona:** Neha, female counsellor from Delhi, conversational Hinglish.

---

## Version log

Each version pairs a system prompt + (eventually) a call flow diagram. Use this log to track what changed and why so A/B test results stay interpretable.

### Template (copy for each new version)

```
### vN — YYYY-MM-DD — <one-line summary>

**Files:** vN_system_prompt.md (+ vN_call_flow.md if added)
**Based on:** vN-1
**Hypothesis:** What you're testing / why this variant exists.

**Changes vs previous:**
- ...

**Known limitations / open questions:**
- ...

**Eval results:** (link to eval/reports/... or paste headline metrics)
```

---

### v0 — 2026-05-01 — Original draft (archived)

**Files:** [v0_original_system_prompt.md](v0_original_system_prompt.md)
**Based on:** —
**Notes:** First-pass prompt as Rohan was running it before the structural rewrite. Kept for diffing / regression reference. Should NOT be used in production.

---

### v1 — 2026-05-01 — Structural rewrite, aligned with `recommend_colleges/v1` conventions

**Files:** [v1_system_prompt.md](v1_system_prompt.md), [v1_call_flow.md](v1_call_flow.md)
**Based on:** v0
**Hypothesis:** A cleaner numbered-section structure with explicit non-negotiable rules and a single fixed opener will improve Flash Lite's instruction-following on warm leads, without changing the conversion funnel.

**Key design choices:**
- **Section structure** matches `recommend_colleges/v1`: non-negotiables → role → language → tools → caller → flow → output → examples → USER CONTEXT.
- **Single fixed opener** (Roman-script Hinglish, verbatim, no personalisation). Original had Devanagari mid-sentence which TTS + LLM both handled inconsistently.
- **6-step flow:** Open → Confirm shortlist (mandatory `get_preferred_institutes` call) → Application nudge (GNIOT, with `application_step_completed` token) → New target colleges → Recommendations → Counselling call.
- **Application token rule** explicit: emit ONCE at end of Step 3, never again.
- **Tool-empty fallback** on `get_preferred_institutes`: pivot to asking the user directly instead of inventing.
- **Configuration note** on Step 3: primary target college (GNIOT) and application window are flagged as the swap-points for new campaigns.
- **USER CONTEXT** moved to end with the same "absent OR empty = missing" rule as recommend_colleges. Explicit instruction: trust the tool over USER CONTEXT for shortlist.
- **Examples section** added (good + bad), including specific failure modes from v0 (token-double-emit, inventing colleges, Devanagari mid-sentence, step-combining).

**Known limitations / open questions:**
- GNIOT Greater Noida is hardcoded as the application target. Should eventually be parameterised via USER CONTEXT (e.g. `Primary application target:` field) so this prompt isn't campaign-specific.
- No call-flow diagram yet — would help when comparing to recommend_colleges visually.
- The opener doesn't use the user's known shortlist for rapport (intentional, per Flash Lite reliability concerns) — worth A/B-ing once core flow is stable.
- No qualification (JEE / 12th) — by design, since this audience has already committed enough to shortlist. If shortlist confirmation rate stays low, may want to test adding light qualification before the application nudge.

**Eval results:** TBD
