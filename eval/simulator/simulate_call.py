"""
Simulate end-to-end multi-turn conversations between a student persona (LLM)
and the voice bot, then score the full conversation.

Usage:
  $env:OPENAI_API_KEY = "sk-..."
  $env:BOT_API_URL = "https://your-bot/chat"
  python eval/simulator/simulate_call.py
  python eval/simulator/simulate_call.py --persona persona_03 --turns 12
"""

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from runner.judge import judge_response

ROOT = Path(__file__).resolve().parent
REPORTS = Path(__file__).resolve().parent.parent / "reports"


def load_personas():
    path = ROOT / "personas.json"
    if not path.exists():
        print("Run generate_personas.py first")
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def call_bot_api(message: str, conversation_history: list, api_url: str) -> str:
    """Send a message to the bot API with conversation history."""
    import urllib.request

    payload = json.dumps({
        "message": message,
        "conversation_history": conversation_history,
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
            return data.get("response", data.get("text", data.get("message", str(data))))
    except Exception as e:
        return f"[BOT_API_ERROR: {e}]"


def generate_student_reply(persona: dict, conversation: list, api_key: str) -> str:
    """Use an LLM to generate the student's next message based on persona."""
    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    conv_text = "\n".join(f"{'Student' if m['role']=='user' else 'Bot'}: {m['content']}" for m in conversation)

    prompt = f"""You are roleplaying as a student/parent calling Shiksha.com for college counselling.

YOUR PERSONA:
Name: {persona['name']}
Description: {persona['description']}
Personality: {persona['personality']}
Course: {persona['profile']['course_interest']}
Exam Scores: {persona['profile']['exam_scores']}
Location: {persona['profile']['location_preference']}
Budget: {persona['profile']['budget']}
Objectives: {', '.join(persona['objectives'])}

CONVERSATION SO FAR:
{conv_text}

INSTRUCTIONS:
- Respond naturally as this persona would. Use Hindi/Hinglish like a real Indian student/parent.
- Stay in character. If you're anxious, show it. If you're price-sensitive, push on fees.
- If the bot gave good info, ask a follow-up or raise one of your objectives you haven't covered yet.
- If you've covered all objectives, start wrapping up naturally.
- Keep responses 1-3 sentences (this is a phone call, not an essay).
- If this persona has objections ({', '.join(persona.get('likely_objections', []))}), raise one if appropriate.

Respond with ONLY the student's next message, nothing else."""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=200,
    )
    return resp.choices[0].message.content.strip()


def score_conversation(persona: dict, conversation: list, api_key: str) -> dict:
    """Score an entire simulated conversation."""
    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    conv_text = "\n".join(f"{'Student' if m['role']=='user' else 'Bot'}: {m['content']}" for m in conversation)

    prompt = f"""You are evaluating a voice bot's performance in a complete counselling conversation with a student.

STUDENT PERSONA:
{json.dumps(persona, indent=2, ensure_ascii=False)}

FULL CONVERSATION:
{conv_text}

Score the bot on these dimensions (1-5 each):

1. **call_flow** — Did the bot follow a logical flow? (greeting → qualification → discovery → recommendations → close)
2. **qualification_completeness** — Did it gather: course, exam scores, category, location, budget?
3. **recommendation_quality** — Were college recommendations relevant to the student's profile?
4. **objection_handling** — If student raised concerns, were they addressed well?
5. **conversion_signal** — Did the call end with a clear next step? (application, WhatsApp, callback)
6. **naturalness** — Did the conversation feel natural, not robotic?
7. **factual_accuracy** — Were facts (fees, placements) accurate or at least plausible?

Return JSON:
{{
  "scores": {{
    "call_flow": <1-5>,
    "qualification_completeness": <1-5>,
    "recommendation_quality": <1-5>,
    "objection_handling": <1-5>,
    "conversion_signal": <1-5>,
    "naturalness": <1-5>,
    "factual_accuracy": <1-5>
  }},
  "overall_score": <1-5 weighted average>,
  "strengths": ["...", "..."],
  "weaknesses": ["...", "..."],
  "summary": "1-2 sentence assessment"
}}"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=1000,
    )
    return json.loads(resp.choices[0].message.content)


def simulate_call(persona: dict, max_turns: int = 10, bot_url: str = "", api_key: str = ""):
    """Simulate a full conversation between a persona and the bot."""
    conversation = []

    # Student opens
    opening = persona["opening_message"]
    conversation.append({"role": "user", "content": opening})
    print(f"  Student: {opening[:80]}...")

    for turn in range(max_turns):
        # Bot responds
        bot_resp = call_bot_api(
            conversation[-1]["content"],
            conversation,
            bot_url,
        )
        if bot_resp.startswith("[BOT_API_ERROR"):
            print(f"  Bot: {bot_resp}")
            break

        conversation.append({"role": "assistant", "content": bot_resp})
        print(f"  Bot: {bot_resp[:80]}...")

        # Check if conversation should end
        if turn >= max_turns - 1:
            break

        # Student responds
        student_msg = generate_student_reply(persona, conversation, api_key)
        conversation.append({"role": "user", "content": student_msg})
        print(f"  Student: {student_msg[:80]}...")

        time.sleep(0.5)

    return conversation


def main():
    parser = argparse.ArgumentParser(description="Simulate counselling conversations")
    parser.add_argument("--persona", help="Specific persona ID to simulate")
    parser.add_argument("--turns", type=int, default=8, help="Max conversation turns")
    parser.add_argument("--bot-url", help="Bot API URL")
    parser.add_argument("--all", action="store_true", help="Run all personas")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY", "")
    bot_url = args.bot_url or os.environ.get("BOT_API_URL", "")

    if not bot_url:
        print("ERROR: Set BOT_API_URL env var or pass --bot-url")
        return

    personas = load_personas()
    if args.persona:
        personas = [p for p in personas if p["id"] == args.persona]
    elif not args.all:
        personas = personas[:3]  # Default: first 3

    results = []
    for persona in personas:
        print(f"\n{'='*50}")
        print(f"SIMULATING: {persona['name']} — {persona['description'][:50]}")
        print(f"{'='*50}")

        conversation = simulate_call(persona, args.turns, bot_url, api_key)

        print(f"\n  Scoring conversation...")
        score = score_conversation(persona, conversation, api_key)
        print(f"  Overall: {score.get('overall_score', 'N/A')}/5")
        print(f"  Strengths: {', '.join(score.get('strengths', []))}")
        print(f"  Weaknesses: {', '.join(score.get('weaknesses', []))}")

        results.append({
            "persona": persona,
            "conversation": conversation,
            "score": score,
        })

    # Save
    REPORTS.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORTS / f"sim_{timestamp}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved: {path}")


if __name__ == "__main__":
    main()
