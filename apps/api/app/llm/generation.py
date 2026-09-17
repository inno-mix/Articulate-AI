"""Generation settings (binding) — ai-layer.md §4.3."""

TEMPERATURE: dict[str, float] = {
    "roleplay": 0.7,
    "hint": 0.7,
    "custom_scenario": 0.7,
    "drill_generate": 0.8,
    "rewrite": 0.3,
    "feedback": 0.0,
    "memory": 0.0,
    "drill_feedback": 0.0,
}
