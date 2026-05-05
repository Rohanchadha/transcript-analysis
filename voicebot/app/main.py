"""Voice-bot issue dashboard. FastAPI on port 8001."""
from __future__ import annotations

import csv
import io
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "voicebot" / "data"
APP_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Voice-Bot Issue Dashboard")
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")


# ---------- Data loading ----------

# _datasets[name] = {"issues": [...], "calls": [...], "calls_by_sid": {...}, "issues_by_sid": {...}}
_datasets: dict[str, dict[str, Any]] = {}
_dataset_meta: dict[str, dict[str, Any]] = {
    "v1": {"label": "Shortlist Bot (v1)", "description": "counsellor 12345678 \u2014 baseline B.Tech shortlist bot"},
    "v2": {"label": "New Bot (v2)", "description": "counsellor 103884168 \u2014 May 1\u20134, 2026"},
}


def _discover_datasets() -> list[str]:
    names = set()
    for p in DATA_DIR.glob("issues__*.json"):
        name = p.stem.removeprefix("issues__")
        if name:
            names.add(name)
    return sorted(names)


def _load_dataset(name: str) -> dict[str, Any] | None:
    issues_path = DATA_DIR / f"issues__{name}.json"
    parsed_path = DATA_DIR / f"parsed_calls__{name}.json"
    if not issues_path.exists():
        return None
    issues = json.loads(issues_path.read_text(encoding="utf-8"))
    calls = json.loads(parsed_path.read_text(encoding="utf-8")) if parsed_path.exists() else []
    return {
        "issues": issues,
        "calls": calls,
        "calls_by_sid": {c["call_sid"]: c for c in calls},
        "issues_by_sid": {i["call_sid"]: i for i in issues},
    }


def _load() -> None:
    _datasets.clear()
    for name in _discover_datasets():
        ds = _load_dataset(name)
        if ds is not None:
            _datasets[name] = ds


def _state_for(dataset: str | None) -> dict[str, Any]:
    """Resolve dataset name (default to first available) and return its state."""
    if not _datasets:
        return {"issues": [], "calls": [], "calls_by_sid": {}, "issues_by_sid": {}}
    name = dataset or next(iter(_datasets))
    if name not in _datasets:
        raise HTTPException(404, f"dataset '{name}' not found")
    return _datasets[name]


@app.on_event("startup")
def startup() -> None:
    _load()


@app.get("/api/datasets")
def list_datasets() -> dict:
    out = []
    for name in _datasets:
        meta = _dataset_meta.get(name, {})
        ds = _datasets[name]
        out.append({
            "name": name,
            "label": meta.get("label", name),
            "description": meta.get("description", ""),
            "call_count": len(ds["issues"]),
        })
    return {"datasets": out}


@app.post("/api/reload")
def reload_data() -> dict:
    _load()
    return {
        "ok": True,
        "datasets": [
            {"name": n, "calls": len(_datasets[n]["calls"]), "issues": len(_datasets[n]["issues"])}
            for n in _datasets
        ],
    }


# ---------- Helpers ----------

CATEGORY_LABELS = {
    "unanswered_query": "Unanswered Query",
    "topic_deviation": "Topic Deviation",
    "repetition_loop": "Repetition / Loop",
    "asr_intent_breakdown": "ASR / Intent Breakdown",
    "student_frustration": "Student Frustration",
    "hallucination": "Hallucination",
    "latency_perceived": "Latency",
    "name_violation": "Name Violation",
    "length_violation": "Length / Question Limit",
    "tool_name_leak": "Tool Name Leak",
    "shuddh_hindi": "Shuddh Hindi Used",
    "user_confusion_marker": "User Confusion",
    "other": "Other",
}

CATEGORY_DESCRIPTIONS = {
    "unanswered_query": "Student asked something and the bot ignored it, gave a vague non-answer, or pivoted away.",
    "topic_deviation": "Bot drifted off the B.Tech admissions topic or didn't bring a wandering conversation back on track.",
    "repetition_loop": "Bot repeated the same line/question multiple times.",
    "asr_intent_breakdown": (
        "The speech-to-text engine (Deepgram) had low confidence on the student's words, "
        "OR the bot's reply makes it clear it misheard the student. Either way, the bot is "
        "responding to the wrong intent. Common causes: heavy accent, background noise, "
        "Hindi-English code-mixing the ASR can't resolve."
    ),
    "student_frustration": "Student showed clear irritation or disengagement (terse 'haan haan', 'nahi nahi', abrupt close).",
    "hallucination": "Bot stated a specific college fact (fee/placement/cutoff) that appears invented.",
    "latency_perceived": "Bot took longer than 5 seconds to respond on a turn — student likely perceived a hang.",
    "name_violation": "Bot called itself something other than 'Neha'.",
    "length_violation": "Bot turn was unusually long (>4 sentences or >2 questions).",
    "tool_name_leak": "Bot leaked a tool/function name in user-facing speech.",
    "shuddh_hindi": "Bot used formal Devanagari Hindi words the prompt explicitly bans.",
    "user_confusion_marker": "Student said something like 'kya?' / 'samajh nahi aaya' / asked for repeat.",
    "other": "Miscellaneous issue.",
}

SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1, None: 0}


# ---------- Endpoints ----------

@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html", {})


@app.get("/api/overview")
def overview(dataset: str | None = Query(None)) -> dict:
    state = _state_for(dataset)
    issues = state["issues"]
    if not issues:
        return {"total_calls": 0}
    total = len(issues)
    with_issue = sum(1 for r in issues if r["issue_count"] > 0)
    avg_issues = round(sum(r["issue_count"] for r in issues) / total, 2)
    qual_completed = sum(1 for r in issues if r.get("qualification_completed"))
    quality_counts: Counter[str] = Counter(r.get("overall_quality", "unknown") for r in issues)
    primary_failures: Counter[str] = Counter(r.get("primary_failure_mode", "none") for r in issues)

    latencies = [r["stats"].get("latency_avg_sec_reported") or r["stats"].get("latency_avg_sec")
                 for r in issues if r.get("stats")]
    latencies = [x for x in latencies if isinstance(x, (int, float))]
    latencies.sort()

    def pct(p: float) -> float | None:
        if not latencies:
            return None
        i = min(len(latencies) - 1, int(len(latencies) * p))
        return round(latencies[i], 3)

    return {
        "total_calls": total,
        "calls_with_issues": with_issue,
        "calls_with_issues_pct": round(with_issue * 100 / total, 1),
        "avg_issues_per_call": avg_issues,
        "qualification_completed_pct": round(qual_completed * 100 / total, 1),
        "overall_quality_distribution": dict(quality_counts),
        "primary_failure_mode_distribution": dict(primary_failures),
        "latency_p50_sec": pct(0.5),
        "latency_p95_sec": pct(0.95),
    }


@app.get("/api/issues/categories")
def issue_categories(dataset: str | None = Query(None)) -> dict:
    issues = _state_for(dataset)["issues"]
    cat_counts: Counter[str] = Counter()
    cat_severity: dict[str, Counter[str]] = defaultdict(Counter)
    cat_examples: dict[str, list[dict]] = defaultdict(list)

    for record in issues:
        for it in record["issues"]:
            cat = it["category"]
            cat_counts[cat] += 1
            cat_severity[cat][it.get("severity", "low")] += 1
            if len(cat_examples[cat]) < 5:
                cat_examples[cat].append({
                    "call_sid": record["call_sid"],
                    "severity": it.get("severity"),
                    "turn_index": it.get("turn_index"),
                    "user_quote": it.get("user_quote", ""),
                    "bot_quote": it.get("bot_quote", ""),
                    "explanation": it.get("explanation", ""),
                    "suggested_fix": it.get("suggested_fix", ""),
                    "source": it.get("source"),
                })

    out = []
    for cat, count in cat_counts.most_common():
        out.append({
            "category": cat,
            "label": CATEGORY_LABELS.get(cat, cat),
            "description": CATEGORY_DESCRIPTIONS.get(cat, ""),
            "count": count,
            "severity": dict(cat_severity[cat]),
            "examples": cat_examples[cat],
        })
    return {"categories": out}


@app.get("/api/issues/by-rule")
def issues_by_rule(dataset: str | None = Query(None)) -> dict:
    counts: Counter[str] = Counter()
    for record in _state_for(dataset)["issues"]:
        for it in record["issues"]:
            if it.get("source") == "rule":
                counts[it["category"]] += 1
    return {"rule_counts": [
        {"category": c, "label": CATEGORY_LABELS.get(c, c), "count": n}
        for c, n in counts.most_common()
    ]}


@app.get("/api/issues/by-persona")
def issues_by_persona(dataset: str | None = Query(None)) -> dict:
    by_persona: dict[str, dict] = defaultdict(lambda: {
        "calls": 0, "total_issues": 0, "categories": Counter(),
        "quality": Counter(),
    })
    for record in _state_for(dataset)["issues"]:
        persona = record["metadata"].get("persona_name") or "(unknown)"
        bucket = by_persona[persona]
        bucket["calls"] += 1
        bucket["total_issues"] += record["issue_count"]
        for cat, n in record["category_counts"].items():
            bucket["categories"][cat] += n
        bucket["quality"][record.get("overall_quality", "unknown")] += 1

    out = []
    for persona, b in by_persona.items():
        out.append({
            "persona": persona,
            "calls": b["calls"],
            "total_issues": b["total_issues"],
            "avg_issues_per_call": round(b["total_issues"] / b["calls"], 2) if b["calls"] else 0,
            "top_categories": dict(b["categories"].most_common(5)),
            "quality_distribution": dict(b["quality"]),
        })
    out.sort(key=lambda x: x["avg_issues_per_call"], reverse=True)
    return {"personas": out}


@app.get("/api/calls")
def list_calls(
    dataset: str | None = Query(None),
    category: str | None = Query(None),
    severity: str | None = Query(None),
    persona: str | None = Query(None),
    quality: str | None = Query(None),
    min_issues: int = Query(0),
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    state = _state_for(dataset)
    matches = []
    search_lc = search.lower().strip() if search else None
    for record in state["issues"]:
        if persona and record["metadata"].get("persona_name") != persona:
            continue
        if quality and record.get("overall_quality") != quality:
            continue
        if record["issue_count"] < min_issues:
            continue
        if category and category not in record["category_counts"]:
            continue
        if severity:
            if not any(it.get("severity") == severity for it in record["issues"]):
                continue
        if search_lc:
            hay = " ".join([
                record["call_sid"],
                record.get("call_summary", "") or "",
                str(record["metadata"].get("persona_name") or ""),
            ]).lower()
            if search_lc not in hay:
                continue
        matches.append(record)

    matches.sort(key=lambda r: r["issue_count"], reverse=True)
    total = len(matches)
    page = matches[offset: offset + limit]

    calls_by_sid = state["calls_by_sid"]
    out = []
    for record in page:
        summary = record.get("call_summary", "") or ""
        if len(summary) > 200:
            summary = summary[:200].rstrip() + "…"
        call = calls_by_sid.get(record["call_sid"]) or {}
        duration_sec = (call.get("metadata") or {}).get("call_duration_sec")
        out.append({
            "call_sid": record["call_sid"],
            "user_id": record["metadata"].get("user_id"),
            "persona": record["metadata"].get("persona_name"),
            "cohort": record["metadata"].get("cohort_identifer"),
            "model_variant": record["metadata"].get("model_variant"),
            "user_turns": record["stats"].get("user_turns"),
            "call_duration_sec": duration_sec,
            "issue_count": record["issue_count"],
            "primary_failure_mode": record.get("primary_failure_mode"),
            "overall_quality": record.get("overall_quality"),
            "categories": list(record["category_counts"].keys()),
            "summary": summary,
        })
    return {
        "calls": out,
        "count": len(out),
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@app.get("/api/calls/{call_sid}")
def call_detail(call_sid: str, dataset: str | None = Query(None)) -> dict:
    state = _state_for(dataset)
    issues_record = state["issues_by_sid"].get(call_sid)
    call = state["calls_by_sid"].get(call_sid)
    if not call:
        raise HTTPException(404, "call not found")
    issues_by_turn: dict[int | None, list[dict]] = defaultdict(list)
    if issues_record:
        for it in issues_record["issues"]:
            issues_by_turn[it.get("turn_index")].append(it)
    return {
        "call_sid": call_sid,
        "metadata": call["metadata"],
        "stats": call["stats"],
        "transcript_source": call.get("transcript_source"),
        "turns": call["turns"],
        "issues_by_turn": {str(k): v for k, v in issues_by_turn.items()},
        "issues_summary": {
            "total": issues_record["issue_count"] if issues_record else 0,
            "categories": issues_record["category_counts"] if issues_record else {},
            "primary_failure_mode": issues_record.get("primary_failure_mode") if issues_record else None,
            "overall_quality": issues_record.get("overall_quality") if issues_record else None,
            "call_summary": issues_record.get("call_summary") if issues_record else None,
            "qualification_completed": issues_record.get("qualification_completed") if issues_record else None,
        },
    }


@app.get("/api/export")
def export_csv(dataset: str | None = Query(None)) -> StreamingResponse:
    state = _state_for(dataset)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "call_sid", "user_id", "persona", "cohort", "model_variant",
        "overall_quality", "primary_failure_mode", "issue_count",
        "category", "severity", "source", "turn_index",
        "user_quote", "bot_quote", "explanation", "suggested_fix",
    ])
    for record in state["issues"]:
        m = record["metadata"]
        if not record["issues"]:
            writer.writerow([
                record["call_sid"], m.get("user_id"), m.get("persona_name"),
                m.get("cohort_identifer"), m.get("model_variant"),
                record.get("overall_quality"), record.get("primary_failure_mode"),
                0, "", "", "", "", "", "", "", "",
            ])
            continue
        for it in record["issues"]:
            writer.writerow([
                record["call_sid"], m.get("user_id"), m.get("persona_name"),
                m.get("cohort_identifer"), m.get("model_variant"),
                record.get("overall_quality"), record.get("primary_failure_mode"),
                record["issue_count"],
                it.get("category"), it.get("severity"), it.get("source"),
                it.get("turn_index"),
                (it.get("user_quote") or "").replace("\n", " "),
                (it.get("bot_quote") or "").replace("\n", " "),
                (it.get("explanation") or "").replace("\n", " "),
                (it.get("suggested_fix") or "").replace("\n", " "),
            ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=voicebot_issues_{dataset or 'default'}.csv"},
    )


# ---------- Latency dashboard ----------

def _percentile(sorted_vals: list[float], p: float) -> float | None:
    if not sorted_vals:
        return None
    i = min(len(sorted_vals) - 1, int(len(sorted_vals) * p))
    return round(sorted_vals[i], 3)


def _histogram(values: list[float], edges: list[float]) -> list[dict]:
    """Bin values into half-open intervals [edges[i], edges[i+1]).
    Last bucket is [edges[-1], +inf)."""
    bins = [0] * len(edges)
    labels = []
    for i, lo in enumerate(edges):
        hi = edges[i + 1] if i + 1 < len(edges) else None
        labels.append(f"{lo:g}\u2013{hi:g}s" if hi is not None else f">{lo:g}s")
    for v in values:
        placed = False
        for i in range(len(edges) - 1, -1, -1):
            if v >= edges[i]:
                bins[i] += 1
                placed = True
                break
        if not placed:
            bins[0] += 1
    return [{"bucket": labels[i], "lo": edges[i], "count": bins[i]} for i in range(len(edges))]


# Bin edges in seconds (tuned for typical voice-bot latencies)
_PER_CALL_EDGES = [0, 1, 1.5, 2, 2.5, 3, 3.5, 4, 5, 6, 8, 10]
_PER_TURN_EDGES = [0, 0.5, 1, 1.5, 2, 2.5, 3, 4, 5, 7, 10, 15]


def _call_avg_latency(record: dict, call: dict | None) -> float | None:
    """Prefer DB-reported avgLatencySec; fall back to computed; then to mean of turn latencies."""
    stats = record.get("stats") or (call or {}).get("stats") or {}
    for key in ("latency_avg_sec_reported", "latency_avg_sec"):
        v = stats.get(key)
        if isinstance(v, (int, float)):
            return float(v)
    if call:
        lats = [t.get("latency_sec") for t in call.get("turns", [])
                if isinstance(t.get("latency_sec"), (int, float))]
        if lats:
            return sum(lats) / len(lats)
    return None


@app.get("/api/latency")
def latency_overview(
    dataset: str | None = Query(None),
    min_turns: int = Query(0, ge=0, description="Only consider calls with >= this many turns"),
) -> dict:
    state = _state_for(dataset)
    issues = state["issues"]
    calls_by_sid = state["calls_by_sid"]

    per_call_avgs: list[float] = []
    per_call_records: list[dict] = []  # for outlier table
    per_turn_lats: list[float] = []
    by_kind: dict[str, list[float]] = defaultdict(list)
    by_role: dict[str, list[float]] = defaultdict(list)

    for record in issues:
        sid = record["call_sid"]
        call = calls_by_sid.get(sid)
        turns = (call or {}).get("turns", [])
        turn_lats = [t["latency_sec"] for t in turns
                     if isinstance(t.get("latency_sec"), (int, float))]
        if len(turns) < min_turns:
            continue

        avg = _call_avg_latency(record, call)
        if avg is not None and turn_lats:  # require at least one measured turn
            per_call_avgs.append(avg)
            sorted_tl = sorted(turn_lats)
            duration_sec = (call.get("metadata") or {}).get("call_duration_sec") if call else None
            per_call_records.append({
                "call_sid": sid,
                "persona": record["metadata"].get("persona_name"),
                "model_variant": record["metadata"].get("model_variant"),
                "user_turns": record["stats"].get("user_turns"),
                "total_turns": record["stats"].get("total_turns"),
                "call_duration_sec": duration_sec,
                "avg_latency_sec": round(avg, 3),
                "max_latency_sec": round(max(turn_lats), 3),
                "p95_latency_sec": _percentile(sorted_tl, 0.95),
                "median_latency_sec": _percentile(sorted_tl, 0.5),
                "turn_count_with_latency": len(turn_lats),
                "overall_quality": record.get("overall_quality"),
                "primary_failure_mode": record.get("primary_failure_mode"),
            })

        for t in turns:
            lat = t.get("latency_sec")
            if not isinstance(lat, (int, float)):
                continue
            per_turn_lats.append(lat)
            role = t.get("role") or "unknown"
            if t.get("is_filler"):
                kind = t.get("filler_kind") or t.get("kind") or "filler"
                by_kind[f"filler:{kind}"].append(lat)
            else:
                by_kind[f"{role}:reply"].append(lat)
            by_role[role].append(lat)

    sorted_call_avgs = sorted(per_call_avgs)
    sorted_turn_lats = sorted(per_turn_lats)

    def _stats(vals: list[float]) -> dict:
        s = sorted(vals)
        return {
            "n": len(s),
            "mean": round(sum(s) / len(s), 3) if s else None,
            "p50": _percentile(s, 0.5),
            "p90": _percentile(s, 0.9),
            "p95": _percentile(s, 0.95),
            "p99": _percentile(s, 0.99),
            "max": round(max(s), 3) if s else None,
        }

    # Outlier detection: any call exceeding the per-call avg p95, OR with max turn > 8s.
    p95_avg = _percentile(sorted_call_avgs, 0.95) or 0
    outliers = [
        c for c in per_call_records
        if c["avg_latency_sec"] >= p95_avg or (c["max_latency_sec"] or 0) >= 8
    ]
    outliers.sort(key=lambda c: c["avg_latency_sec"], reverse=True)

    kind_breakdown = []
    for kind, vals in by_kind.items():
        st = _stats(vals)
        kind_breakdown.append({"kind": kind, **st})
    kind_breakdown.sort(key=lambda k: (k["n"] or 0), reverse=True)

    return {
        "per_call": {
            "stats": _stats(per_call_avgs),
            "histogram": _histogram(per_call_avgs, _PER_CALL_EDGES),
            "n_calls": len(per_call_avgs),
        },
        "per_turn": {
            "stats": _stats(per_turn_lats),
            "histogram": _histogram(per_turn_lats, _PER_TURN_EDGES),
            "n_turns": len(per_turn_lats),
        },
        "by_kind": kind_breakdown,
        "outlier_threshold": {
            "per_call_avg_p95_sec": p95_avg,
            "max_turn_sec": 8,
        },
        "outliers": outliers[:100],
        "outlier_count": len(outliers),
    }
