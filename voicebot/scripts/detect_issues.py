"""Detect issues in voice-bot calls.

Two layers:
  A. Deterministic rules grounded in prompts/voice_bot_system_prompt.md
  B. GPT-4o-mini classifier over the conversation, with rule flags as priors

Output: voicebot/data/issues.json. Incremental on call_sid, checkpoint every 5.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT_DIR / ".env")

DATA_DIR = ROOT_DIR / "voicebot" / "data"
SYSTEM_PROMPT_PATH = ROOT_DIR / "prompts" / "voice_bot_system_prompt.md"

# ---------- Layer A: deterministic rules ----------

# Devanagari "shuddh hindi" words that the prompt explicitly bans
SHUDDH_HINDI_WORDS = ["कृपया", "धन्यवाद", "विवरण", "बताइए", "पाठ्यक्रम", "विशिष्ट"]

# Names other than Neha that the bot should never use
FORBIDDEN_NAMES = ["riya", "priya", "shreya", "anjali", "pooja", "sneha", "meera", "kavya", "ritika"]

# Phrases indicating tool/function leakage
TOOL_LEAK_PATTERNS = [
    r"\blet me search\b",
    r"\bsearching\b",
    r"\bfunction call\b",
    r"\btool call\b",
    r"\bget_college_recommendations\b",
    r"\bapi\b",
]

# User-side confusion markers (Hindi/English mixed)
USER_CONFUSION_PATTERNS = [
    r"\bक्या\?",
    r"\bkya\?",
    r"samajh\s*nahi\s*aaya",
    r"samajh\s*nahin\s*aaya",
    r"\brepeat\b",
    r"\bpardon\b",
    r"\bphir se\b",
    r"\bdobara\b",
    r"\bwhat did you say\b",
]

CLOSING_PHRASE = "thank you, have a great day"

# Tuned thresholds (after first-pass review)
LATENCY_TURN_THRESHOLD_SEC = 5.0     # only flag truly long pauses
LENGTH_SENTENCE_LIMIT = 4            # relaxed from 2 (system prompt) to reduce false positives
LENGTH_QUESTION_LIMIT = 2            # relaxed from 1
ASR_LOW_CONFIDENCE_THRESHOLD = 0.5


def _count_sentences(text: str) -> int:
    # Count sentence-ending punctuation; treat consecutive separators as one
    parts = [p for p in re.split(r"[.!?।]+", text) if p.strip()]
    return max(1, len(parts))


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _looks_like_college_recommendation(text: str) -> bool:
    # College indicator: contains words like "IIT", "NIT", "IIIT", "VIT", "BITS", "college", "university", or named institute
    indicators = [
        r"\bIIT\b", r"\bNIT\b", r"\bIIIT\b", r"\bVIT\b", r"\bBITS\b",
        r"\bSRM\b", r"\bManipal\b", r"\bAmity\b", r"\bKIIT\b", r"\bSOA\b",
        r"\bcollege\b", r"\buniversity\b", r"\binstitute\b",
    ]
    return any(re.search(p, text, flags=re.IGNORECASE) for p in indicators)


def _has_qualification(turns: list[dict], up_to_index: int) -> bool:
    """Has user provided BOTH JEE percentile AND 12th % by turn index `up_to_index`?"""
    user_text = " ".join(
        t["text"].lower() for t in turns[:up_to_index] if t.get("role") == "user"
    )
    has_jee = bool(re.search(r"\b(percentile|jee|\d{2,3}\s*percentile|\d{2,3}\s*%)", user_text))
    has_12th = bool(re.search(r"(12th|twelfth|board|\d{2,3}\s*%|\d{2,3}\s*percent|out of)", user_text))
    return has_jee and has_12th


def detect_rule_issues(call: dict) -> list[dict]:
    issues: list[dict] = []
    turns = call["turns"]
    stats = call["stats"]
    nodes = set(call["metadata"].get("nodes_asked") or [])

    # Repetition tracking
    seen_assistant_texts: Counter[str] = Counter()

    for turn in turns:
        role = turn.get("role")
        text = turn.get("text") or ""
        idx = turn.get("index")

        if role == "assistant" and not turn.get("is_filler"):
            # name_violation
            for name in FORBIDDEN_NAMES:
                if re.search(rf"\b{name}\b", text, flags=re.IGNORECASE):
                    issues.append({
                        "category": "name_violation",
                        "severity": "high",
                        "source": "rule",
                        "turn_index": idx,
                        "bot_quote": text,
                        "explanation": f"Bot referred to itself as '{name}' instead of 'Neha'.",
                    })
                    break

            # length_violation (relaxed: only flag clearly excessive turns)
            sentences = _count_sentences(text)
            questions = text.count("?")
            if sentences > LENGTH_SENTENCE_LIMIT or questions > LENGTH_QUESTION_LIMIT:
                issues.append({
                    "category": "length_violation",
                    "severity": "low",
                    "source": "rule",
                    "turn_index": idx,
                    "bot_quote": text,
                    "explanation": f"Turn is unusually long: {sentences} sentences / {questions} questions (relaxed limit: {LENGTH_SENTENCE_LIMIT}/{LENGTH_QUESTION_LIMIT}).",
                })

            # tool_name_leak
            for pat in TOOL_LEAK_PATTERNS:
                if re.search(pat, text, flags=re.IGNORECASE):
                    issues.append({
                        "category": "tool_name_leak",
                        "severity": "medium",
                        "source": "rule",
                        "turn_index": idx,
                        "bot_quote": text,
                        "explanation": f"Bot leaked tool/function reference matching '{pat}'.",
                    })
                    break

            # shuddh_hindi
            for word in SHUDDH_HINDI_WORDS:
                if word in text:
                    issues.append({
                        "category": "shuddh_hindi",
                        "severity": "low",
                        "source": "rule",
                        "turn_index": idx,
                        "bot_quote": text,
                        "explanation": f"Bot used banned Shuddh Hindi word '{word}'.",
                    })
                    break

            # repetition
            norm = _normalize(text)
            if norm:
                seen_assistant_texts[norm] += 1
                if seen_assistant_texts[norm] == 2:
                    issues.append({
                        "category": "repetition_loop",
                        "severity": "medium",
                        "source": "rule",
                        "turn_index": idx,
                        "bot_quote": text,
                        "explanation": "Bot repeated the same line later in the call.",
                    })

            # high latency per turn (only truly long pauses)
            lat = turn.get("latency_sec")
            if isinstance(lat, (int, float)) and lat > LATENCY_TURN_THRESHOLD_SEC:
                issues.append({
                    "category": "latency_perceived",
                    "severity": "medium",
                    "source": "rule",
                    "turn_index": idx,
                    "bot_quote": text,
                    "explanation": f"Bot took {lat:.2f}s to respond (threshold: {LATENCY_TURN_THRESHOLD_SEC}s) — student may perceive this as a hang.",
                })

            # ASR low confidence on the IMMEDIATELY PRECEDING user turn
            # If a user turn had low ASR confidence and the bot's next response doesn't
            # actually address it (we approximate this by always flagging the user turn,
            # not the bot turn). Bot-side ASR breakdown is captured per-user-turn below.

        elif role == "user":
            # user_confusion_marker
            for pat in USER_CONFUSION_PATTERNS:
                if re.search(pat, text, flags=re.IGNORECASE):
                    issues.append({
                        "category": "user_confusion_marker",
                        "severity": "medium",
                        "source": "rule",
                        "turn_index": idx,
                        "user_quote": text,
                        "explanation": "User signalled confusion or asked for repetition.",
                    })
                    break

            # ASR low confidence on this user turn
            asr_min = turn.get("asr_min_confidence")
            if isinstance(asr_min, (int, float)) and asr_min < ASR_LOW_CONFIDENCE_THRESHOLD:
                issues.append({
                    "category": "asr_intent_breakdown",
                    "severity": "medium",
                    "source": "rule",
                    "turn_index": idx,
                    "user_quote": text,
                    "explanation": (
                        f"Speech-to-text (Deepgram) had low confidence on the student's words "
                        f"(min word confidence {asr_min:.2f} < {ASR_LOW_CONFIDENCE_THRESHOLD}). "
                        f"This means the bot likely 'heard' something different from what the student actually said, "
                        f"so any reply may be answering the wrong question."
                    ),
                })

    # Call-level rules
    # ASR overall low (call-level)
    asr_avg = stats.get("asr_avg_overall")
    if isinstance(asr_avg, (int, float)) and asr_avg < 0.7:
        issues.append({
            "category": "asr_intent_breakdown",
            "severity": "high",
            "source": "rule",
            "turn_index": None,
            "explanation": (
                f"Across the whole call, average speech-to-text confidence was {asr_avg:.2f} (< 0.70). "
                f"Indicates the bot was consistently mis-hearing the student — likely accent, background noise, "
                f"or code-mixing the ASR engine couldn't handle."
            ),
        })

    return issues


# ---------- Layer B: LLM detection ----------

LLM_SYSTEM = """You are evaluating a voice-bot ("Neha") call against its system prompt.

Flag ONLY these specific issues:

1. unanswered_query — The STUDENT asked a question or made a clear request, and the BOT either ignored it, gave a vague non-answer, or pivoted to a different topic without addressing it. CRITICAL: this is ONLY when the STUDENT asks something the BOT fails to answer. Do NOT flag cases where the bot asks a question and the student doesn't answer — that is the opposite direction and is NOT an issue with the bot.

2. topic_deviation — The bot drifted off the B.Tech admissions topic, brought up irrelevant subjects, or failed to bring a wandering conversation back on track.

3. repetition_loop — The bot repeated the same line/question multiple times, or got stuck cycling through the same prompts.

4. asr_intent_breakdown — The bot's reply makes it clear it misheard or misunderstood what the student said (e.g. student said one college and bot replied about another, or bot's response is a non-sequitur to the user's actual words).

5. student_frustration — The student showed clear frustration, irritation, or disengagement (sighing, terse "haan haan haan", "nahi nahi nahi", hanging up abruptly, repeated "kya?").

6. hallucination — The bot stated a specific fact about a college, fee, placement, cutoff, or process that appears invented or unverifiable from context.

7. latency_perceived — The student explicitly noted or reacted to a delay ("hello?", "are you there?", awkward silence acknowledged).

DO NOT flag: tone/empathy, failed handoffs, premature recommendations, length violations — these are out of scope.

Output STRICT JSON only. Be CONSERVATIVE — only flag clear issues with verbatim evidence. Reference the turn_index field shown in [#N] markers.
"""

LLM_USER_TEMPLATE = """SYSTEM PROMPT THE BOT WAS TOLD TO FOLLOW:
<<<
{system_prompt}
>>>

DETERMINISTIC RULE FLAGS ALREADY DETECTED (use as priors, do not re-list these unless adding nuance):
{rule_flag_summary}

CONVERSATION (each line tagged [#turn_index] role: text):
{conversation}

Return JSON with this exact schema:
{{
  "issues": [
    {{
      "category": "unanswered_query|topic_deviation|repetition_loop|asr_intent_breakdown|student_frustration|hallucination|latency_perceived|other",
      "severity": "low|medium|high",
      "turn_index": <int or null>,
      "user_quote": "verbatim user line if relevant, else empty string",
      "bot_quote": "verbatim bot line if relevant, else empty string",
      "explanation": "1-2 sentences",
      "suggested_fix": "actionable suggestion for prompt/bot team"
    }}
  ],
  "call_summary": "2-3 sentence summary of how the call went",
  "overall_quality": "good|mediocre|poor",
  "qualification_completed": true/false,
  "primary_failure_mode": "one category from the list above, or 'none'"
}}
"""


def format_conversation(turns: list[dict], max_turns: int = 80) -> str:
    lines = []
    for t in turns[:max_turns]:
        if t.get("is_filler"):
            continue
        idx = t.get("index")
        role = t.get("role", "?")
        text = (t.get("text") or "").replace("\n", " ")
        lines.append(f"[#{idx}] {role}: {text}")
    return "\n".join(lines)


def summarize_rule_flags(rule_issues: list[dict]) -> str:
    if not rule_issues:
        return "(none)"
    cats: Counter[str] = Counter()
    for it in rule_issues:
        cats[it["category"]] += 1
    return ", ".join(f"{c}:{n}" for c, n in cats.most_common())


def detect_llm_issues(call: dict, rule_issues: list[dict], system_prompt: str, client) -> dict:
    user_msg = LLM_USER_TEMPLATE.format(
        system_prompt=system_prompt[:6000],  # cap to control tokens
        rule_flag_summary=summarize_rule_flags(rule_issues),
        conversation=format_conversation(call["turns"]),
    )
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": LLM_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=2500,
    )
    content = resp.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = {"issues": [], "call_summary": "", "overall_quality": "mediocre",
                "qualification_completed": False, "primary_failure_mode": "none",
                "_parse_error": True}
    # Tag issues with source
    for it in data.get("issues", []) or []:
        it["source"] = "llm"
    return data


# ---------- Driver ----------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=str, default="v1", help="Dataset name (file suffix)")
    args = ap.parse_args()

    input_path = DATA_DIR / f"parsed_calls__{args.dataset}.json"
    output_path = DATA_DIR / f"issues__{args.dataset}.json"

    if not input_path.exists():
        sys.exit(f"missing {input_path}; run parse_calls.py --dataset {args.dataset} first")
    with input_path.open("r", encoding="utf-8") as f:
        calls = json.load(f)
    print(f"dataset: {args.dataset}  loaded {len(calls)} parsed calls")

    if not SYSTEM_PROMPT_PATH.exists():
        sys.exit(f"missing {SYSTEM_PROMPT_PATH}")
    system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

    use_llm = bool(os.getenv("OPENAI_API_KEY"))
    client = None
    if use_llm:
        from openai import OpenAI  # type: ignore
        client = OpenAI()
        print("LLM detection: enabled (gpt-4o-mini)")
    else:
        print("LLM detection: DISABLED (no OPENAI_API_KEY) — rule-based only")

    existing: dict[str, dict] = {}
    if output_path.exists():
        with output_path.open("r", encoding="utf-8") as f:
            for r in json.load(f):
                if r.get("call_sid"):
                    existing[r["call_sid"]] = r
        print(f"existing detections: {len(existing)} (will skip)")

    results: list[dict] = []
    analyzed = 0
    skipped = 0
    skipped_no_user = 0

    for call in calls:
        sid = call["call_sid"]
        if sid in existing:
            results.append(existing[sid])
            skipped += 1
            continue

        # Skip calls with no user turns (student never spoke) — saves LLM tokens
        if (call.get("stats", {}).get("user_turns") or 0) == 0:
            results.append({
                "call_sid": sid,
                "metadata": call["metadata"],
                "stats": call["stats"],
                "transcript_source": call.get("transcript_source"),
                "issues": [],
                "issue_count": 0,
                "category_counts": {},
                "call_summary": "Student did not speak (no user turns).",
                "overall_quality": "no_engagement",
                "qualification_completed": False,
                "primary_failure_mode": "none",
                "skipped_reason": "no_user_turns",
            })
            skipped_no_user += 1
            continue

        rule_issues = detect_rule_issues(call)
        llm_data: dict[str, Any] = {}
        if use_llm:
            try:
                llm_data = detect_llm_issues(call, rule_issues, system_prompt, client)
            except Exception as e:  # noqa: BLE001
                print(f"  LLM error on {sid}: {e}")
                llm_data = {"issues": [], "_llm_error": str(e)}

        all_issues = rule_issues + (llm_data.get("issues") or [])
        category_counts: Counter[str] = Counter(i["category"] for i in all_issues)

        record = {
            "call_sid": sid,
            "metadata": call["metadata"],
            "stats": call["stats"],
            "transcript_source": call.get("transcript_source"),
            "issues": all_issues,
            "issue_count": len(all_issues),
            "category_counts": dict(category_counts),
            "call_summary": llm_data.get("call_summary", ""),
            "overall_quality": llm_data.get("overall_quality", "unknown"),
            "qualification_completed": llm_data.get("qualification_completed"),
            "primary_failure_mode": llm_data.get("primary_failure_mode", "none"),
        }
        results.append(record)
        analyzed += 1

        if analyzed % 5 == 0:
            with output_path.open("w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"  checkpoint: {analyzed} analyzed, {skipped} skipped")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"done: {analyzed} analyzed, {skipped} already-cached, {skipped_no_user} skipped (no user turns), total {len(results)}")
    print(f"wrote {output_path}")


if __name__ == "__main__":
    main()
