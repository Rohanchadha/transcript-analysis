"""
Extract golden test cases from analyzed human counsellor transcripts.
Creates 3 test files:
  - query_tests.json: Student queries with counsellor reference responses
  - fact_tests.json: Factual college data verification tests
  - objection_tests.json: Objection handling test scenarios

Usage:
  python eval/golden_tests/extract_test_cases.py
"""

import json
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
OUT = Path(__file__).resolve().parent


def load_data():
    with open(DATA / "analysis_results.json", "r", encoding="utf-8") as f:
        analysis = json.load(f)
    with open(DATA / "parsed_transcripts.json", "r", encoding="utf-8") as f:
        transcripts = json.load(f)
    tmap = {t["id"]: t for t in transcripts}
    return analysis, tmap


def find_counsellor_response(turns: list, quote: str, window: int = 5) -> str:
    """Find the counsellor's response that follows a student quote in the transcript."""
    if not quote or not turns:
        return ""

    q_lower = quote[:35].lower().strip()

    # Find the turn index where this quote appears (from User)
    match_idx = -1
    for i, turn in enumerate(turns):
        if turn["speaker"] == "User" and q_lower in turn["text"].lower():
            match_idx = i
            break

    if match_idx == -1:
        return ""

    # Collect the next counsellor turns (up to `window` turns)
    response_parts = []
    for j in range(match_idx + 1, min(match_idx + 1 + window, len(turns))):
        if turns[j]["speaker"] == "Counsellor":
            response_parts.append(turns[j]["text"])
        elif turns[j]["speaker"] == "User" and response_parts:
            break  # Stop when user speaks again after counsellor has responded
    return " ".join(response_parts)


def get_conversation_context(turns: list, quote: str, context_turns: int = 6) -> str:
    """Get the conversation context leading up to a quote."""
    if not quote or not turns:
        return ""

    q_lower = quote[:35].lower().strip()
    match_idx = -1
    for i, turn in enumerate(turns):
        if q_lower in turn["text"].lower():
            match_idx = i
            break

    if match_idx == -1:
        return ""

    start = max(0, match_idx - context_turns)
    context_lines = []
    for t in turns[start:match_idx + 1]:
        context_lines.append(f"{t['speaker']}: {t['text']}")
    return "\n".join(context_lines)


def is_counsellor_quote(turns: list, quote: str) -> bool:
    """Check if a quote is actually from the Counsellor."""
    if not quote:
        return False
    q_lower = quote[:40].lower().strip()
    for turn in turns:
        if turn["speaker"] == "Counsellor" and (
            q_lower in turn["text"].lower() or turn["text"].lower().startswith(q_lower[:25])
        ):
            return True
    return False


def extract_query_tests(analysis, tmap):
    """Extract student query test cases with counsellor reference responses."""
    tests = []
    seen_queries = set()

    for record in analysis:
        if not record.get("analysis"):
            continue

        call_id = record["id"]
        tr = tmap.get(call_id)
        if not tr:
            continue

        turns = tr.get("turns", [])
        profile = record["analysis"]["student_profile"]

        for q in record["analysis"].get("query_buckets", []):
            quote = q.get("quote", "").strip()
            query_text = q.get("query", "").strip()

            # Skip counsellor questions
            if is_counsellor_quote(turns, quote):
                continue

            # Deduplicate similar queries
            dedup_key = query_text[:50].lower()
            if dedup_key in seen_queries:
                continue
            seen_queries.add(dedup_key)

            # Find the counsellor's actual response
            reference_response = find_counsellor_response(turns, quote)
            if not reference_response:
                continue

            # Get conversation context
            context = get_conversation_context(turns, quote)

            test = {
                "id": f"query_{len(tests)+1:03d}",
                "type": "student_query",
                "bucket": q.get("bucket", ""),
                "call_id": call_id,
                "student_profile": profile,
                "query_hindi": quote,
                "query_english": q.get("translation", ""),
                "conversation_context": context,
                "reference_response": reference_response,
                "counsellor": record["metadata"]["counsellor_name"] if record.get("metadata") else "Unknown",
            }
            tests.append(test)

    return tests


def extract_fact_tests(analysis):
    """Extract factual verification tests from college data discussed in calls."""
    tests = []
    seen = set()

    for record in analysis:
        if not record.get("analysis"):
            continue

        profile = record["analysis"]["student_profile"]

        for college in record["analysis"].get("colleges_discussed", []):
            name = college["name"]
            fee = college.get("fee_mentioned", "")
            placement = college.get("placement_mentioned", "")
            location = college.get("location", "")

            if fee and fee.lower() != "not_mentioned":
                key = f"{name}__fee"
                if key not in seen:
                    seen.add(key)
                    tests.append({
                        "id": f"fact_{len(tests)+1:03d}",
                        "type": "factual_accuracy",
                        "category": "fee",
                        "college_name": name,
                        "college_location": location,
                        "question": f"What is the fee for {profile['course_interest']} at {name}?",
                        "expected_answer": fee,
                        "course": profile["course_interest"],
                        "call_id": record["id"],
                    })

            if placement and placement.lower() != "not_mentioned":
                key = f"{name}__placement"
                if key not in seen:
                    seen.add(key)
                    tests.append({
                        "id": f"fact_{len(tests)+1:03d}",
                        "type": "factual_accuracy",
                        "category": "placement",
                        "college_name": name,
                        "college_location": location,
                        "question": f"What are the placement statistics at {name}?",
                        "expected_answer": placement,
                        "course": profile["course_interest"],
                        "call_id": record["id"],
                    })

    return tests


def extract_objection_tests(analysis, tmap):
    """Extract objection handling test scenarios."""
    tests = []
    seen = set()

    for record in analysis:
        if not record.get("analysis"):
            continue

        call_id = record["id"]
        tr = tmap.get(call_id)
        turns = tr.get("turns", []) if tr else []
        profile = record["analysis"]["student_profile"]

        for obj in record["analysis"].get("objections", []):
            objection = obj.get("objection", "").strip()
            student_quote = obj.get("student_quote", "").strip()
            counsellor_quote = obj.get("counsellor_quote", "").strip()
            obj_type = obj.get("objection_type", "other")

            if not student_quote:
                continue

            # Deduplicate
            dedup_key = student_quote[:40].lower()
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            # Get conversation context
            context = get_conversation_context(turns, student_quote)

            test = {
                "id": f"objection_{len(tests)+1:03d}",
                "type": "objection_handling",
                "objection_type": obj_type,
                "objection_description": objection,
                "call_id": call_id,
                "student_profile": profile,
                "student_quote_hindi": student_quote,
                "conversation_context": context,
                "reference_counsellor_response": counsellor_quote,
                "handling_strategy": obj.get("handling_strategy", ""),
                "was_resolved_by_human": obj.get("was_resolved", False),
                "counsellor": record["metadata"]["counsellor_name"] if record.get("metadata") else "Unknown",
            }
            tests.append(test)

    return tests


def main():
    print("Loading data...")
    analysis, tmap = load_data()
    results = [r for r in analysis if r.get("analysis")]
    print(f"  {len(results)} analyzed calls, {len(tmap)} transcripts")

    print("\nExtracting query test cases...")
    query_tests = extract_query_tests(analysis, tmap)
    print(f"  Extracted {len(query_tests)} query tests")

    print("\nExtracting fact verification tests...")
    fact_tests = extract_fact_tests(analysis)
    print(f"  Extracted {len(fact_tests)} fact tests")

    print("\nExtracting objection handling tests...")
    objection_tests = extract_objection_tests(analysis, tmap)
    print(f"  Extracted {len(objection_tests)} objection tests")

    total = len(query_tests) + len(fact_tests) + len(objection_tests)
    print(f"\n{'='*50}")
    print(f"TOTAL: {total} golden test cases")
    print(f"{'='*50}")

    # Bucket distribution for queries
    from collections import Counter
    bucket_dist = Counter(t["bucket"] for t in query_tests)
    print("\nQuery bucket distribution:")
    for b, c in bucket_dist.most_common():
        print(f"  {b}: {c}")

    obj_dist = Counter(t["objection_type"] for t in objection_tests)
    print("\nObjection type distribution:")
    for o, c in obj_dist.most_common():
        print(f"  {o}: {c}")

    fact_dist = Counter(t["category"] for t in fact_tests)
    print("\nFact test distribution:")
    for f, c in fact_dist.most_common():
        print(f"  {f}: {c}")

    # Save
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "query_tests.json", "w", encoding="utf-8") as f:
        json.dump(query_tests, f, ensure_ascii=False, indent=2)
    with open(OUT / "fact_tests.json", "w", encoding="utf-8") as f:
        json.dump(fact_tests, f, ensure_ascii=False, indent=2)
    with open(OUT / "objection_tests.json", "w", encoding="utf-8") as f:
        json.dump(objection_tests, f, ensure_ascii=False, indent=2)

    print(f"\nSaved to {OUT}/")


if __name__ == "__main__":
    main()
