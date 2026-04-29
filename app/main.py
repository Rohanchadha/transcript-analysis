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


def aggregate_data():
    results = [r for r in store["analysis"] if r.get("analysis")]
    all_records = store["analysis"]
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

    # ---- Bot Learnings -----------------------------------------------------
    learnings: list[str] = []
    for r in results:
        learnings.extend(r["analysis"].get("bot_learnings", []))
    a["bot_learnings"] = learnings

    # ---- Call List (for explorer) ------------------------------------------
    call_list = []
    for r in all_records:
        entry = {
            "id": r["id"],
            "counsellor": r["metadata"]["counsellor_name"] if r.get("metadata") else "Unknown",
            "team": r["metadata"]["team_name"] if r.get("metadata") else "Unknown",
            "duration": r["metadata"]["duration"] if r.get("metadata") else 0,
            "stage": r["metadata"]["stage_name"] if r.get("metadata") else "Unknown",
            "total_turns": r.get("stats", {}).get("total_turns", 0),
            "counsellor_words": r.get("stats", {}).get("counsellor_words", 0),
            "user_words": r.get("stats", {}).get("user_words", 0),
        }
        if r.get("analysis"):
            an = r["analysis"]
            entry["course"] = an["student_profile"].get("course_interest", "N/A")
            entry["outcome"] = an["call_outcome"]["primary_outcome"]
            entry["summary"] = an.get("summary", "")
            entry["buckets"] = list({q["bucket"] for q in an.get("query_buckets", [])})
            entry["tactics_used"] = list({t["tactic"] for t in an.get("counsellor_tactics", [])})
            entry["caller_type"] = an["student_profile"].get("caller_type", "unclear")
        else:
            entry.update(course="N/A", outcome=r.get("skip_reason", "error"),
                         summary="Not analyzed", buckets=[], tactics_used=[], caller_type="unknown")
        call_list.append(entry)
    a["call_list"] = call_list

    store["agg"] = a
    # Attach institute USPs if loaded
    if store.get("institute_usps"):
        store["agg"]["institute_usps"] = store["institute_usps"]


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
    return templates.TemplateResponse(
        name="index.html",
        request=request,
        context={"data_json": Markup(_safe(store["agg"]))},
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
