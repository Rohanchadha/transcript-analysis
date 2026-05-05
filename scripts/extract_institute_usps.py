"""
Extract institute-level USPs from counsellor call transcripts.
Reads: data/parsed_transcripts.json, data/analysis_results.json
Outputs: data/institute_usps_raw.json, data/institute_usps.json

Usage:
  $env:OPENAI_API_KEY = "sk-..."
  python scripts/extract_institute_usps.py
"""

import json
import os
import time
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
PARSED_PATH = ROOT_DIR / "data" / "parsed_transcripts.json"
ANALYSIS_PATH = ROOT_DIR / "data" / "analysis_results.json"
RAW_OUTPUT_PATH = ROOT_DIR / "data" / "institute_usps_raw.json"
AGG_OUTPUT_PATH = ROOT_DIR / "data" / "institute_usps.json"

SYSTEM_PROMPT = """You are an expert analyst studying call center transcripts from Shiksha.com, an Indian education counselling platform. Your task is to extract every piece of information a counsellor uses to PITCH or RECOMMEND colleges/institutes to students.

Focus on what a voice bot would need in an "Institute USPs" knowledge base — the actual facts, claims, and selling points counsellors use when recommending colleges.

For EACH college/institute mentioned in the transcript, extract:

Return a JSON object:
{
  "institutes": [
    {
      "name": "Full official name of the institute",
      "aliases": ["any abbreviations or nicknames used in the call, e.g. KIIDS, VIT"],
      "location": "city, state",
      "courses_discussed": ["B.Tech CSE", "BDS", etc.],
      "pitch_points": [
        {
          "category": "one of: placement, fee, scholarship, infrastructure, ranking, accreditation, admission_process, hostel, location_advantage, industry_tie_up, faculty, alumni, campus_life, comparison_with_others, eligibility, exam_cutoff, other",
          "claim": "the specific fact or selling point in English",
          "counsellor_quote_hindi": "exact quote from the counsellor in original Hindi/Hinglish",
          "translation": "English translation of the quote"
        }
      ],
      "fee_details": [
        {
          "course": "which course this fee is for",
          "amount": "the fee amount as stated",
          "fee_type": "one of: total_program, per_year, per_semester, management_quota, general_quota, scholarship, not_specified",
          "additional_info": "any extra context (e.g. hostel included, EMI available)"
        }
      ],
      "placement_details": {
        "highest_package": "if mentioned",
        "average_package": "if mentioned",
        "placement_percentage": "if mentioned",
        "top_recruiters": ["company names if mentioned"],
        "sectors": ["sectors/industries if mentioned"]
      },
      "was_recommended": true,
      "recommendation_context": "why the counsellor recommended this college (in English)",
      "student_reaction": "one of: positive, negative, neutral, not_mentioned",
      "compared_with": ["names of colleges this was compared against, if any"]
    }
  ]
}

IMPORTANT RULES:
- Extract ONLY information that the counsellor actually states in the transcript. Do not infer or make up data.
- Include the actual Hindi/Hinglish quotes from the counsellor for every pitch point.
- If no colleges are discussed in detail, return {"institutes": []}.
- Capture subtle pitch points too — e.g. "bahut accha campus hai" (great campus), "hospital tie-up hai" (hospital tie-up), "direct placement hoti hai" (direct placement).
- Fee info should be separated out into fee_details even if also captured as a pitch_point.
- For placement_details, only include fields that were actually mentioned — use "not_mentioned" for others.
- Normalize college names to their full official form when possible."""


def extract_usps(client: OpenAI, transcript_text: str, metadata: dict | None, colleges_discussed: list | None) -> dict:
    """Send a transcript to OpenAI for USP extraction."""
    context_parts = []
    if metadata:
        context_parts.append(f"Counsellor: {metadata.get('counsellor_name', 'Unknown')}")
        context_parts.append(f"Team: {metadata.get('team_name', 'Unknown')}")
        context_parts.append(f"Duration: {metadata.get('duration', 0):.0f} seconds")
        context_parts.append(f"Stage: {metadata.get('stage_name', 'Unknown')}")
    context = "\n".join(context_parts) if context_parts else "No metadata available"

    # Give the LLM a hint about colleges already identified
    college_hint = ""
    if colleges_discussed:
        names = [c.get("name", "") for c in colleges_discussed if c.get("name")]
        if names:
            college_hint = f"\n\nCOLLEGES ALREADY IDENTIFIED IN THIS CALL: {', '.join(names)}\n(There may be others — extract ALL colleges mentioned.)"

    user_prompt = f"""Extract all institute-level USPs and pitch points from this counsellor call.

CALL METADATA:
{context}
{college_hint}

TRANSCRIPT:
{transcript_text}

Extract every fact, claim, and selling point the counsellor uses about each college. Include exact Hindi/Hinglish quotes. Return valid JSON only."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=4000,
    )

    return json.loads(response.choices[0].message.content)


def normalize_name(name: str) -> str:
    """Basic normalization for grouping — lowercase, strip whitespace."""
    return name.strip().lower()


def aggregate_usps(raw_results: list) -> dict:
    """Aggregate per-call USP extractions into per-institute profiles."""
    # Group by normalized college name
    institute_map: dict[str, dict] = {}  # normalized_name -> aggregated data

    for call in raw_results:
        call_id = call["id"]
        for inst in call.get("institutes", []):
            name = inst["name"]
            norm = normalize_name(name)

            if norm not in institute_map:
                institute_map[norm] = {
                    "name": name,  # keep first seen full name
                    "aliases": set(),
                    "locations": set(),
                    "courses_discussed": set(),
                    "pitch_points": [],
                    "fee_details": [],
                    "placement_details_list": [],
                    "recommendation_count": 0,
                    "mention_count": 0,
                    "compared_with": set(),
                    "student_reactions": defaultdict(int),
                    "source_calls": set(),
                    "recommendation_contexts": [],
                }

            entry = institute_map[norm]
            entry["mention_count"] += 1
            entry["source_calls"].add(call_id)

            # Use the longest name variant as the canonical name
            if len(name) > len(entry["name"]):
                entry["name"] = name

            # Aliases
            for alias in inst.get("aliases", []):
                if alias and normalize_name(alias) != norm:
                    entry["aliases"].add(alias)

            # Location
            loc = inst.get("location", "")
            if loc and loc.lower() not in ("not_mentioned", "n/a", "unknown", ""):
                entry["locations"].add(loc)

            # Courses
            for course in inst.get("courses_discussed", []):
                if course:
                    entry["courses_discussed"].add(course)

            # Pitch points — deduplicate by claim text
            existing_claims = {p["claim"].lower() for p in entry["pitch_points"]}
            for pp in inst.get("pitch_points", []):
                claim = pp.get("claim", "")
                if claim and claim.lower() not in existing_claims:
                    pp["source_call"] = call_id
                    entry["pitch_points"].append(pp)
                    existing_claims.add(claim.lower())

            # Fee details — deduplicate by course + amount
            existing_fees = {
                (f.get("course", "").lower(), f.get("amount", "").lower())
                for f in entry["fee_details"]
            }
            for fd in inst.get("fee_details", []):
                key = (fd.get("course", "").lower(), fd.get("amount", "").lower())
                if key not in existing_fees:
                    fd["source_call"] = call_id
                    entry["fee_details"].append(fd)
                    existing_fees.add(key)

            # Placement details
            pd = inst.get("placement_details", {})
            if pd and any(v and v != "not_mentioned" for v in pd.values() if isinstance(v, str)):
                pd["source_call"] = call_id
                entry["placement_details_list"].append(pd)

            # Recommendation
            if inst.get("was_recommended"):
                entry["recommendation_count"] += 1
            ctx = inst.get("recommendation_context", "")
            if ctx and ctx.lower() not in ("", "not_mentioned", "n/a"):
                entry["recommendation_contexts"].append(ctx)

            # Compared with
            for cw in inst.get("compared_with", []):
                if cw:
                    entry["compared_with"].add(cw)

            # Student reaction
            reaction = inst.get("student_reaction", "not_mentioned")
            entry["student_reactions"][reaction] += 1

    # Convert sets to lists and build final output
    result = {}
    for norm, data in sorted(institute_map.items(), key=lambda x: -x[1]["mention_count"]):
        # Merge placement details into best-known
        merged_placement = {
            "highest_package": "not_mentioned",
            "average_package": "not_mentioned",
            "placement_percentage": "not_mentioned",
            "top_recruiters": [],
            "sectors": [],
        }
        for pd in data["placement_details_list"]:
            for field in ("highest_package", "average_package", "placement_percentage"):
                val = pd.get(field, "not_mentioned")
                if val and val != "not_mentioned":
                    merged_placement[field] = val
            for field in ("top_recruiters", "sectors"):
                for item in pd.get(field, []):
                    if item and item not in merged_placement[field]:
                        merged_placement[field].append(item)

        result[data["name"]] = {
            "aliases": sorted(data["aliases"]),
            "location": ", ".join(sorted(data["locations"])) or "not_mentioned",
            "courses_discussed": sorted(data["courses_discussed"]),
            "pitch_points": data["pitch_points"],
            "fee_details": data["fee_details"],
            "placement_details": merged_placement,
            "mention_count": data["mention_count"],
            "recommendation_count": data["recommendation_count"],
            "recommendation_contexts": data["recommendation_contexts"],
            "compared_with": sorted(data["compared_with"]),
            "student_reactions": dict(data["student_reactions"]),
            "source_calls": sorted(data["source_calls"]),
        }

    return result


def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: Set OPENAI_API_KEY environment variable")
        print('  PowerShell: $env:OPENAI_API_KEY = "sk-..."')
        print("  Then re-run: python scripts/extract_institute_usps.py")
        return

    client = OpenAI(api_key=api_key)

    # Load parsed transcripts
    if not PARSED_PATH.exists():
        print(f"ERROR: {PARSED_PATH} not found. Run parse_transcripts.py first.")
        return
    with open(PARSED_PATH, "r", encoding="utf-8") as f:
        transcripts = json.load(f)

    # Load analysis results for college hints
    analysis_map = {}
    if ANALYSIS_PATH.exists():
        with open(ANALYSIS_PATH, "r", encoding="utf-8") as f:
            analysis_data = json.load(f)
            for r in analysis_data:
                if r.get("analysis"):
                    analysis_map[r["id"]] = r["analysis"]

    print(f"Loaded {len(transcripts)} transcripts, {len(analysis_map)} with analysis")

    # Load existing raw results for incremental processing
    existing_raw = {}
    if RAW_OUTPUT_PATH.exists():
        with open(RAW_OUTPUT_PATH, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
            for r in existing_data:
                existing_raw[r["id"]] = r
        print(f"Found {len(existing_raw)} existing USP extractions (will skip these)")

    raw_results = []
    extracted = 0
    skipped = 0
    errors = 0

    for i, transcript in enumerate(transcripts):
        tid = transcript["id"]

        # Skip if already extracted
        if tid in existing_raw:
            raw_results.append(existing_raw[tid])
            skipped += 1
            continue

        # Skip very short transcripts
        if transcript["stats"]["total_turns"] < 4:
            skipped += 1
            continue

        # Skip calls with no colleges discussed (from analysis)
        analysis = analysis_map.get(tid)
        colleges_discussed = analysis.get("colleges_discussed", []) if analysis else []

        print(f"  [{i+1}/{len(transcripts)}] Extracting USPs: {tid[:60]}...")

        try:
            result = extract_usps(
                client,
                transcript["full_text"],
                transcript.get("metadata"),
                colleges_discussed,
            )

            raw_entry = {
                "id": tid,
                "filename": transcript["filename"],
                "counsellor": transcript.get("metadata", {}).get("counsellor_name", "Unknown"),
                "institutes": result.get("institutes", []),
            }
            raw_results.append(raw_entry)
            extracted += 1

            # Save checkpoint every 5
            if extracted % 5 == 0:
                with open(RAW_OUTPUT_PATH, "w", encoding="utf-8") as f:
                    json.dump(raw_results, f, ensure_ascii=False, indent=2)
                print(f"    Saved checkpoint ({extracted} extracted so far)")

            time.sleep(0.3)

        except Exception as e:
            print(f"    ERROR: {e}")
            errors += 1
            time.sleep(2)

    # Preserve existing raw results not in current parsed set (avoid data loss)
    current_ids = set(r["id"] for r in raw_results)
    preserved = 0
    for eid, eresult in existing_raw.items():
        if eid not in current_ids:
            raw_results.append(eresult)
            preserved += 1

    # Save raw results
    with open(RAW_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(raw_results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved raw USP extractions to {RAW_OUTPUT_PATH}")

    # Aggregate
    print("Aggregating institute-level USPs...")
    aggregated = aggregate_usps(raw_results)

    with open(AGG_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(aggregated, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"DONE!")
    print(f"  Extracted: {extracted}")
    print(f"  Skipped: {skipped}")
    print(f"  Preserved (not in current parse): {preserved}")
    print(f"  Errors: {errors}")
    print(f"  Unique institutes: {len(aggregated)}")
    print(f"  Raw output: {RAW_OUTPUT_PATH}")
    print(f"  Aggregated output: {AGG_OUTPUT_PATH}")
    print(f"{'='*50}")

    # Print top institutes summary
    print(f"\nTop institutes by mention count:")
    for name, data in list(aggregated.items())[:10]:
        n_usps = len(data["pitch_points"])
        print(f"  {name}: {data['mention_count']} mentions, {n_usps} USPs, {len(data['fee_details'])} fee entries")


if __name__ == "__main__":
    main()
