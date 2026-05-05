"""
Scoring rubric definitions for the evaluation framework.
Each dimension has a name, description, and 1-5 scale definitions.
"""

DIMENSIONS = {
    "factual_accuracy": {
        "name": "Factual Accuracy",
        "weight": 3.0,
        "description": "Are college fees, placements, cutoffs, and rankings correct?",
        "scale": {
            1: "Multiple factual errors or fabricated data",
            2: "One significant factual error (wrong fee, wrong placement)",
            3: "Mostly correct but vague or missing key details",
            4: "Accurate with minor imprecisions (e.g. rounding)",
            5: "Completely accurate, matches verified data",
        },
    },
    "relevance": {
        "name": "Relevance",
        "weight": 2.0,
        "description": "Did the bot answer the actual question asked?",
        "scale": {
            1: "Completely off-topic or generic response",
            2: "Partially related but misses the core question",
            3: "Addresses the question but includes unnecessary tangents",
            4: "Directly addresses the question with minor extras",
            5: "Precisely answers exactly what was asked",
        },
    },
    "completeness": {
        "name": "Completeness",
        "weight": 2.0,
        "description": "Did the response cover what the human counsellor covered?",
        "scale": {
            1: "Missing most key information the human covered",
            2: "Covers less than half of what human covered",
            3: "Covers the main point but misses supporting details",
            4: "Covers most of what human covered",
            5: "Covers everything the human covered, or adds useful extras",
        },
    },
    "tone_empathy": {
        "name": "Tone & Empathy",
        "weight": 1.5,
        "description": "Is the tone appropriate for an anxious student/parent?",
        "scale": {
            1: "Robotic, cold, or dismissive",
            2: "Functional but lacks warmth",
            3: "Neutral and professional",
            4: "Warm and reassuring",
            5: "Empathetic, builds trust, acknowledges anxiety",
        },
    },
    "actionability": {
        "name": "Actionability",
        "weight": 1.5,
        "description": "Did it give a clear next step?",
        "scale": {
            1: "No next step mentioned",
            2: "Vague suggestion ('explore options')",
            3: "Mentions a next step but unclear how",
            4: "Clear next step (apply, check website, call back)",
            5: "Specific actionable step with details (link, deadline, process)",
        },
    },
    "hallucination": {
        "name": "Hallucination Check",
        "weight": 3.0,
        "description": "Did the bot invent colleges, fees, or placements that don't exist?",
        "scale": {
            1: "Major hallucination — invented college, program, or data",
            2: "Minor hallucination — inflated/deflated real numbers significantly",
            3: "Slight embellishment but core facts are real",
            4: "No hallucination detected, sticks to known data",
            5: "Explicitly qualifies uncertain info ('I'd need to verify this')",
        },
    },
}

# Specialized rubric for objection handling (adds to base dimensions)
OBJECTION_DIMENSIONS = {
    "objection_acknowledgment": {
        "name": "Objection Acknowledgment",
        "weight": 2.0,
        "description": "Did the bot acknowledge the student's concern before responding?",
        "scale": {
            1: "Ignored the objection entirely",
            2: "Glossed over it, jumped to a pitch",
            3: "Brief acknowledgment then moved on",
            4: "Acknowledged with empathy, then addressed it",
            5: "Validated the concern, reframed it constructively",
        },
    },
    "conversation_continuation": {
        "name": "Conversation Continuation",
        "weight": 2.0,
        "description": "Did the response keep the conversation going or kill it?",
        "scale": {
            1: "Response would likely end the conversation",
            2: "Student would need to drive the conversation forward",
            3: "Neutral — doesn't actively continue or end",
            4: "Includes a question or suggestion that continues naturally",
            5: "Smoothly transitions to next topic while addressing the concern",
        },
    },
}


def get_dimensions(test_type: str) -> dict:
    """Get scoring dimensions for a test type."""
    dims = dict(DIMENSIONS)
    if test_type == "objection_handling":
        dims.update(OBJECTION_DIMENSIONS)
    return dims


def compute_weighted_score(scores: dict, test_type: str) -> float:
    """Compute weighted average score from dimension scores."""
    dims = get_dimensions(test_type)
    total_weight = 0
    weighted_sum = 0
    for dim_key, score in scores.items():
        if dim_key in dims:
            w = dims[dim_key]["weight"]
            weighted_sum += score * w
            total_weight += w
    return round(weighted_sum / max(total_weight, 1), 2)
