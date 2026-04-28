"""
Parse HTML transcript files and link with CSV metadata.
Outputs: data/parsed_transcripts.json
"""

import csv
import json
import os
import re
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
TRANSCRIPT_DIR = ROOT_DIR / "transcript"
CSV_PATH = ROOT_DIR / "counsellor-calls-to-be-transcribed-100.csv"
OUTPUT_DIR = ROOT_DIR / "data"
OUTPUT_PATH = OUTPUT_DIR / "parsed_transcripts.json"

# Pattern: [MM:SS - MM:SS] Speaker: text
DIALOGUE_PATTERN = re.compile(
    r"\[(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})\]\s*(Counsellor|User):\s*(.*)"
)


def parse_timestamp(ts: str) -> int:
    """Convert MM:SS to total seconds."""
    parts = ts.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def parse_html_transcript(filepath: Path) -> dict:
    """Parse a single HTML transcript file using regex on raw HTML."""
    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()

    # Extract text between <p> tags, then match dialogue pattern
    # Using regex directly on HTML since structure is uniform
    p_texts = re.findall(r"<p>(.*?)</p>", html, re.DOTALL)

    turns = []
    for p_html in p_texts:
        # Strip HTML tags to get plain text
        plain = re.sub(r"<[^>]+>", "", p_html).strip()
        match = DIALOGUE_PATTERN.search(plain)
        if match:
            start_ts, end_ts, speaker, dialogue = match.groups()
            turns.append(
                {
                    "start_time": start_ts,
                    "end_time": end_ts,
                    "start_seconds": parse_timestamp(start_ts),
                    "end_seconds": parse_timestamp(end_ts),
                    "speaker": speaker,
                    "text": dialogue.strip(),
                }
            )

    # Compute stats
    counsellor_words = sum(
        len(t["text"].split()) for t in turns if t["speaker"] == "Counsellor"
    )
    user_words = sum(
        len(t["text"].split()) for t in turns if t["speaker"] == "User"
    )
    total_turns = len(turns)
    counsellor_turns = sum(1 for t in turns if t["speaker"] == "Counsellor")
    user_turns = sum(1 for t in turns if t["speaker"] == "User")

    # Full text for LLM analysis
    full_text = "\n".join(
        f"[{t['start_time']} - {t['end_time']}] {t['speaker']}: {t['text']}"
        for t in turns
    )

    return {
        "filename": filepath.name,
        "turns": turns,
        "stats": {
            "total_turns": total_turns,
            "counsellor_turns": counsellor_turns,
            "user_turns": user_turns,
            "counsellor_words": counsellor_words,
            "user_words": user_words,
            "total_words": counsellor_words + user_words,
            "talk_ratio": round(counsellor_words / max(user_words, 1), 2),
        },
        "full_text": full_text,
    }


def load_csv_metadata() -> dict:
    """Load CSV and create lookup by transcript filename."""
    metadata = {}
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Transcript filename = basename of file_url + ".html"
            file_url = row.get("file_url", "")
            transcript_filename = os.path.basename(file_url) + ".html"
            metadata[transcript_filename] = {
                "counsellor_id": row.get("counsellor_id", ""),
                "counsellor_name": row.get("counsellor_name", ""),
                "team_id": row.get("team_id", ""),
                "team_name": row.get("team_name", ""),
                "user_id": row.get("user_id", ""),
                "mobile_number": row.get("mobile_number", ""),
                "file_name": row.get("file_name", ""),
                "duration": float(row.get("duration", 0)),
                "file_creation_date": row.get("file_creation_date", ""),
                "stage_id": row.get("stageId", ""),
                "stage_name": row.get("stage_name", ""),
                "created_on": row.get("created_on", ""),
                "added_on": row.get("addedOn", ""),
            }
    return metadata


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Load CSV metadata
    print("Loading CSV metadata...")
    csv_metadata = load_csv_metadata()
    print(f"  Found {len(csv_metadata)} rows in CSV")

    # Parse all transcripts
    html_files = sorted(TRANSCRIPT_DIR.glob("*.html"))
    print(f"Found {len(html_files)} HTML transcript files")

    results = []
    matched = 0
    unmatched = []

    for filepath in html_files:
        parsed = parse_html_transcript(filepath)

        # Link metadata
        if filepath.name in csv_metadata:
            parsed["metadata"] = csv_metadata[filepath.name]
            matched += 1
        else:
            parsed["metadata"] = None
            unmatched.append(filepath.name)

        # Assign an ID
        parsed["id"] = filepath.stem  # filename without .html
        results.append(parsed)

    print(f"\nResults:")
    print(f"  Total parsed: {len(results)}")
    print(f"  Matched with CSV: {matched}")
    print(f"  Unmatched: {len(unmatched)}")
    if unmatched:
        for uf in unmatched[:10]:
            print(f"    - {uf}")
        if len(unmatched) > 10:
            print(f"    ... and {len(unmatched) - 10} more")

    # Save
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nSaved to {OUTPUT_PATH}")
    print(f"Sample stats from first transcript:")
    if results:
        s = results[0]["stats"]
        print(f"  Turns: {s['total_turns']}, Words: {s['total_words']}, Talk ratio: {s['talk_ratio']}")


if __name__ == "__main__":
    main()
