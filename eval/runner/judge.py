"""
LLM-as-Judge scoring engine.
Sends (question, bot_response, reference_response) to GPT-4o and returns
structured scores on the evaluation rubric.
"""

import json
import os
from openai import OpenAI
from .rubric import get_dimensions, compute_weighted_score


def _build_judge_prompt(test_case: dict, bot_response: str) -> str:
    """Build the judge prompt for a specific test case."""
    test_type = test_case["type"]
    dims = get_dimensions(test_type)

    dim_descriptions = "\n".join(
        f'- **{d["name"]}** ({key}): {d["description"]}\n  Scale: 1={d["scale"][1]}, 3={d["scale"][3]}, 5={d["scale"][5]}'
        for key, d in dims.items()
    )

    if test_type == "student_query":
        context_block = f"""
STUDENT PROFILE:
- Course: {test_case['student_profile']['course_interest']}
- Exam Scores: {test_case['student_profile']['exam_scores']}
- Category: {test_case['student_profile']['category']}
- Location: {test_case['student_profile']['location_preference']}
- Budget: {test_case['student_profile']['budget']}

CONVERSATION CONTEXT:
{test_case.get('conversation_context', 'N/A')}

STUDENT QUERY (Hindi): {test_case['query_hindi']}
STUDENT QUERY (English): {test_case['query_english']}

HUMAN COUNSELLOR'S RESPONSE (reference):
{test_case['reference_response']}

BOT'S RESPONSE (to evaluate):
{bot_response}"""

    elif test_type == "factual_accuracy":
        context_block = f"""
QUESTION: {test_case['question']}
COLLEGE: {test_case['college_name']} ({test_case.get('college_location', '')})
COURSE: {test_case.get('course', '')}

EXPECTED ANSWER (from verified data):
{test_case['expected_answer']}

BOT'S RESPONSE (to evaluate):
{bot_response}"""

    elif test_type == "objection_handling":
        context_block = f"""
STUDENT PROFILE:
- Course: {test_case['student_profile']['course_interest']}
- Exam Scores: {test_case['student_profile']['exam_scores']}
- Location: {test_case['student_profile']['location_preference']}
- Budget: {test_case['student_profile']['budget']}

CONVERSATION CONTEXT:
{test_case.get('conversation_context', 'N/A')}

OBJECTION TYPE: {test_case['objection_type']}
STUDENT'S OBJECTION (Hindi): {test_case['student_quote_hindi']}
OBJECTION DESCRIPTION: {test_case['objection_description']}

HUMAN COUNSELLOR'S RESPONSE (reference):
{test_case['reference_counsellor_response']}
Strategy used: {test_case.get('handling_strategy', '')}
Resolved by human: {test_case.get('was_resolved_by_human', 'unknown')}

BOT'S RESPONSE (to evaluate):
{bot_response}"""

    else:
        context_block = f"Unknown test type: {test_type}"

    dim_keys = list(dims.keys())

    return f"""You are an expert evaluator assessing a voice bot's response quality for Shiksha.com, an Indian education counselling platform that helps Class 12 students choose colleges.

EVALUATION DIMENSIONS:
{dim_descriptions}

{context_block}

INSTRUCTIONS:
1. Score the bot's response on each dimension (1-5 scale).
2. For factual_accuracy and hallucination, compare against the reference/expected data. If bot invents specific numbers not in reference, score low.
3. For tone_empathy, remember the caller is typically an anxious 17-18 year old or their worried parent.
4. Provide a brief justification for each score.

Return a JSON object with this exact structure:
{{
  "scores": {{
    {', '.join(f'"{k}": <1-5>' for k in dim_keys)}
  }},
  "justifications": {{
    {', '.join(f'"{k}": "<brief reason>"' for k in dim_keys)}
  }},
  "overall_notes": "<1-2 sentence overall assessment>"
}}

Return ONLY the JSON object, no other text."""


def judge_response(
    test_case: dict,
    bot_response: str,
    api_key: str | None = None,
    model: str = "gpt-4o-mini",
) -> dict:
    """Score a bot response using LLM-as-judge.

    Returns:
        {
            "scores": {"factual_accuracy": 4, ...},
            "justifications": {"factual_accuracy": "...", ...},
            "weighted_score": 3.85,
            "overall_notes": "..."
        }
    """
    key = api_key or os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise ValueError("OPENAI_API_KEY required for judge scoring")

    client = OpenAI(api_key=key)
    prompt = _build_judge_prompt(test_case, bot_response)

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=1500,
    )

    result = json.loads(response.choices[0].message.content)

    # Compute weighted score
    scores = result.get("scores", {})
    result["weighted_score"] = compute_weighted_score(scores, test_case["type"])

    return result
