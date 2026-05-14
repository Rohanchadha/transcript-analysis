# Goals: Transcript Intelligence → Voice Bot

## Why This Exists

Shiksha.com has hundreds of human counsellors making thousands of calls daily to students and parents exploring college admissions. These counsellors have deep, intuition-driven expertise — they know which colleges to pitch for which student profile, how to handle fee objections, when to create urgency, and how to read a parent's anxiety vs a student's confusion.

**This project extracts that intelligence systematically** — turning unstructured Hindi/Hinglish phone conversations into structured, actionable data that powers an AI admissions voice bot.

The thesis: **the best training data for an admissions bot isn't synthetic — it's what real counsellors actually say in real calls.**

---

## What We've Learned So Far

### From 100 calls analyzed:

**How counsellors qualify leads:**
- Structured sequence: Course → Exam scores → Category → Location → Budget (in that order)
- Top counsellors complete all 7 call phases; weaker ones skip Need Discovery or Objection Handling
- Average talk ratio is 2.5x (counsellor talks 2.5x more than student) — top converters talk less

**What students ask most:**
- Fee structure & costs dominate (~30% of queries)
- Placement & packages are the #2 concern
- Entrance exam eligibility ("NEET mein kitne chahiye?") is a major anxiety driver
- College recommendations ("kaun sa college accha hai?") come up when students are overwhelmed

**How counsellors sell colleges:**
- Tiered recommendations: dream school + realistic option + safety (2-3 colleges)
- Placement Data Anchoring: lead with "highest package 53 lakh" — students anchor on the number
- Urgency Creation: "application deadline next week", "only 5 seats left"
- Friction Removal: free applications, coupon codes, "I'll help you fill the form"

**What blocks conversions:**
- Budget concerns (most common, ~60% resolution rate)
- Exam anxiety ("meri NEET ki taiyari nahi hai")
- Quality doubt ("is college ka placement kaisa hai really?")
- Location preference conflicts
- Parent vs student disagreements

**Institute intelligence:**
- 200 unique institutes extracted across 100 calls
- Amity leads with 23 mentions, 48 USPs, 14 fee data points
- Counsellors have clear favorites per course — B.Tech defaults to Amity/Chandigarh/NIET; BDS to Kalinga/SOA
- Fee claims and placement stats are the primary pitch levers

---

## What's Next

### Phase 1: Deeper Transcript Analysis (current)
- [ ] **Parent vs Student communication patterns** — segment by caller_type, compare tactics/outcomes/objections
- [ ] **Counsellor performance benchmarking** — score each counsellor on conversion, tactic diversity, resolution rate
- [ ] **Course-specific selling patterns** — how pitch differs for B.Tech vs BDS vs Nursing vs MBA
- [ ] **Gender-aware communication analysis** — infer gender from Hindi cues, check if counsellors pitch differently
- [ ] **Emotional journey mapping** — per-turn sentiment to identify "turning points" in successful calls
- [ ] **Decision stage funnel analysis** — what tactics work at each stage (exploring → comparing → ready → applied)

### Phase 2: Voice Bot Knowledge Base
- [ ] **Institute USPs tool** — structured JSON per college for bot to query in real-time (from institute_usps.json)
- [ ] **Objection handling playbook** — pattern-matched responses by objection type + student profile
- [ ] **Fee comparison tool** — cross-college fee comparison by course
- [ ] **Eligibility checker** — exam cutoff + category → eligible colleges

### Phase 3: Continuous Evaluation
- [ ] **Golden test pipeline** — auto-extract new test cases as more calls are analyzed
- [ ] **Regression testing** — run eval suite on every bot update, track scores over time
- [ ] **A/B dimension analysis** — which scoring dimensions improve/degrade with changes
- [ ] **Human-in-the-loop validation** — counsellors review bot responses, flag hallucinations

### Phase 4: Scale
- [ ] Process 500+ calls (more counsellors, more teams, more courses)
- [ ] Regional analysis (Delhi vs North vs East vs South teams)
- [ ] Seasonal patterns (peak admission season vs off-season)
- [ ] Multi-turn evaluation (full call simulation, not just single-turn Q&A)

---

## Success Metrics for the Voice Bot

### Accuracy
- **Factual accuracy ≥ 4.0/5.0** on golden fact tests (no hallucinated fees/placements)
- **Hallucination score ≥ 4.5/5.0** (near-zero invented data)
- **Institute USP coverage ≥ 80%** of colleges counsellors actually recommend

### Experience
- **Tone & empathy ≥ 4.0/5.0** — appropriate for anxious students and concerned parents
- **Actionability ≥ 4.0/5.0** — every response ends with a clear next step
- **Objection acknowledgment ≥ 4.0/5.0** — never dismisses a concern

### Conversion
- **Application push rate** comparable to median human counsellor
- **WhatsApp handoff rate** — bot should achieve similar follow-up conversion
- **Student satisfaction** (measured via post-call survey or callback rate)

### Operational
- **Response latency < 2s** for voice bot (real-time constraint)
- **Hindi/Hinglish fluency** — natural code-switching, not robotic Hindi
- **Graceful fallback** — knows when to hand off to human counsellor

---

## Key Insight

The gap isn't in what the bot knows — it's in **how it knows to say it**. A counsellor doesn't just recite fees; they anchor on placement data first, then present fees as an investment, then remove friction with free applications. The sequence matters as much as the content.

This project exists to capture that sequence — the *how* of selling, not just the *what*.
