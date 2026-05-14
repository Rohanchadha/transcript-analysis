"""
FastAPI application for Shiksha Counsellor Call Insights Dashboard.
Loads pre-computed analysis results and serves an interactive dashboard.

Usage:
  cd transcript-insights
  python -m uvicorn app.main:app --reload
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
APP_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Shiksha Transcript Insights")
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")

# ---------------------------------------------------------------------------
# Global data store — loaded once on startup
# ---------------------------------------------------------------------------
store: dict = {"transcripts": [], "analysis": [], "agg": {}}


def _safe(obj) -> str:
    """Return a JSON string safe for embedding in <script> tags."""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


# ---------------------------------------------------------------------------
# Data loading & aggregation
# ---------------------------------------------------------------------------
def load_data():
    analysis_path = DATA_DIR / "analysis_results.json"
    parsed_path = DATA_DIR / "parsed_transcripts.json"
    usps_path = DATA_DIR / "institute_usps.json"

    if parsed_path.exists():
        with open(parsed_path, "r", encoding="utf-8") as f:
            store["transcripts"] = json.load(f)

    if analysis_path.exists():
        with open(analysis_path, "r", encoding="utf-8") as f:
            store["analysis"] = json.load(f)

    if usps_path.exists():
        with open(usps_path, "r", encoding="utf-8") as f:
            store["institute_usps"] = json.load(f)

    deep_dive_path = DATA_DIR / "deep_dive_insights.json"
    if deep_dive_path.exists():
        with open(deep_dive_path, "r", encoding="utf-8") as f:
            store["deep_dive"] = json.load(f)

    aggregate_data()


def _classify_college_info(query_text: str) -> str:
    """Classify a 'College Information' query into a finer sub-bucket."""
    q = query_text.lower()
    rules = [
        ("Fee Structure & Cost", ["fee", "lakh", "cost", "budget", "paisa", "kitna padega",
                                   "charge", "scholarship", "price", "rupee", "free hai",
                                   "paid", "hostel fee", "affordable", "cheap", "expensive",
                                   "low fee", "kitna lagega"]),
        ("Placement & Packages", ["placement", "package", "lpa", "salary", "recruit", "job",
                                   "company", "hire", "career", "placed", "highest package",
                                   "average package", "opportunity", "package kitna"]),
        ("College Ranking & Reviews", ["ranking", "rating", "review", "reputation", "kaisa hai",
                                        "kaisa college", "badhiya", "acch", "reputed", "brand",
                                        "worth", "concern", "doubt", "how is", "haal hai",
                                        "soch rahi", "comparison", "compare", "better hai",
                                        "vs", "versus"]),
        ("Application & Forms", ["apply", "form", "registration", "fill", "test date",
                                  "exam date", "deadline", "interview", "process", "admission",
                                  "dale hain", "bhar rahe"]),
        ("Location & Campus", ["location", "kahan pe", "kahan hai", "campus", "infrastructure",
                                "city", "surrounding", "hospital", "tie-up", "where",
                                "mumbai", "pune", "delhi", "bangalore", "chennai",
                                "taraf", "mein hai"]),
        ("College Recommendations", ["suggest", "recommend", "kaun se college", "which college",
                                      "option", "list de", "alag college", "koi aur",
                                      "target kar", "dekh rahe", "shortlist", "naam suna",
                                      "colleges hain", "baare mein", "ke bare mein",
                                      "ke liye inquiry", "college details"]),
    ]
    for sub_name, keywords in rules:
        if any(kw in q for kw in keywords):
            return sub_name
    return "Other College Queries"


def aggregate_data(counsellor_filter: str | None = None) -> dict:
    """Compute aggregations across all analysis records.

    If `counsellor_filter` is set, only records whose `metadata.counsellor_name`
    matches (case-insensitive) are included. The unfiltered result is also
    cached in `store["agg"]`.
    """
    all_analysis = store["analysis"]
    if counsellor_filter:
        cf = counsellor_filter.strip().lower()
        all_records = [
            r for r in all_analysis
            if (r.get("metadata") or {}).get("counsellor_name", "").lower() == cf
        ]
    else:
        all_records = all_analysis

    results = [r for r in all_records if r.get("analysis")]
    a: dict = {}

    # ---- Overview ----------------------------------------------------------
    a["total_calls"] = len(all_records)
    a["analyzed_calls"] = len(results)

    durations = [r["metadata"]["duration"] for r in results if r.get("metadata")]
    a["avg_duration"] = round(sum(durations) / max(len(durations), 1), 1)
    a["total_duration_mins"] = round(sum(durations) / 60, 1)
    a["min_duration"] = round(min(durations, default=0), 1)
    a["max_duration"] = round(max(durations, default=0), 1)

    # Distributions
    a["stages"] = dict(Counter(
        r["metadata"]["stage_name"] for r in results if r.get("metadata")
    ).most_common())
    a["teams"] = dict(Counter(
        r["metadata"]["team_name"] for r in results if r.get("metadata")
    ).most_common())
    a["counsellors"] = dict(Counter(
        r["metadata"]["counsellor_name"] for r in results if r.get("metadata")
    ).most_common())

    course_counter = Counter()
    for r in results:
        c = r["analysis"]["student_profile"].get("course_interest", "")
        if c and c.lower() not in ("not_mentioned", "n/a", "unknown", ""):
            course_counter[c] += 1
    a["courses"] = dict(course_counter.most_common(15))

    a["outcomes"] = dict(Counter(
        r["analysis"]["call_outcome"]["primary_outcome"] for r in results
    ).most_common())

    a["caller_types"] = dict(Counter(
        r["analysis"]["student_profile"].get("caller_type", "unclear") for r in results
    ).most_common())

    # Decision stages
    a["decision_stages"] = dict(Counter(
        r["analysis"]["student_profile"].get("decision_stage", "unknown") for r in results
    ).most_common())

    # Build transcript lookup for speaker attribution
    transcript_map: dict = {}
    for t in store["transcripts"]:
        transcript_map[t["id"]] = t

    # ---- Query Buckets -----------------------------------------------------
    bucket_data: dict[str, list] = defaultdict(list)
    for r in results:
        tr = transcript_map.get(r["id"])
        counsellor_texts = set()
        if tr:
            for turn in tr.get("turns", []):
                if turn["speaker"] == "Counsellor":
                    counsellor_texts.add(turn["text"].lower().strip())

        for q in r["analysis"].get("query_buckets", []):
            quote = q.get("quote", "").strip()
            # Skip queries whose quote is actually from the Counsellor
            if quote and counsellor_texts:
                q_lower = quote[:40].lower()
                if any(q_lower in ct or ct.startswith(q_lower[:25]) for ct in counsellor_texts):
                    continue

            entry = {
                "query": q.get("query", ""),
                "quote": q.get("quote", ""),
                "translation": q.get("translation", ""),
                "call_id": r["id"],
                "counsellor": r["metadata"]["counsellor_name"] if r.get("metadata") else "Unknown",
            }
            bucket = q["bucket"]
            if bucket == "College Information":
                bucket = _classify_college_info(
                    entry["query"] + " " + entry.get("translation", "")
                )
            bucket_data[bucket].append(entry)

    a["query_buckets"] = {
        bucket: {"count": len(items), "examples": items}
        for bucket, items in sorted(bucket_data.items(), key=lambda x: -len(x[1]))
    }

    # ---- Tactics -----------------------------------------------------------
    tactic_data: dict[str, list] = defaultdict(list)
    for r in results:
        for t in r["analysis"].get("counsellor_tactics", []):
            tactic_data[t["tactic"]].append({
                "description": t.get("description", ""),
                "quote": t.get("quote", ""),
                "translation": t.get("translation", ""),
                "call_id": r["id"],
                "counsellor": r["metadata"]["counsellor_name"] if r.get("metadata") else "Unknown",
            })

    a["tactics"] = {
        tactic: {
            "count": len(items),
            "pct": round(len(items) / max(len(results), 1) * 100, 1),
            "examples": items,
        }
        for tactic, items in sorted(tactic_data.items(), key=lambda x: -len(x[1]))
    }

    # ---- Objections --------------------------------------------------------
    obj_data: dict[str, list] = defaultdict(list)
    for r in results:
        for o in r["analysis"].get("objections", []):
            obj_data[o.get("objection_type", "other")].append({
                "objection": o.get("objection", ""),
                "handling": o.get("handling_strategy", ""),
                "student_quote": o.get("student_quote", ""),
                "counsellor_quote": o.get("counsellor_quote", ""),
                "resolved": o.get("was_resolved", False),
                "call_id": r["id"],
                "counsellor": r["metadata"]["counsellor_name"] if r.get("metadata") else "Unknown",
            })

    a["objections"] = {
        otype: {
            "count": len(items),
            "resolution_rate": round(
                sum(1 for e in items if e["resolved"]) / max(len(items), 1) * 100, 1
            ),
            "examples": items,
        }
        for otype, items in sorted(obj_data.items(), key=lambda x: -len(x[1]))
    }

    # ---- Colleges ----------------------------------------------------------
    college_counter: Counter = Counter()
    college_details: dict = defaultdict(lambda: {"fees": [], "placements": [], "reactions": Counter()})
    for r in results:
        for c in r["analysis"].get("colleges_discussed", []):
            name = c["name"]
            college_counter[name] += 1
            fee = c.get("fee_mentioned", "")
            plc = c.get("placement_mentioned", "")
            if fee and fee.lower() != "not_mentioned":
                college_details[name]["fees"].append(fee)
            if plc and plc.lower() != "not_mentioned":
                college_details[name]["placements"].append(plc)
            college_details[name]["reactions"][c.get("student_reaction", "not_mentioned")] += 1

    a["colleges"] = {
        name: {
            "count": cnt,
            "fees": college_details[name]["fees"][:3],
            "placements": college_details[name]["placements"][:3],
            "reactions": dict(college_details[name]["reactions"]),
        }
        for name, cnt in college_counter.most_common(25)
    }

    # ---- Call Flow ---------------------------------------------------------
    phase_order = [
        "Opening & Rapport",
        "Lead Qualification",
        "Need Discovery",
        "College Recommendations",
        "Objection Handling",
        "Application Push",
        "Closing & Next Steps",
    ]
    phase_counts: Counter = Counter()
    for r in results:
        for p in r["analysis"].get("call_flow_phases", []):
            if p.get("happened"):
                phase_counts[p["phase"]] += 1

    a["call_flow"] = {
        phase: {
            "count": phase_counts.get(phase, 0),
            "pct": round(phase_counts.get(phase, 0) / max(len(results), 1) * 100, 1),
        }
        for phase in phase_order
    }

    # ---- Direct Admissions & Management Quota ------------------------------
    import re
    DA_KEYWORDS = [
        # English
        "direct admission", "direct entry", "management quota",
        "management seat", "mgmt quota", "donation seat",
        "capitation", "without entrance",
        # Hindi / Hinglish
        "direct admission", "management quota",
        "management seat", "bina entrance", "bina exam",
        "donation se", "sidha admission", "seedha admission",
        "management se", "quota se admission",
    ]
    # Build a single regex (case-insensitive) for efficient matching
    _da_pattern = re.compile(
        "|".join(re.escape(kw) for kw in DA_KEYWORDS), re.IGNORECASE
    )

    da_calls: list[dict] = []
    keyword_counter: Counter = Counter()

    for r in all_records:
        tr = transcript_map.get(r["id"])
        if not tr:
            continue

        # Search every turn for keyword matches
        matched_turns: list[dict] = []
        call_keywords: set = set()
        for idx, turn in enumerate(tr.get("turns", [])):
            matches = _da_pattern.findall(turn["text"])
            if matches:
                normalised = {m.lower() for m in matches}
                call_keywords.update(normalised)
                # Include ±2 surrounding turns for context
                ctx_start = max(0, idx - 2)
                ctx_end = min(len(tr["turns"]), idx + 3)
                context_turns = [
                    {
                        "speaker": t["speaker"],
                        "text": t["text"],
                        "time": t.get("start_time", ""),
                        "is_match": bool(_da_pattern.search(t["text"])),
                    }
                    for t in tr["turns"][ctx_start:ctx_end]
                ]
                matched_turns.append({
                    "turn_index": idx,
                    "speaker": turn["speaker"],
                    "text": turn["text"],
                    "time": turn.get("start_time", ""),
                    "keywords_found": sorted(normalised),
                    "context": context_turns,
                })

        # Also check analysis text (summary, queries, objections) for extra signal
        analysis_mentions: list[dict] = []
        if r.get("analysis"):
            an = r["analysis"]
            # Summary
            if _da_pattern.search(an.get("summary", "")):
                analysis_mentions.append({
                    "source": "summary",
                    "text": an["summary"],
                })
            # Query buckets
            for q in an.get("query_buckets", []):
                combined = f'{q.get("query","")} {q.get("quote","")} {q.get("translation","")}'
                if _da_pattern.search(combined):
                    analysis_mentions.append({
                        "source": "student_query",
                        "text": q.get("translation") or q.get("query", ""),
                        "quote": q.get("quote", ""),
                        "bucket": q.get("bucket", ""),
                    })
            # Objections
            for o in an.get("objections", []):
                combined = f'{o.get("objection","")} {o.get("handling_strategy","")} {o.get("student_quote","")} {o.get("counsellor_quote","")}'
                if _da_pattern.search(combined):
                    analysis_mentions.append({
                        "source": "objection",
                        "text": o.get("objection", ""),
                        "handling": o.get("handling_strategy", ""),
                        "student_quote": o.get("student_quote", ""),
                        "counsellor_quote": o.get("counsellor_quote", ""),
                    })

        if matched_turns or analysis_mentions:
            for kw in call_keywords:
                keyword_counter[kw] += 1

            meta = r.get("metadata") or {}
            entry = {
                "id": r["id"],
                "counsellor": meta.get("counsellor_name", "Unknown"),
                "team": meta.get("team_name", "Unknown"),
                "duration": meta.get("duration", 0),
                "stage": meta.get("stage_name", "Unknown"),
                "course": r["analysis"]["student_profile"].get("course_interest", "N/A") if r.get("analysis") else "N/A",
                "outcome": r["analysis"]["call_outcome"]["primary_outcome"] if r.get("analysis") else "unknown",
                "summary": r["analysis"].get("summary", "") if r.get("analysis") else "",
                "keywords_found": sorted(call_keywords),
                "matched_turns": matched_turns,
                "analysis_mentions": analysis_mentions,
                "colleges_discussed": [
                    c["name"] for c in (r["analysis"].get("colleges_discussed", []) if r.get("analysis") else [])
                ],
            }
            da_calls.append(entry)

    # Who initiates the topic more — student or counsellor?
    speaker_counter: Counter = Counter()
    for call in da_calls:
        for mt in call["matched_turns"]:
            speaker_counter[mt["speaker"]] += 1

    a["direct_admissions"] = {
        "total_flagged": len(da_calls),
        "pct_of_calls": round(len(da_calls) / max(len(all_records), 1) * 100, 1),
        "keyword_breakdown": dict(keyword_counter.most_common()),
        "initiated_by": dict(speaker_counter.most_common()),
        "calls": da_calls,
    }

    # ---- Bot Learnings -----------------------------------------------------
    learnings: list[str] = []
    for r in results:
        learnings.extend(r["analysis"].get("bot_learnings", []))
    a["bot_learnings"] = learnings

    # ---- Call List (for explorer) ------------------------------------------
    # Build gender lookup from deep_dive data
    gender_lookup = {}
    if store.get("deep_dive"):
        for gr in store["deep_dive"].get("gender_raw", []):
            gender_lookup[gr["id"]] = gr.get("gender", {}).get("student_gender", "unclear")

    # Batches whose users are confirmed to have applied (downstream conversion known)
    APPLIED_BATCHES = {"batch-may-14th-may"}
    # _batch lives on parsed_transcripts (not analysis_results); build id -> batch lookup
    batch_by_id = {t["id"]: t.get("_batch") for t in store.get("transcripts", []) if t.get("id")}

    call_list = []
    for r in all_records:
        m = r.get("metadata") or {}
        # created_on looks like "2026-04-30 21:51:42"; keep date prefix for filtering
        created_full = m.get("created_on", "") or ""
        created_date = created_full[:10] if len(created_full) >= 10 else ""
        entry = {
            "id": r["id"],
            "counsellor": m.get("counsellor_name") or "Unknown",
            "team": m.get("team_name") or "Unknown",
            "duration": m.get("duration") or 0,
            "stage": m.get("stage_name") or "Unknown",
            "user_id": str(m.get("user_id") or ""),
            "mobile": str(m.get("mobile_number") or ""),
            "created_on": created_full,
            "created_date": created_date,
            "applied": batch_by_id.get(r["id"]) in APPLIED_BATCHES,
            "total_turns": r.get("stats", {}).get("total_turns", 0),
            "counsellor_words": r.get("stats", {}).get("counsellor_words", 0),
            "user_words": r.get("stats", {}).get("user_words", 0),
            "student_gender": gender_lookup.get(r["id"], "unclear"),
        }
        if r.get("analysis"):
            an = r["analysis"]
            entry["course"] = an["student_profile"].get("course_interest", "N/A")
            entry["outcome"] = an["call_outcome"]["primary_outcome"]
            entry["summary"] = an.get("summary", "")
            entry["buckets"] = list({q["bucket"] for q in an.get("query_buckets", [])})
            entry["tactics_used"] = list({t["tactic"] for t in an.get("counsellor_tactics", [])})
            entry["caller_type"] = an["student_profile"].get("caller_type", "unclear")
            entry["colleges"] = list({c["name"] for c in an.get("colleges_discussed", []) if c.get("name")})
        else:
            entry.update(course="N/A", outcome=r.get("skip_reason", "error"),
                         summary="Not analyzed", buckets=[], tactics_used=[], caller_type="unknown", colleges=[])
        call_list.append(entry)
    a["call_list"] = call_list

    # ---- Users aggregation: group calls by user_id (or mobile fallback) ----
    users_map: dict = {}
    for c in call_list:
        # Prefer user_id; fall back to mobile so anonymous calls still group
        key = c.get("user_id") or ("mob:" + c["mobile"] if c.get("mobile") else "")
        if not key:
            continue
        u = users_map.setdefault(key, {
            "user_id": c.get("user_id") or "",
            "mobile": c.get("mobile") or "",
            "calls": [],
            "call_ids": [],
            "total_duration": 0.0,
            "stages": set(),
            "counsellors": set(),
            "teams": set(),
            "courses": set(),
            "outcomes": set(),
            "latest_date": "",
            "earliest_date": "",
        })
        u["calls"].append(c)
        u["call_ids"].append(c["id"])
        try:
            u["total_duration"] += float(c.get("duration") or 0)
        except (TypeError, ValueError):
            pass
        if c.get("stage") and c["stage"] != "Unknown":
            u["stages"].add(c["stage"])
        if c.get("counsellor") and c["counsellor"] != "Unknown":
            u["counsellors"].add(c["counsellor"])
        if c.get("team") and c["team"] != "Unknown":
            u["teams"].add(c["team"])
        if c.get("course") and c["course"] not in ("N/A", "not_mentioned", ""):
            u["courses"].add(c["course"])
        if c.get("outcome"):
            u["outcomes"].add(c["outcome"])
        d = c.get("created_date") or ""
        if d:
            if not u["latest_date"] or d > u["latest_date"]:
                u["latest_date"] = d
            if not u["earliest_date"] or d < u["earliest_date"]:
                u["earliest_date"] = d

    users_list = []
    for u in users_map.values():
        # Latest stage = stage of the call with the most recent created_on (proxy for current funnel position)
        sorted_calls = sorted(u["calls"], key=lambda x: x.get("created_on", ""), reverse=True)
        latest_stage = sorted_calls[0]["stage"] if sorted_calls else "Unknown"
        users_list.append({
            "user_id": u["user_id"],
            "mobile": u["mobile"],
            "call_count": len(u["calls"]),
            "total_duration": round(u["total_duration"], 2),
            "stages": sorted(u["stages"]),
            "latest_stage": latest_stage,
            "counsellors": sorted(u["counsellors"]),
            "teams": sorted(u["teams"]),
            "courses": sorted(u["courses"]),
            "outcomes": sorted(u["outcomes"]),
            "latest_date": u["latest_date"],
            "earliest_date": u["earliest_date"],
            "call_ids": u["call_ids"],
        })
    # Sort: most calls first, then most recent
    users_list.sort(key=lambda x: (-x["call_count"], x["latest_date"]), reverse=False)
    users_list.sort(key=lambda x: (x["call_count"], x["latest_date"]), reverse=True)
    a["users"] = users_list

    # ---- Attach institute USPs (optionally filtered by counsellor) --------
    usps = store.get("institute_usps", {})
    if counsellor_filter and usps:
        # Build set of transcript IDs belonging to this counsellor
        allowed_ids = {r["id"] for r in all_records}
        a["institute_usps"] = _filter_institute_usps(usps, allowed_ids)
    elif usps:
        a["institute_usps"] = usps

    # ---- Attach deep-dive insights (optionally filtered) ------------------
    dd = store.get("deep_dive", {})
    if dd:
        if counsellor_filter:
            a["deep_dive"] = _filter_deep_dive(dd, all_records, counsellor_filter)
        else:
            a["deep_dive"] = {
                "urgency_analysis": dd.get("urgency_analysis", {}),
                "gender_analysis": dd.get("gender_analysis", {}),
            }

    if counsellor_filter:
        return a

    store["agg"] = a
    return a


def _filter_institute_usps(usps: dict, allowed_call_ids: set) -> dict:
    """Filter institute USPs to only include data sourced from given call IDs."""
    filtered: dict = {}
    for name, inst in usps.items():
        # Filter pitch_points and fee_details by source_call
        new_pp = [pp for pp in inst.get("pitch_points", [])
                  if pp.get("source_call") in allowed_call_ids]
        new_fees = [f for f in inst.get("fee_details", [])
                    if f.get("source_call") in allowed_call_ids]
        # Drop institutes the counsellor never mentioned
        if not new_pp and not new_fees:
            continue
        new_inst = dict(inst)
        new_inst["pitch_points"] = new_pp
        new_inst["fee_details"] = new_fees
        # Recompute mention_count as # of distinct allowed source calls touching this institute
        sources = {pp.get("source_call") for pp in new_pp} | {f.get("source_call") for f in new_fees}
        new_inst["mention_count"] = len([s for s in sources if s])
        filtered[name] = new_inst
    # Sort by mention_count desc to preserve original ordering convention
    return dict(sorted(filtered.items(), key=lambda kv: -kv[1].get("mention_count", 0)))


def _filter_deep_dive(dd: dict, records: list, counsellor_filter: str) -> dict:
    """Filter deep_dive insights to a single counsellor.

    - urgency_examples: filter by counsellor name (case-insensitive)
    - with_urgency / without_urgency stats: recomputed from filtered records
    - gender_analysis: pass-through (aggregated, not filterable cleanly)
    """
    cf = counsellor_filter.strip().lower()
    urg_in = dd.get("urgency_analysis", {}) or {}
    examples = urg_in.get("urgency_examples", []) or []
    filtered_examples = [
        ex for ex in examples
        if (ex.get("counsellor", "") or "").strip().lower() == cf
    ]

    # Recompute urgency_types breakdown
    type_counts: Counter = Counter()
    for ex in filtered_examples:
        t = ex.get("urgency_type") or ex.get("type") or "other"
        type_counts[t] += 1

    # Calls with at least one urgency mention (within this counsellor's calls)
    urgency_call_ids = {ex.get("call_id") for ex in filtered_examples if ex.get("call_id")}
    with_records = [r for r in records if r["id"] in urgency_call_ids and r.get("analysis")]
    without_records = [r for r in records if r["id"] not in urgency_call_ids and r.get("analysis")]

    def _stats(recs):
        n = len(recs)
        if n == 0:
            return {"count": 0, "application_rate": 0, "whatsapp_rate": 0}
        apps = sum(1 for r in recs if r["analysis"]["call_outcome"].get("application_started"))
        wa = sum(1 for r in recs if r["analysis"]["call_outcome"].get("whatsapp_handoff"))
        return {
            "count": n,
            "application_rate": round(apps / n * 100, 1),
            "whatsapp_rate": round(wa / n * 100, 1),
        }

    urg_out = {
        "key_finding": urg_in.get("key_finding", ""),
        "urgency_types": dict(type_counts.most_common()),
        "urgency_examples": filtered_examples,
        "with_urgency": _stats(with_records),
        "without_urgency": _stats(without_records),
    }
    return {
        "urgency_analysis": urg_out,
        "gender_analysis": dd.get("gender_analysis", {}),
    }


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def startup():
    load_data()


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
@app.get("/")
async def index(request: Request):
    selected = (request.query_params.get("counsellor") or "").strip()
    if selected:
        agg = aggregate_data(counsellor_filter=selected)
    else:
        agg = store["agg"]

    # Build the canonical counsellor list (with call counts) from the unfiltered cache.
    counts = store["agg"].get("counsellors") or {}
    counsellor_list = [
        {"name": name, "count": count}
        for name, count in sorted(counts.items(), key=lambda kv: kv[0].lower())
    ]

    return templates.TemplateResponse(
        name="index.html",
        request=request,
        context={
            "data_json": Markup(_safe(agg)),
            "counsellors": counsellor_list,
            "selected_counsellor": selected,
        },
    )


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------
@app.get("/api/overview")
async def api_overview():
    a = store["agg"]
    return {k: a.get(k) for k in (
        "total_calls", "analyzed_calls", "avg_duration", "total_duration_mins",
        "min_duration", "max_duration", "stages", "teams", "counsellors",
        "courses", "outcomes", "caller_types", "decision_stages",
    )}


@app.get("/api/query-buckets")
async def api_query_buckets():
    return store["agg"].get("query_buckets", {})


@app.get("/api/tactics")
async def api_tactics():
    return store["agg"].get("tactics", {})


@app.get("/api/objections")
async def api_objections():
    return store["agg"].get("objections", {})


@app.get("/api/call-flow")
async def api_call_flow():
    return store["agg"].get("call_flow", {})


@app.get("/api/colleges")
async def api_colleges():
    return store["agg"].get("colleges", {})


@app.get("/api/calls")
async def api_calls():
    return store["agg"].get("call_list", [])


@app.get("/api/users")
async def api_users():
    return store["agg"].get("users", [])


@app.get("/api/calls/{call_id:path}")
async def api_call_detail(call_id: str):
    for r in store["analysis"]:
        if r["id"] == call_id:
            transcript = next(
                (t for t in store["transcripts"] if t["id"] == call_id), None
            )
            return {"analysis": r, "transcript": transcript}
    return JSONResponse({"error": "Not found"}, status_code=404)


@app.get("/api/bot-playbook")
async def api_bot_playbook():
    a = store["agg"]
    return {
        "learnings": a.get("bot_learnings", []),
        "top_queries": a.get("query_buckets", {}),
        "top_objections": a.get("objections", {}),
        "call_flow": a.get("call_flow", {}),
        "colleges": a.get("colleges", {}),
    }


@app.get("/api/institute-usps")
async def api_institute_usps():
    return store.get("institute_usps", {})


@app.get("/api/direct-admissions")
async def api_direct_admissions():
    return store["agg"].get("direct_admissions", {})


@app.get("/api/institute-usps/{college_name:path}")
async def api_institute_usp_detail(college_name: str):
    usps = store.get("institute_usps", {})
    # Exact match first
    if college_name in usps:
        return usps[college_name]
    # Case-insensitive search
    key_lower = college_name.lower()
    for name, data in usps.items():
        if name.lower() == key_lower:
            return data
        # Check aliases
        if any(a.lower() == key_lower for a in data.get("aliases", [])):
            return data
    return JSONResponse({"error": "Institute not found"}, status_code=404)
