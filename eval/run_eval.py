"""
Evaluation runner — sends test cases to the bot API, collects responses,
and scores them using the LLM judge.

Usage:
  # Set env vars
  $env:OPENAI_API_KEY = "sk-..."
  $env:BOT_API_URL = "https://your-bot.example.com/chat"

  # Run all tests
  python eval/run_eval.py

  # Run specific test type
  python eval/run_eval.py --type query
  python eval/run_eval.py --type fact
  python eval/run_eval.py --type objection

  # Limit number of tests (for quick checks)
  python eval/run_eval.py --limit 10

  # Use a specific bot version label
  python eval/run_eval.py --version "v2.1-improved-objections"
"""

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from runner.judge import judge_response
from runner.rubric import get_dimensions, compute_weighted_score

ROOT = Path(__file__).resolve().parent
GOLDEN = ROOT / "golden_tests"
REPORTS = ROOT / "reports"


def load_tests(test_type: str | None = None) -> list:
    """Load test cases, optionally filtered by type."""
    tests = []
    files = {
        "query": GOLDEN / "query_tests.json",
        "fact": GOLDEN / "fact_tests.json",
        "objection": GOLDEN / "objection_tests.json",
    }

    for typ, path in files.items():
        if test_type and typ != test_type:
            continue
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                tests.extend(json.load(f))

    return tests


def call_bot_api(question: str, context: dict, api_url: str) -> str:
    """Call the bot's text API and return the response.

    Override this function to match your bot's API contract.
    """
    import urllib.request

    payload = json.dumps({
        "message": question,
        "context": context,
    }).encode("utf-8")

    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            # Adapt this to your bot's response format
            return data.get("response", data.get("text", data.get("message", str(data))))
    except Exception as e:
        return f"[BOT_API_ERROR: {e}]"


def build_bot_question(test_case: dict) -> tuple[str, dict]:
    """Build the question and context to send to the bot API."""
    test_type = test_case["type"]

    if test_type == "student_query":
        question = test_case["query_hindi"]
        context = {
            "student_profile": test_case["student_profile"],
            "conversation_history": test_case.get("conversation_context", ""),
        }
    elif test_type == "factual_accuracy":
        question = test_case["question"]
        context = {"course": test_case.get("course", "")}
    elif test_type == "objection_handling":
        question = test_case["student_quote_hindi"]
        context = {
            "student_profile": test_case["student_profile"],
            "conversation_history": test_case.get("conversation_context", ""),
            "objection_type": test_case["objection_type"],
        }
    else:
        question = str(test_case)
        context = {}

    return question, context


def run_eval(
    test_type: str | None = None,
    limit: int | None = None,
    version: str = "default",
    bot_api_url: str | None = None,
    api_key: str | None = None,
    dry_run: bool = False,
):
    """Run the evaluation suite."""
    bot_url = bot_api_url or os.environ.get("BOT_API_URL", "")
    api_key = api_key or os.environ.get("OPENAI_API_KEY", "")

    tests = load_tests(test_type)
    if limit:
        tests = tests[:limit]

    if not tests:
        print("No test cases found. Run extract_test_cases.py first.")
        return

    print(f"{'='*60}")
    print(f"EVAL RUN: {version}")
    print(f"  Tests: {len(tests)}")
    print(f"  Bot API: {bot_url or '(dry-run / no API)'}")
    print(f"  Judge model: gpt-4o-mini")
    print(f"  Time: {datetime.now().isoformat()}")
    print(f"{'='*60}\n")

    results = []
    scores_by_type = {}
    scores_by_dim = {}

    for i, test in enumerate(tests):
        tid = test["id"]
        ttype = test["type"]
        print(f"  [{i+1}/{len(tests)}] {tid}...", end=" ", flush=True)

        # Get bot response
        if dry_run or not bot_url:
            bot_response = "(dry-run: no bot response)"
            print("DRY-RUN", end=" ")
        else:
            question, context = build_bot_question(test)
            bot_response = call_bot_api(question, context, bot_url)
            if bot_response.startswith("[BOT_API_ERROR"):
                print(f"ERROR: {bot_response}")
                results.append({"test_id": tid, "type": ttype, "error": bot_response})
                continue

        # Judge the response
        if dry_run:
            judgment = {
                "scores": {k: 0 for k in get_dimensions(ttype)},
                "justifications": {},
                "weighted_score": 0,
                "overall_notes": "dry-run",
            }
            print("OK (dry-run)")
        else:
            try:
                judgment = judge_response(test, bot_response, api_key=api_key)
                ws = judgment["weighted_score"]
                print(f"Score: {ws:.2f}")
            except Exception as e:
                print(f"JUDGE ERROR: {e}")
                results.append({"test_id": tid, "type": ttype, "error": str(e)})
                time.sleep(1)
                continue

        # Collect result
        result = {
            "test_id": tid,
            "type": ttype,
            "bot_response": bot_response,
            "judgment": judgment,
        }
        results.append(result)

        # Aggregate
        ws = judgment["weighted_score"]
        scores_by_type.setdefault(ttype, []).append(ws)
        for dim, score in judgment.get("scores", {}).items():
            scores_by_dim.setdefault(dim, []).append(score)

        time.sleep(0.3)

    # Print summary
    print(f"\n{'='*60}")
    print("RESULTS SUMMARY")
    print(f"{'='*60}")

    for ttype, scores in sorted(scores_by_type.items()):
        avg = sum(scores) / max(len(scores), 1)
        print(f"\n  {ttype} ({len(scores)} tests):")
        print(f"    Average weighted score: {avg:.2f} / 5.00")

    print(f"\n  Scores by dimension:")
    for dim, scores in sorted(scores_by_dim.items()):
        avg = sum(scores) / max(len(scores), 1)
        bar = "█" * int(avg) + "░" * (5 - int(avg))
        print(f"    {dim:30s} {avg:.2f}  {bar}")

    # Overall
    all_scores = [s for sl in scores_by_type.values() for s in sl]
    if all_scores:
        overall = sum(all_scores) / len(all_scores)
        print(f"\n  OVERALL SCORE: {overall:.2f} / 5.00")

    # Save report
    REPORTS.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = {
        "version": version,
        "timestamp": datetime.now().isoformat(),
        "config": {
            "test_type": test_type,
            "limit": limit,
            "bot_api_url": bot_url,
            "total_tests": len(tests),
        },
        "summary": {
            "overall_score": round(sum(all_scores) / max(len(all_scores), 1), 2) if all_scores else 0,
            "by_type": {t: round(sum(s) / len(s), 2) for t, s in scores_by_type.items()},
            "by_dimension": {d: round(sum(s) / len(s), 2) for d, s in scores_by_dim.items()},
        },
        "results": results,
    }

    report_path = REPORTS / f"eval_{version}_{timestamp}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n  Report saved: {report_path}")
    return report


def main():
    parser = argparse.ArgumentParser(description="Run voice bot evaluation suite")
    parser.add_argument("--type", choices=["query", "fact", "objection"], help="Test type to run")
    parser.add_argument("--limit", type=int, help="Max number of tests to run")
    parser.add_argument("--version", default="default", help="Bot version label")
    parser.add_argument("--bot-url", help="Bot API URL (or set BOT_API_URL env var)")
    parser.add_argument("--dry-run", action="store_true", help="Skip bot API calls, just test pipeline")
    args = parser.parse_args()

    run_eval(
        test_type=args.type,
        limit=args.limit,
        version=args.version,
        bot_api_url=args.bot_url,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
