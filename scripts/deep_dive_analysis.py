"""
Deep-dive analysis: Gender-aware communication & Urgency tactic effectiveness.
Reads: data/parsed_transcripts.json, data/analysis_results.json
Outputs: data/deep_dive_insights.json

Lens 8: Infers caller/student gender from Hindi cues using GPT-4o-mini,
         then analyzes if counsellors pitch differently by gender.
Lens 12: Cross-references urgency tactic usage with call outcomes
         to measure if urgency actually drives action.

Usage:
  $env:OPENAI_API_KEY = "sk-..."
  python scripts/deep_dive_analysis.py
"""

import json
import os
import time
from collections import Counter, defaultdict
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
PARSED_PATH = ROOT_DIR / "data" / "parsed_transcripts.json"
ANALYSIS_PATH = ROOT_DIR / "data" / "analysis_results.json"
OUTPUT_PATH = ROOT_DIR / "data" / "deep_dive_insights.json"

# ---------------------------------------------------------------------------
# LENS 8: Gender inference prompt
# ---------------------------------------------------------------------------
GENDER_SYSTEM_PROMPT = """You are an expert linguist analyzing Hindi/Hinglish call transcripts from Shiksha.com, an Indian education counselling platform.

Your task is to infer the GENDER of the student being discussed (not necessarily the caller) and the gender of the person on the call (the caller/user).

Look for these Hindi/Hinglish cues:
- Gendered words: "beta" (son), "beti" (daughter), "ladka" (boy), "ladki" (girl)
- Possessive: "mera beta" (my son), "meri beti" (my daughter), "mere ladke" (my boy)
- Pronouns: "uski" vs "uska" (though often used interchangeably in casual Hindi)
- Names: Indian names often indicate gender (e.g., Priya, Anjali = female; Rahul, Rohan = male)
- Family references: "bhai" (brother), "behen" (sister), "papa", "mummy"
- Counsellor addressing: "sir", "ma'am", "bhaiya", "didi"
- Self-references: "main ladki hoon" (I am a girl), "main boy hoon"
- Voice cues described in transcript context

Return a JSON object:
{
  "caller_gender": "male|female|unclear",
  "caller_gender_confidence": "high|medium|low",
  "caller_gender_evidence": ["list of specific quotes/cues that indicate gender"],
  "student_gender": "male|female|unclear",
  "student_gender_confidence": "high|medium|low",
  "student_gender_evidence": ["list of specific quotes/cues"],
  "student_name_mentioned": "name if mentioned, else null",
  "is_caller_the_student": true|false,
  "gendered_terms_found": ["list of all gendered Hindi terms found in transcript"]
}

IMPORTANT:
- The caller may be a parent calling about their child — so caller_gender and student_gender may differ
- If a parent says "meri beti ke liye" (for my daughter), the student is female
- Be conservative — only mark "high" confidence if multiple strong signals exist
- "unclear" is perfectly valid when there aren't enough cues"""


def infer_gender(client: OpenAI, transcript_text: str, caller_type: str) -> dict:
    """Send transcript to GPT-4o-mini for gender inference."""
    user_prompt = f"""Analyze this counsellor call transcript and infer the gender of the caller and the student.

KNOWN INFO: The caller has been identified as: {caller_type}

TRANSCRIPT:
{transcript_text}

Look for Hindi/Hinglish gender cues (names, "beta"/"beti", "ladka"/"ladki", "sir"/"ma'am", etc.). Return valid JSON only."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": GENDER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=1000,
    )
    return json.loads(response.choices[0].message.content)


# ---------------------------------------------------------------------------
# LENS 12: Urgency analysis (computed from existing data, no LLM needed)
# ---------------------------------------------------------------------------
def analyze_urgency(analysis_results: list) -> dict:
    """Cross-reference urgency tactic usage with call outcomes."""
    urgency_calls = []
    non_urgency_calls = []

    for r in analysis_results:
        if not r.get("analysis"):
            continue
        a = r["analysis"]
        tactics = [t["tactic"] for t in a.get("counsellor_tactics", [])]
        outcome = a["call_outcome"]["primary_outcome"]
        app_started = a["call_outcome"].get("application_started", False)
        whatsapp = a["call_outcome"].get("whatsapp_handoff", False)
        callback = a["call_outcome"].get("callback_scheduled", False)
        colleges_short = a["call_outcome"].get("colleges_shortlisted", 0)
        decision_stage = a["student_profile"].get("decision_stage", "unknown")
        caller_type = a["student_profile"].get("caller_type", "unclear")

        call_info = {
            "id": r["id"],
            "outcome": outcome,
            "app_started": app_started,
            "whatsapp": whatsapp,
            "callback": callback,
            "colleges_shortlisted": colleges_short,
            "decision_stage": decision_stage,
            "caller_type": caller_type,
            "all_tactics": tactics,
            "counsellor": (r.get("metadata") or {}).get("counsellor_name", "Unknown"),
            "duration": (r.get("metadata") or {}).get("duration", 0),
        }

        urgency_tactics = [t for t in a.get("counsellor_tactics", []) if t["tactic"] == "Urgency Creation"]
        has_urgency = len(urgency_tactics) > 0

        if has_urgency:
            call_info["urgency_quotes"] = [
                {"quote": t.get("quote", ""), "translation": t.get("translation", ""), "description": t.get("description", "")}
                for t in urgency_tactics
            ]
            urgency_calls.append(call_info)
        else:
            non_urgency_calls.append(call_info)

    def outcome_stats(calls):
        if not calls:
            return {"count": 0}
        outcomes = Counter(c["outcome"] for c in calls)
        return {
            "count": len(calls),
            "outcomes": dict(outcomes),
            "application_rate": round(sum(1 for c in calls if c["app_started"]) / len(calls) * 100, 1),
            "whatsapp_rate": round(sum(1 for c in calls if c["whatsapp"]) / len(calls) * 100, 1),
            "callback_rate": round(sum(1 for c in calls if c["callback"]) / len(calls) * 100, 1),
            "avg_colleges_shortlisted": round(sum(c["colleges_shortlisted"] for c in calls) / len(calls), 1),
            "avg_duration": round(sum(c["duration"] for c in calls) / len(calls), 1),
        }

    urgency_by_stage = defaultdict(list)
    for c in urgency_calls:
        urgency_by_stage[c["decision_stage"]].append(c)

    urgency_by_caller = defaultdict(list)
    for c in urgency_calls:
        urgency_by_caller[c["caller_type"]].append(c)

    co_tactics = Counter()
    for c in urgency_calls:
        for t in c["all_tactics"]:
            if t != "Urgency Creation":
                co_tactics[t] += 1

    urgency_types = {"deadline": 0, "limited_seats": 0, "fee_waiver_expiring": 0, "competition": 0, "other": 0}
    for c in urgency_calls:
        for uq in c.get("urgency_quotes", []):
            desc = (uq.get("description", "") + " " + uq.get("translation", "")).lower()
            if any(w in desc for w in ["deadline", "last date", "closing", "expire", "ending", "last day"]):
                urgency_types["deadline"] += 1
            elif any(w in desc for w in ["seat", "limited", "few left", "filling", "slot"]):
                urgency_types["limited_seats"] += 1
            elif any(w in desc for w in ["waive", "free", "discount", "offer", "scholarship", "coupon"]):
                urgency_types["fee_waiver_expiring"] += 1
            elif any(w in desc for w in ["competition", "demand", "popular", "rush", "many student"]):
                urgency_types["competition"] += 1
            else:
                urgency_types["other"] += 1

    all_urgency_examples = []
    for c in urgency_calls:
        for uq in c.get("urgency_quotes", []):
            all_urgency_examples.append({
                "quote": uq["quote"],
                "translation": uq["translation"],
                "description": uq["description"],
                "outcome": c["outcome"],
                "app_started": c["app_started"],
                "counsellor": c["counsellor"],
                "call_id": c["id"],
            })

    return {
        "with_urgency": outcome_stats(urgency_calls),
        "without_urgency": outcome_stats(non_urgency_calls),
        "urgency_by_decision_stage": {
            stage: outcome_stats(calls) for stage, calls in urgency_by_stage.items()
        },
        "urgency_by_caller_type": {
            ct: outcome_stats(calls) for ct, calls in urgency_by_caller.items()
        },
        "urgency_types": urgency_types,
        "co_occurring_tactics": dict(co_tactics.most_common(10)),
        "urgency_examples": all_urgency_examples,
        "key_finding": "",
    }


# ---------------------------------------------------------------------------
# Gender analysis aggregation
# ---------------------------------------------------------------------------
def aggregate_gender_insights(gender_results: list, analysis_results: list) -> dict:
    """Cross-reference inferred gender with tactics, objections, outcomes."""
    analysis_map = {}
    for r in analysis_results:
        if r.get("analysis"):
            analysis_map[r["id"]] = r

    male_calls = []
    female_calls = []
    unclear_calls = []

    for gr in gender_results:
        call_id = gr["id"]
        analysis = analysis_map.get(call_id)
        if not analysis or not analysis.get("analysis"):
            continue

        a = analysis["analysis"]
        gender = gr["gender"].get("student_gender", "unclear")
        confidence = gr["gender"].get("student_gender_confidence", "low")

        call_data = {
            "id": call_id,
            "student_gender": gender,
            "gender_confidence": confidence,
            "caller_type": a["student_profile"].get("caller_type", "unclear"),
            "course": a["student_profile"].get("course_interest", "unknown"),
            "decision_stage": a["student_profile"].get("decision_stage", "unknown"),
            "outcome": a["call_outcome"]["primary_outcome"],
            "app_started": a["call_outcome"].get("application_started", False),
            "whatsapp": a["call_outcome"].get("whatsapp_handoff", False),
            "tactics": [t["tactic"] for t in a.get("counsellor_tactics", [])],
            "objection_types": [o["objection_type"] for o in a.get("objections", [])],
            "colleges_recommended": [c["name"] for c in a.get("colleges_discussed", []) if c.get("was_recommended")],
            "duration": (analysis.get("metadata") or {}).get("duration", 0),
            "counsellor": (analysis.get("metadata") or {}).get("counsellor_name", "Unknown"),
            "evidence": gr["gender"].get("student_gender_evidence", []),
            "student_name": gr["gender"].get("student_name_mentioned"),
            "gendered_terms": gr["gender"].get("gendered_terms_found", []),
        }

        if gender == "male":
            male_calls.append(call_data)
        elif gender == "female":
            female_calls.append(call_data)
        else:
            unclear_calls.append(call_data)

    def segment_stats(calls, label):
        if not calls:
            return {"count": 0, "label": label}

        outcomes = Counter(c["outcome"] for c in calls)
        tactics_all = Counter()
        for c in calls:
            for t in c["tactics"]:
                tactics_all[t] += 1

        objections_all = Counter()
        for c in calls:
            for o in c["objection_types"]:
                objections_all[o] += 1

        courses = Counter(c["course"] for c in calls)
        stages = Counter(c["decision_stage"] for c in calls)

        college_counter = Counter()
        for c in calls:
            for col in c["colleges_recommended"]:
                college_counter[col] += 1

        confidence = Counter(c["gender_confidence"] for c in calls)

        return {
            "count": len(calls),
            "label": label,
            "confidence_breakdown": dict(confidence),
            "outcomes": dict(outcomes),
            "application_rate": round(sum(1 for c in calls if c["app_started"]) / len(calls) * 100, 1),
            "whatsapp_rate": round(sum(1 for c in calls if c["whatsapp"]) / len(calls) * 100, 1),
            "avg_duration": round(sum(c["duration"] for c in calls) / len(calls), 1),
            "top_tactics": dict(tactics_all.most_common(10)),
            "top_objections": dict(objections_all.most_common(8)),
            "top_courses": dict(courses.most_common(8)),
            "decision_stages": dict(stages),
            "top_colleges": dict(college_counter.most_common(10)),
            "sample_evidence": [
                {"name": c.get("student_name"), "evidence": c["evidence"][:2], "call_id": c["id"]}
                for c in calls[:5] if c["evidence"]
            ],
        }

    male_stats = segment_stats(male_calls, "Male Students")
    female_stats = segment_stats(female_calls, "Female Students")
    unclear_stats = segment_stats(unclear_calls, "Unclear Gender")

    deltas = []
    if male_stats["count"] >= 3 and female_stats["count"] >= 3:
        app_delta = female_stats["application_rate"] - male_stats["application_rate"]
        deltas.append({
            "metric": "Application Start Rate",
            "male": f"{male_stats['application_rate']}%",
            "female": f"{female_stats['application_rate']}%",
            "delta": f"{app_delta:+.1f}pp",
            "insight": "Female students have higher application rate" if app_delta > 0 else "Male students have higher application rate" if app_delta < 0 else "No significant difference"
        })

        dur_delta = female_stats["avg_duration"] - male_stats["avg_duration"]
        deltas.append({
            "metric": "Avg Call Duration",
            "male": f"{male_stats['avg_duration']:.0f}s",
            "female": f"{female_stats['avg_duration']:.0f}s",
            "delta": f"{dur_delta:+.0f}s",
            "insight": "Calls with female students are longer" if dur_delta > 0 else "Calls with male students are longer" if dur_delta < 0 else "Similar duration"
        })

        wa_delta = female_stats["whatsapp_rate"] - male_stats["whatsapp_rate"]
        deltas.append({
            "metric": "WhatsApp Handoff Rate",
            "male": f"{male_stats['whatsapp_rate']}%",
            "female": f"{female_stats['whatsapp_rate']}%",
            "delta": f"{wa_delta:+.1f}pp",
            "insight": "More WhatsApp handoffs with female students" if wa_delta > 0 else "More WhatsApp handoffs with male students" if wa_delta < 0 else "Similar rate"
        })

        all_tactics = set(male_stats["top_tactics"].keys()) | set(female_stats["top_tactics"].keys())
        tactic_skew = []
        for tactic in all_tactics:
            m_pct = round(male_stats["top_tactics"].get(tactic, 0) / male_stats["count"] * 100, 1)
            f_pct = round(female_stats["top_tactics"].get(tactic, 0) / female_stats["count"] * 100, 1)
            if abs(m_pct - f_pct) >= 10:
                tactic_skew.append({
                    "tactic": tactic,
                    "male_pct": f"{m_pct}%",
                    "female_pct": f"{f_pct}%",
                    "skew": "More with female" if f_pct > m_pct else "More with male",
                })
        if tactic_skew:
            deltas.append({"metric": "Tactic Usage Differences (≥10pp gap)", "details": tactic_skew})

        all_objs = set(male_stats["top_objections"].keys()) | set(female_stats["top_objections"].keys())
        obj_skew = []
        for obj in all_objs:
            m_pct = round(male_stats["top_objections"].get(obj, 0) / male_stats["count"] * 100, 1)
            f_pct = round(female_stats["top_objections"].get(obj, 0) / female_stats["count"] * 100, 1)
            if abs(m_pct - f_pct) >= 10:
                obj_skew.append({
                    "objection": obj,
                    "male_pct": f"{m_pct}%",
                    "female_pct": f"{f_pct}%",
                    "skew": "More with female" if f_pct > m_pct else "More with male",
                })
        if obj_skew:
            deltas.append({"metric": "Objection Differences (≥10pp gap)", "details": obj_skew})

    return {
        "male": male_stats,
        "female": female_stats,
        "unclear": unclear_stats,
        "deltas": deltas,
        "total_analyzed": len(gender_results),
        "gender_distribution": {
            "male": male_stats["count"],
            "female": female_stats["count"],
            "unclear": unclear_stats["count"],
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: Set OPENAI_API_KEY environment variable")
        return

    client = OpenAI(api_key=api_key)

    with open(PARSED_PATH, "r", encoding="utf-8") as f:
        transcripts = json.load(f)
    with open(ANALYSIS_PATH, "r", encoding="utf-8") as f:
        analysis_results = json.load(f)

    transcript_map = {t["id"]: t for t in transcripts}
    analysis_map = {r["id"]: r for r in analysis_results if r.get("analysis")}

    print(f"Loaded {len(transcripts)} transcripts, {len(analysis_map)} analyzed")

    # --- LENS 12: Urgency analysis (no LLM needed) ---
    print("\n=== LENS 12: Urgency Tactic Effectiveness ===")
    urgency_insights = analyze_urgency(analysis_results)

    u_with = urgency_insights["with_urgency"]
    u_without = urgency_insights["without_urgency"]
    print(f"  Calls WITH urgency tactic: {u_with['count']}")
    print(f"  Calls WITHOUT urgency tactic: {u_without['count']}")
    if u_with["count"] > 0 and u_without["count"] > 0:
        print(f"  Application rate WITH urgency:    {u_with['application_rate']}%")
        print(f"  Application rate WITHOUT urgency: {u_without['application_rate']}%")
        print(f"  WhatsApp rate WITH urgency:       {u_with['whatsapp_rate']}%")
        print(f"  WhatsApp rate WITHOUT urgency:    {u_without['whatsapp_rate']}%")

        app_diff = u_with["application_rate"] - u_without["application_rate"]
        if app_diff > 5:
            urgency_insights["key_finding"] = f"Urgency tactics correlate with +{app_diff:.1f}pp higher application rate ({u_with['application_rate']}% vs {u_without['application_rate']}%)."
        elif app_diff < -5:
            urgency_insights["key_finding"] = f"Urgency tactics correlate with {app_diff:.1f}pp LOWER application rate — may be used as a last resort on reluctant leads."
        else:
            urgency_insights["key_finding"] = f"Urgency tactics show minimal direct impact on application rate ({u_with['application_rate']}% vs {u_without['application_rate']}%). Effect may depend on decision stage."

    # --- LENS 8: Gender inference (LLM pass) ---
    print("\n=== LENS 8: Gender-Aware Communication ===")

    existing_gender = {}
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)
            for gr in existing.get("gender_raw", []):
                existing_gender[gr["id"]] = gr

    gender_results = []
    extracted = 0
    skipped = 0

    for call_id, analysis in analysis_map.items():
        if call_id in existing_gender:
            gender_results.append(existing_gender[call_id])
            skipped += 1
            continue

        transcript = transcript_map.get(call_id)
        if not transcript or transcript["stats"]["total_turns"] < 4:
            skipped += 1
            continue

        caller_type = analysis["analysis"]["student_profile"].get("caller_type", "unclear")

        print(f"  [{extracted + skipped + 1}/{len(analysis_map)}] Inferring gender: {call_id[:50]}...")

        try:
            gender = infer_gender(client, transcript["full_text"], caller_type)
            gender_results.append({"id": call_id, "caller_type": caller_type, "gender": gender})
            extracted += 1

            if extracted % 10 == 0:
                _save_checkpoint(gender_results, urgency_insights, analysis_results)
                print(f"    Saved checkpoint ({extracted} inferred so far)")

            time.sleep(0.3)
        except Exception as e:
            print(f"    ERROR: {e}")
            time.sleep(2)

    print(f"  Gender inference: {extracted} new, {skipped} skipped")

    gender_insights = aggregate_gender_insights(gender_results, analysis_results)

    print(f"\n  Gender distribution: Male={gender_insights['gender_distribution']['male']}, "
          f"Female={gender_insights['gender_distribution']['female']}, "
          f"Unclear={gender_insights['gender_distribution']['unclear']}")

    if gender_insights["deltas"]:
        print("  Key deltas:")
        for d in gender_insights["deltas"]:
            if "details" not in d:
                print(f"    {d['metric']}: M={d['male']} F={d['female']} ({d['delta']})")

    output = {
        "urgency_analysis": urgency_insights,
        "gender_analysis": gender_insights,
        "gender_raw": gender_results,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"DONE! Saved to {OUTPUT_PATH}")
    print(f"{'='*50}")


def _save_checkpoint(gender_results, urgency_insights, analysis_results):
    gender_insights = aggregate_gender_insights(gender_results, analysis_results)
    output = {
        "urgency_analysis": urgency_insights,
        "gender_analysis": gender_insights,
        "gender_raw": gender_results,
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
