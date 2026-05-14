"""Parse raw call rows into a normalized per-call structure.

The DB row's `info` column is a JSON blob (or already a dict) containing:
  - transcriptV2: JSON-string of [{role, content (with " (Latency: X.XXs)"), latency_sec, ...}]
  - transcript:   JSON-string of [{role, content}, ...] (fallback)
  - deepGramConfidenceScoreMatrix: list[list[str]] aligned to USER turns
  - persona_name, persona_id, cohort_identifer, model_variant, examBotVersion
  - nodesAsked, success, scheduleLater, freshRegistration, openToApplication, ...
  - {min,max,median,avg}LatencySec
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from statistics import mean, median
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "voicebot" / "data"

LATENCY_SUFFIX_RE = re.compile(r"\s*\(Latency:\s*[\d.]+s\)\s*$")
FILLER_PREFIX_RE = re.compile(r"^\(FILLER:[^)]*\)\s*")


def _maybe_json(value: Any) -> Any:
    """Decode a value that may be a JSON string, double-encoded JSON, or already parsed."""
    if value is None or value == "":
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return value
        # Sometimes double-encoded
        if isinstance(decoded, str):
            try:
                return json.loads(decoded)
            except (json.JSONDecodeError, ValueError):
                return decoded
        return decoded
    return value


def _clean_content(text: str) -> tuple[str, bool, str | None]:
    """Strip latency suffix and filler prefix. Return (clean_text, is_filler, filler_kind)."""
    if not isinstance(text, str):
        return str(text), False, None
    is_filler = False
    filler_kind: str | None = None
    m = FILLER_PREFIX_RE.match(text)
    if m:
        is_filler = True
        # FILLER:<type>:<kind>
        prefix = m.group(0)
        inner = prefix.strip().strip("()").removeprefix("FILLER:")
        filler_kind = inner.strip()
        text = text[m.end():]
    text = LATENCY_SUFFIX_RE.sub("", text).strip()
    return text, is_filler, filler_kind


def parse_turns(info: dict) -> tuple[list[dict], str]:
    """Return (turns, source) where source is 'transcriptV2' or 'transcript'."""
    raw_v2 = _maybe_json(info.get("transcriptV2"))
    raw_v1 = _maybe_json(info.get("transcript"))
    raw = raw_v2 if isinstance(raw_v2, list) and raw_v2 else raw_v1
    source = "transcriptV2" if raw is raw_v2 and isinstance(raw_v2, list) else "transcript"
    if not isinstance(raw, list):
        return [], source

    turns: list[dict] = []
    user_turn_index = 0
    for i, t in enumerate(raw):
        if not isinstance(t, dict):
            continue
        role = t.get("role")
        content = t.get("content", "")
        clean, is_filler, filler_kind = _clean_content(content)
        latency = t.get("latency_sec")
        if latency is None and isinstance(t.get("latency_ms"), (int, float)):
            latency = round(t["latency_ms"] / 1000.0, 3)
        turn = {
            "index": i,
            "role": role,
            "text": clean,
            "is_filler": is_filler,
            "filler_kind": filler_kind,
            "latency_sec": latency,
            "type": t.get("type"),
            "kind": t.get("kind"),
        }
        if role == "user":
            turn["user_turn_index"] = user_turn_index
            user_turn_index += 1
        turns.append(turn)
    return turns, source


def attach_asr_confidence(turns: list[dict], matrix: Any) -> None:
    """Attach Deepgram word-level confidence aggregates to each user turn.

    matrix is list[list[str|float]]; entry i corresponds to user_turn_index i.
    """
    if not isinstance(matrix, list):
        return
    for turn in turns:
        if turn.get("role") != "user":
            continue
        idx = turn.get("user_turn_index")
        if idx is None or idx >= len(matrix):
            continue
        scores_raw = matrix[idx]
        if not isinstance(scores_raw, list) or not scores_raw:
            continue
        try:
            scores = [float(s) for s in scores_raw]
        except (TypeError, ValueError):
            continue
        if not scores:
            continue
        turn["asr_word_count"] = len(scores)
        turn["asr_min_confidence"] = round(min(scores), 4)
        turn["asr_avg_confidence"] = round(sum(scores) / len(scores), 4)


def compute_stats(turns: list[dict], info: dict) -> dict:
    assistant_turns = [t for t in turns if t["role"] == "assistant" and not t["is_filler"]]
    filler_turns = [t for t in turns if t["is_filler"]]
    user_turns = [t for t in turns if t["role"] == "user"]
    latencies = [t["latency_sec"] for t in turns if isinstance(t.get("latency_sec"), (int, float))]
    asr_mins = [t["asr_min_confidence"] for t in user_turns if "asr_min_confidence" in t]
    return {
        "total_turns": len(turns),
        "assistant_turns": len(assistant_turns),
        "filler_turns": len(filler_turns),
        "user_turns": len(user_turns),
        "user_words": sum(len(t["text"].split()) for t in user_turns),
        "assistant_words": sum(len(t["text"].split()) for t in assistant_turns),
        "latency_min_sec": round(min(latencies), 3) if latencies else None,
        "latency_max_sec": round(max(latencies), 3) if latencies else None,
        "latency_avg_sec": round(mean(latencies), 3) if latencies else None,
        "latency_median_sec": round(median(latencies), 3) if latencies else None,
        # Prefer DB-reported aggregates if present
        "latency_avg_sec_reported": info.get("avgLatencySec"),
        "latency_median_sec_reported": info.get("medianLatencySec"),
        "asr_min_overall": min(asr_mins) if asr_mins else None,
        "asr_avg_overall": round(mean(asr_mins), 4) if asr_mins else None,
    }


def parse_row(row: dict) -> dict | None:
    info = _maybe_json(row.get("info"))
    if not isinstance(info, dict):
        return None
    turns, source = parse_turns(info)
    if not turns:
        return None
    attach_asr_confidence(turns, info.get("deepGramConfidenceScoreMatrix"))
    stats = compute_stats(turns, info)

    metadata = {
        "call_sid": row.get("call_sid") or info.get("callSid"),
        "user_id": info.get("userId") or row.get("user_id"),
        "counsellor_id": info.get("counsellorId") or row.get("counsellor_id"),
        "campaign_id": info.get("campaignId"),
        "persona_name": info.get("persona_name"),
        "persona_id": info.get("persona_id"),
        "cohort_identifer": info.get("cohort_identifer"),
        "model_variant": info.get("model_variant"),
        "exam_bot_version": info.get("examBotVersion"),
        "type": info.get("type"),
        "processing_type": info.get("processingType"),
        "is_incoming": info.get("isIncoming"),
        "is_paid": info.get("isPaid"),
        "listing_type": info.get("listingType"),
        "base_course_ids": info.get("baseCourseIds"),
        "state_ids": info.get("stateIds"),
        "open_to_pvt_universities": info.get("openToPvtUniversities"),
        "open_to_application": info.get("openToApplication"),
        "fresh_registration": info.get("freshRegistration"),
        "schedule_later": info.get("scheduleLater"),
        "hot_marked": info.get("hotMarked"),
        "skip_transfer": info.get("skipTransferToAgentOrBackToPool"),
        "success": info.get("success"),
        "nodes_asked": info.get("nodesAsked") or [],
        "already_recommended_institutes": info.get("alreadyRecommendedInstitutes") or [],
        "preferred_institute_list": info.get("preferredInstituteList") or [],
        "pre_call_ds_score": info.get("preCallDsScore"),
        "pre_call_user_base_course": info.get("preCallUserBaseCourse"),
    }
    # Pass through ueil log fields (anything not 'info' that may be useful)
    for k in ("created_at", "updated_at", "mobile", "mobile_number", "phone", "status",
              "created_on", "added_on", "call_status"):
        if k in row and row[k] is not None:
            metadata[k] = str(row[k])
    # Numeric pass-throughs
    if row.get("call_duration") is not None:
        try:
            metadata["call_duration_sec"] = int(row["call_duration"])
        except (TypeError, ValueError):
            pass

    return {
        "call_sid": metadata["call_sid"],
        "metadata": metadata,
        "turns": turns,
        "stats": stats,
        "transcript_source": source,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=str, default="v1", help="Dataset name (file suffix)")
    args = ap.parse_args()

    input_path = DATA_DIR / f"raw_calls__{args.dataset}.json"
    output_path = DATA_DIR / f"parsed_calls__{args.dataset}.json"
    if not input_path.exists():
        raise SystemExit(f"missing {input_path}; run pull_calls.py --dataset {args.dataset} first")
    with input_path.open("r", encoding="utf-8") as f:
        rows = json.load(f)
    print(f"dataset: {args.dataset}  loaded {len(rows)} raw rows")

    parsed: list[dict] = []
    skipped = 0
    for row in rows:
        result = parse_row(row)
        if result is None:
            skipped += 1
            continue
        parsed.append(result)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)
    print(f"parsed {len(parsed)} calls (skipped {skipped} with no usable transcript)")
    print(f"wrote {output_path}")


if __name__ == "__main__":
    main()
