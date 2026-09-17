"""One valid example payload per structured output model (ai-layer.md §2), keyed by class name."""

from typing import Any

FAKE_OUTPUTS: dict[str, dict[str, Any]] = {
    "FeedbackAnalysis": {
        "summary": "Clear structure overall; a couple of filler phrases blunted the message.",
        "objective_met": True,
        "scores": [
            {"dimension": "clarity", "score": 4, "reason": "Stated the ask early."},
            {"dimension": "conciseness", "score": 3, "reason": "Some repeated points."},
            {"dimension": "structure", "score": 4, "reason": "Followed a logical order."},
            {
                "dimension": "audience_fit",
                "score": 3,
                "reason": "A little technical for the listener.",
            },
            {"dimension": "tone", "score": 5, "reason": "Professional and warm."},
            {"dimension": "confidence", "score": 3, "reason": "Some hedging language."},
            {"dimension": "grammar_vocabulary", "score": 4, "reason": "Accurate, minor slips."},
        ],
        "strengths": ["Clear opening.", "Stayed on topic."],
        "improvements": ["Cut repeated points.", "State the ask earlier."],
        "highlights": [
            {
                "quote": "so basically",
                "issue": "Filler phrase that weakens the point.",
                "better_version": "Drop it and start with the point directly.",
            }
        ],
        "grammar_fixes": [
            {
                "original": "I am agree",
                "corrected": "I agree",
                "explanation": "'agree' is a verb here, not an adjective.",
            }
        ],
    },
    "MemoryUpdate": {
        "actions": [
            {
                "action": "add",
                "dimension": "clarity",
                "note": "Tends to bury the main point.",
                "evidence": "Took three sentences to state the ask.",
            }
        ]
    },
    "RewriteResult": {
        "output_text": "The deploy is blocked by a failing migration. I'll have a fix by 3pm.",
        "changes": [{"what": "Shortened the opening.", "why": "Leads with the point."}],
        "tone_note": "Kept it direct and professional.",
    },
    "ScenarioDraftOut": {
        "title": "Ask for a deadline extension",
        "category": "negotiation",
        "difficulty": 2,
        "summary": "Your manager wants a feature shipped Friday, but you need one more week.",
        "persona": {
            "name": "Alex",
            "role": "Engineering manager",
            "personality": "Supportive but results-focused.",
            "goals": "Ship reliably without slipping the roadmap.",
        },
        "user_objective": "Negotiate a one-week extension without losing trust.",
        "opening_line": "How's the feature coming along for Friday?",
        "success_criteria": ["States the risk clearly.", "Proposes a new date."],
        "recommended_mode": "voice",
    },
    "DrillBatch": {
        "drills": [
            {
                "kind": "rephrase",
                "title": "Say it more directly",
                "prompt": "Rewrite: 'I was sort of thinking maybe we could look at this.'",
                "target_dimension": "confidence",
            }
        ]
    },
    "DrillFeedback": {
        "score": 4,
        "feedback": "Much more direct — nice work.",
        "better_version": None,
    },
}
