"""Small descriptive metrics, never a readiness score or validated accuracy estimate."""

from collections import defaultdict


def fraction(passed, total):
    return f"{passed}/{total} ({passed / total:.0%})" if total else "not measured (0 samples)"


def summarize(sessions, benchmark=None):
    # Intake-only and scripted/demo sessions are not assessment attempts.
    attempts = [s for s in sessions if not s.demo and s.assessment is not None]
    completed = sum(s.stage == "complete" and bool(s.report) for s in attempts)
    results = [r for s in attempts for r in s.results]
    grounded = sum(
        bool(r.evaluation.evidence.strip())
        and any(r.evaluation.evidence in answer for answer in r.answers)
        for r in results
    )
    lines = [
        "Prototype evaluation metrics (live assessments only)",
        "Effectiveness",
        f"Assessments completed with a saved report: {fraction(completed, len(attempts))}",
        "Denominator: sessions with generated questions, including unfinished attempts.",
        "This measures saved report generation, not Telegram delivery or user satisfaction.",
        "Accuracy checks",
        f"Evidence quotes present in submitted answers: {fraction(grounded, len(results))}",
        "Quote validity checks source attribution, not whether the grading is correct.",
    ]
    if benchmark:
        cases = benchmark["cases"]
        lines += [
            f"Latest scoring check: {benchmark['created_at']} | {benchmark['model']} | {benchmark['suite']}",
            f"Scores within expected ranges: {fraction(sum(c['score_in_range'] for c in cases), len(cases))}",
            f"All case checks passed: {fraction(sum(c['passed'] for c in cases), len(cases))}",
            f"API/evaluation errors: {sum(c['error'] is not None for c in cases)}/{len(cases)}",
            "Three predefined examples are a regression check, not validated grading accuracy.",
        ]
    else:
        lines += ["Scoring agreement: not measured. Run: uv run python scripts/evaluate.py"]
    lines += ["User progress"]
    comparable = defaultdict(dict)
    for s in sorted(attempts, key=lambda s: (s.created_at, s.id)):
        for r in s.results:
            q = r.question
            key = (
                s.model,
                q.skill.strip().lower(),
                q.kind,
                q.prompt,
                tuple(q.criteria),
                q.coding_mode,
                q.code_to_review,
            )
            # A session contributes at most one observation to each repeated question.
            comparable[key][s.id] = (s.created_at[:10], r.evaluation.score)
    changes = []
    for key, observations in comparable.items():
        if len(observations) < 2:
            continue
        previous, latest = list(observations.values())[-2:]
        changes.append(
            f"- {key[1]} / {key[2]}: {previous[1]} → {latest[1]} "
            f"({latest[1] - previous[1]:+d} rubric points; {previous[0]} → {latest[0]})"
        )
    lines += changes or [
        "Not measured: no repeated identical questions yet. Complete an assessment, then use /retake."
    ]
    lines += [
        "Comparisons require the same question, code, criteria and model (rubric v1). "
        "Scores are ordinal; familiarity, different follow-ups and AI variation can change them. "
        "A score increase alone does not establish learning or overall career readiness."
    ]
    return "\n".join(lines)
