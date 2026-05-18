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
OUTPUT_DIR = ROOT_DIR / "data"
OUTPUT_PATH = OUTPUT_DIR / "parsed_transcripts.json"

# List of (transcript_dir, csv_path) batches to process.
# Add new batches at the end. Existing batches MUST stay so old data is preserved.
# Filename collisions are resolved by first-occurrence wins (earlier batches take priority).
BATCHES = [
    (ROOT_DIR / "transcripts", ROOT_DIR / "counsellor-calls-all.csv"),
    (
        ROOT_DIR / "batches" / "batch-may-14th-may",
        ROOT_DIR / "batches" / "batch-may-14th-may" / "calls for transcription 13 May.csv",
    ),
    (
        ROOT_DIR / "batches" / "batch-may-14th-may-2",
        # Reuse the master CSV from the first May 14 batch (covers both batches)
        ROOT_DIR / "batches" / "batch-may-14th-may" / "calls for transcription 13 May.csv",
    ),
    (
        ROOT_DIR / "batches" / "batch-may-14th-may-3",
        ROOT_DIR / "batches" / "batch-may-14th-may" / "calls for transcription 13 May.csv",
    ),
    (
        ROOT_DIR / "batches" / "batch-may-14th-may-4",
        ROOT_DIR / "batches" / "batch-may-14th-may" / "calls for transcription 13 May.csv",
    ),
]

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


def load_csv_metadata(csv_path: Path) -> dict:
    """Load a single CSV and create lookup by transcript filename.

    Indexes each row under multiple keys to handle filename variants:
      - raw basename + ".html"  (e.g. "1777566100779audio_X.mp3.html")
      - basename with leading 10-16 digit timestamp prefix stripped + ".html"
        (e.g. "audio_X.mp3.html")
    """
    metadata = {}
    if not csv_path.exists():
        print(f"  WARNING: CSV not found: {csv_path}")
        return metadata
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            file_url = row.get("file_url", "")
            base = os.path.basename(file_url)
            try:
                duration = float(row.get("duration", 0) or 0)
            except (TypeError, ValueError):
                duration = 0.0
            row_meta = {
                "counsellor_id": row.get("counsellor_id", ""),
                "counsellor_name": row.get("counsellor_name", ""),
                "team_id": row.get("team_id", ""),
                "team_name": row.get("team_name", ""),
                "user_id": row.get("user_id", ""),
                "mobile_number": row.get("mobile_number", ""),
                "file_name": row.get("file_name", ""),
                "duration": duration,
                "file_creation_date": row.get("file_creation_date", ""),
                "stage_id": row.get("stageId", ""),
                "stage_name": row.get("stage_name", ""),
                "created_on": row.get("created_on", ""),
                "added_on": row.get("addedOn", ""),
                "_source_csv": csv_path.name,
                "_source_file_url": file_url,
            }
            keys = {base + ".html"}
            # Try stripping each possible Shiksha timestamp prefix length (10-16 digits).
            # Greedy regex would over-consume when the underlying filename also starts
            # with digits (e.g. mobile-prefixed recordings like "0091...").
            m = re.match(r"^(\d{10,16})", base)
            if m:
                run = m.group(1)
                for n in range(10, len(run) + 1):
                    stripped = base[n:]
                    if stripped:
                        keys.add(stripped + ".html")
            for k in keys:
                # First occurrence wins (don't overwrite a more specific match)
                if k not in metadata:
                    metadata[k] = row_meta
    return metadata


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    results = []
    seen_ids = set()
    total_matched = 0
    total_unmatched = []

    for batch_idx, (transcript_dir, csv_path) in enumerate(BATCHES, start=1):
        print(f"\n=== Batch {batch_idx}: {transcript_dir.name} ===")

        if not transcript_dir.exists():
            print(f"  WARNING: transcript dir missing, skipping: {transcript_dir}")
            continue

        # Load CSV metadata for this batch
        print(f"  Loading CSV: {csv_path.name}")
        csv_metadata = load_csv_metadata(csv_path)
        print(f"    {len(csv_metadata)} rows in CSV")

        html_files = sorted(transcript_dir.glob("*.html"))
        print(f"  Found {len(html_files)} HTML files")

        batch_added = 0
        batch_skipped_dupes = 0
        for filepath in html_files:
            tid = filepath.stem
            if tid in seen_ids:
                batch_skipped_dupes += 1
                continue

            parsed = parse_html_transcript(filepath)
            if filepath.name in csv_metadata:
                parsed["metadata"] = csv_metadata[filepath.name]
                total_matched += 1
            else:
                parsed["metadata"] = None
                total_unmatched.append(filepath.name)

            parsed["id"] = tid
            parsed["_batch"] = transcript_dir.name
            results.append(parsed)
            seen_ids.add(tid)
            batch_added += 1

        print(f"  Added: {batch_added}, skipped (dupe filename across batches): {batch_skipped_dupes}")

    print(f"\n=== Summary ===")
    print(f"  Total parsed: {len(results)}")
    print(f"  Matched with CSV: {total_matched}")
    print(f"  Unmatched: {len(total_unmatched)}")
    if total_unmatched:
        for uf in total_unmatched[:10]:
            print(f"    - {uf}")
        if len(total_unmatched) > 10:
            print(f"    ... and {len(total_unmatched) - 10} more")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nSaved to {OUTPUT_PATH}")
    if results:
        s = results[0]["stats"]
        print(f"Sample stats from first transcript:")
        print(f"  Turns: {s['total_turns']}, Words: {s['total_words']}, Talk ratio: {s['talk_ratio']}")


if __name__ == "__main__":
    main()
