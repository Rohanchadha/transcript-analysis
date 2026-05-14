"""
Analyze parsed transcripts using OpenAI GPT-4o-mini.
Reads: data/parsed_transcripts.json
Outputs: data/analysis_results.json

Usage:
  $env:OPENAI_API_KEY = "sk-..."
  python scripts/analyze_transcripts.py
"""

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
PARSED_PATH = ROOT_DIR / "data" / "parsed_transcripts.json"
OUTPUT_PATH = ROOT_DIR / "data" / "analysis_results.json"

SYSTEM_PROMPT = """You are an expert analyst studying call center transcripts from Shiksha.com, an Indian education counselling platform. Shiksha counsellors help Class 12 students and their parents choose colleges and programs across India.

Your task is to analyze a single call transcript and extract structured insights. The transcripts are in Hindi/Hinglish (Hindi written in Roman script mixed with English).

IMPORTANT CONTEXT:
- Shiksha.com focuses on college recommendations and selection, NOT career counselling
- The goal is to understand how human counsellors handle calls so we can build a better voice bot
- Students/parents typically search on the Shiksha website and the counsellor calls them back
- Common exams: JEE Mains/Advanced, NEET, CUET, VITEEE, MHT-CET, COMEDK
- Common categories: General, OBC, SC, ST, EWS
- Counsellors recommend private colleges primarily (Amity, VIT, SRM, Manipal, KIIT, etc.)

Return a JSON object with these exact keys:

{
  "student_profile": {
    "course_interest": "string - e.g. B.Tech CSE, BDS, MBA, B.Pharma",
    "exam_scores": "string - any scores mentioned (JEE %, NEET, 12th %, 10th %)",
    "category": "string - General/OBC/SC/ST/EWS/not_mentioned",
    "location_preference": "string - preferred city/state or 'anywhere'",
    "budget": "string - fee budget or 'not_mentioned'",
    "decision_stage": "one of: just_exploring, actively_comparing, ready_to_apply, already_applied_elsewhere",
    "caller_type": "one of: student, parent, unclear"
  },
  "query_buckets": [
    {
      "bucket": "one of: College Information, Entrance Exam Queries, Course Selection, Location Preferences, Budget & Fees, Admission Process, Government vs Private, Placement & Career, Already Applied Elsewhere, General Confusion",
      "query": "specific question raised",
      "quote": "exact quote from transcript in original language",
      "translation": "English translation"
    }
  ],
  "counsellor_tactics": [
    {
      "tactic": "one of: Rapport Building, Structured Qualification, Reality Check, Tiered College Recommendation, Placement Data Anchoring, Urgency Creation, Friction Removal, Objection Reframing, Multi-Option Strategy, WhatsApp Handoff, Parent/Family Engagement, Empathy & Reassurance, Comparison Nudge, Callback Scheduling",
      "description": "how the tactic was applied",
      "quote": "supporting quote from counsellor in original language",
      "translation": "English translation"
    }
  ],
  "objections": [
    {
      "objection": "what the student/parent objected to",
      "objection_type": "one of: budget_concern, location_concern, exam_not_ready, not_interested, already_decided, quality_doubt, too_many_options, wants_government, family_pressure, other",
      "handling_strategy": "how counsellor handled it",
      "student_quote": "student's objection quote",
      "counsellor_quote": "counsellor's response quote",
      "was_resolved": true/false
    }
  ],
  "colleges_discussed": [
    {
      "name": "college name",
      "location": "city",
      "fee_mentioned": "fee info or not_mentioned",
      "placement_mentioned": "placement data or not_mentioned",
      "was_recommended": true/false,
      "student_reaction": "one of: positive, negative, neutral, not_mentioned"
    }
  ],
  "call_outcome": {
    "primary_outcome": "one of: application_started, info_shared_interested, info_shared_lukewarm, callback_scheduled, student_disengaged, wrong_number_or_short_call",
    "application_started": true/false,
    "whatsapp_handoff": true/false,
    "callback_scheduled": true/false,
    "colleges_shortlisted": number
  },
  "call_flow_phases": [
    {
      "phase": "one of: Opening & Rapport, Lead Qualification, Need Discovery, College Recommendations, Objection Handling, Application Push, Closing & Next Steps",
      "happened": true/false,
      "description": "brief description of what happened in this phase"
    }
  ],
  "summary": "2-3 sentence summary in English",
  "bot_learnings": ["learning 1", "learning 2", "..."]
}

Be thorough. Use ACTUAL quotes from the transcript in the original language (Hindi/Hinglish). Extract ALL queries, tactics, and objections - don't skip any. For bot_learnings, focus on specific actionable things a voice bot should replicate from this call."""


def analyze_transcript(client: OpenAI, transcript_text: str, metadata: dict | None) -> dict:
    """Send a transcript to OpenAI for analysis."""
    context_parts = []
    if metadata:
        context_parts.append(f"Counsellor: {metadata.get('counsellor_name', 'Unknown')}")
        context_parts.append(f"Team: {metadata.get('team_name', 'Unknown')}")
        context_parts.append(f"Duration: {metadata.get('duration', 0):.0f} seconds")
        context_parts.append(f"Stage: {metadata.get('stage_name', 'Unknown')}")

    context = "\n".join(context_parts) if context_parts else "No metadata available"

    user_prompt = f"""Analyze this counsellor call transcript from Shiksha.com.

CALL METADATA:
{context}

TRANSCRIPT:
{transcript_text}

Extract all insights as specified in your instructions. Include actual quotes in the original language (Hindi/Hinglish). If a field doesn't apply, use empty arrays or "not_mentioned". Return valid JSON only."""

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


def main():
    # Check API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: Set OPENAI_API_KEY environment variable")
        print('  PowerShell: $env:OPENAI_API_KEY = "sk-..."')
        print("  Then re-run: python scripts/analyze_transcripts.py")
        return

    client = OpenAI(api_key=api_key)

    # Load parsed transcripts
    if not PARSED_PATH.exists():
        print(f"ERROR: {PARSED_PATH} not found. Run parse_transcripts.py first.")
        return

    with open(PARSED_PATH, "r", encoding="utf-8") as f:
        transcripts = json.load(f)

    print(f"Loaded {len(transcripts)} parsed transcripts")

    # Load existing results for incremental processing
    existing_results = {}
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
            for r in existing_data:
                existing_results[r["id"]] = r
        print(f"Found {len(existing_results)} existing analysis results (will skip these)")

    results = []
    analyzed = 0
    skipped = 0
    errors = 0

    for i, transcript in enumerate(transcripts):
        tid = transcript["id"]

        # Skip if already analyzed
        if tid in existing_results:
            results.append(existing_results[tid])
            skipped += 1
            continue

        # Skip very short transcripts (likely wrong numbers / no conversation)
        if transcript["stats"]["total_turns"] < 4:
            print(f"  [{i+1}/{len(transcripts)}] SKIP (too short, {transcript['stats']['total_turns']} turns): {tid[:60]}")
            result = {
                "id": tid,
                "filename": transcript["filename"],
                "metadata": transcript["metadata"],
                "stats": transcript["stats"],
                "analysis": None,
                "skip_reason": "too_short",
            }
            results.append(result)
            skipped += 1
            continue

        print(f"  [{i+1}/{len(transcripts)}] Analyzing: {tid[:60]}...")

        try:
            analysis = analyze_transcript(
                client, transcript["full_text"], transcript.get("metadata")
            )

            result = {
                "id": tid,
                "filename": transcript["filename"],
                "metadata": transcript["metadata"],
                "stats": transcript["stats"],
                "analysis": analysis,
            }
            results.append(result)
            analyzed += 1

            # Save incrementally every 5 transcripts
            if analyzed % 5 == 0:
                with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                print(f"    Saved checkpoint ({analyzed} analyzed so far)")

            # Small delay for rate limiting
            time.sleep(0.3)

        except Exception as e:
            print(f"    ERROR: {e}")
            result = {
                "id": tid,
                "filename": transcript["filename"],
                "metadata": transcript["metadata"],
                "stats": transcript["stats"],
                "analysis": None,
                "error": str(e),
            }
            results.append(result)
            errors += 1
            time.sleep(2)

    # Preserve existing results not in current parsed set (avoid data loss)
    current_ids = set(r["id"] for r in results)
    preserved = 0
    for eid, eresult in existing_results.items():
        if eid not in current_ids:
            results.append(eresult)
            preserved += 1

    # Final save
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"DONE!")
    print(f"  Analyzed: {analyzed}")
    print(f"  Skipped (existing + short): {skipped}")
    print(f"  Preserved (not in current parse): {preserved}")
    print(f"  Errors: {errors}")
    print(f"  Total: {len(results)}")
    print(f"  Saved to {OUTPUT_PATH}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
