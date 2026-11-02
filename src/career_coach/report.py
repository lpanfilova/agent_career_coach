from datetime import date, timedelta

from .models import RUBRIC

RESOURCES = {
    "python": ("Python tutorial", "https://docs.python.org/3/tutorial/"),
    "sql": ("PostgreSQL tutorial", "https://www.postgresql.org/docs/current/tutorial.html"),
    "experimentation": (
        "Google ML crash course",
        "https://developers.google.com/machine-learning/crash-course",
    ),
    "communication": ("MIT communication resources", "https://mitcommlab.mit.edu/"),
}


def render_report(s, today=None):
    today = today or date.today()
    deadline = date.fromisoformat(s.profile["deadline"])
    days = max(0, (deadline - today).days)
    lines = [
        "# Career Readiness Report",
        f"Target: {s.profile['role']}",
        f"Preparation deadline: {deadline} ({days} days from {today})",
        f"Session: {s.id} | Model: {s.model} | Rubric: v1",
        "DEMO — all scores and feedback are scripted."
        if s.demo
        else "Evidence from a short, AI-reviewed assessment; code was NOT executed.",
        "This is a limited sample, not an overall career readiness judgment or hiring prediction.",
        "\n## Self-reported background (unverified)",
        s.profile["background"],
        "\n## Opportunity requirements",
        *[f"- {r}" for r in s.assessment.requirements],
        "\n## Demonstrated strengths",
    ]
    strengths = [r for r in s.results if r.evaluation.score >= 2]
    lines += [
        f"- {r.question.skill}: {r.evaluation.feedback} Evidence: {r.evaluation.evidence!r}"
        for r in strengths
    ] or ["- No strength established at score 2+ in this sample."]
    lines += ["\n## Evidence, feedback and knowledge gaps", f"Rubric: {RUBRIC}"]
    for n, r in enumerate(s.results, 1):
        e = r.evaluation
        lines += [
            f"{n}. {r.question.skill} ({r.question.kind}): {e.score}/3",
            f"   Evidence: {e.evidence!r}",
            f"   Feedback: {e.feedback}",
            f"   Gap: {e.gap or 'No specific gap observed; broader coverage remains untested.'}",
        ]
    lines += [
        "\n## Actionable preparation plan",
        "Prioritize weaker evidence first; adjust the effort to your availability.",
    ]
    for n, r in enumerate(sorted(s.results, key=lambda r: r.evaluation.score), 1):
        due = today + timedelta(days=round(days * n / max(1, len(s.results))))
        resource = RESOURCES.get(r.question.skill.lower())
        lines += [
            f"- By {due}: spend 30–45 minutes on {r.question.skill}. "
            f"{r.evaluation.gap or 'Practice a harder variation.'} "
            f"Deliverable: a worked example addressing {', '.join(r.question.criteria)}. "
            "Then retake a comparable question and explain your reasoning without notes."
        ]
        if resource:
            lines += [f"  Resource: {resource[0]} — {resource[1]}"]
        else:
            lines += [
                "  Resource: use the opportunity provider's official documentation or training material; no specific resource verified for this skill."
            ]
    lines += [
        "\n## Limits and next steps",
        "Requirements not directly covered by the four questions remain unassessed. "
        "Scores are ordinal snapshots; comparisons require similar skill, question criteria, difficulty and model. "
        "Use /history to inspect evidence over time, then /new for another assessment.",
    ]
    return "\n".join(lines)
