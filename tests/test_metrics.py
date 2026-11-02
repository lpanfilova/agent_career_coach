from datetime import UTC, datetime
from unittest.mock import Mock

from test_coach import MemoryStore, intake

from career_coach.ai import DemoAI
from career_coach.evaluation import run_evaluation
from career_coach.metrics import summarize
from career_coach.models import Evaluation, Result, Session
from career_coach.service import Service


def session(identifier, scores, *, demo=False, prompt_suffix="", model="test-model"):
    plan = DemoAI().analyze({})
    plan.questions[0].prompt += prompt_suffix
    return Session(
        id=identifier,
        created_at=f"2026-11-0{identifier}T00:00:00+00:00",
        demo=demo,
        model=model,
        stage="complete" if len(scores) == 4 else "assessment",
        assessment=plan,
        report="Report" if len(scores) == 4 else None,
        results=[
            Result(
                question=plan.questions[i],
                answers=["my answer"],
                evaluation=Evaluation(
                    score=score, evidence="my answer", feedback="Feedback", gap="", follow_up=None
                ),
            )
            for i, score in enumerate(scores)
        ],
    )


def test_completion_denominator_excludes_demo_and_intake():
    intake_only = Session(
        id="intake", created_at=datetime.now(UTC).isoformat(), demo=False, model="test-model"
    )
    text = summarize(
        [
            session("1", [2, 2, 2, 2]),
            session("2", [1]),
            session("3", [3, 3, 3, 3], demo=True),
            intake_only,
        ]
    )
    assert "saved report: 1/2 (50%)" in text
    assert "submitted answers: 5/5 (100%)" in text
    assert "Scoring agreement: not measured" in text
    assert "not Telegram delivery" in text


def test_zero_samples_not_reported_as_success_and_bad_quotes_are_counted():
    assert "not measured (0 samples)" in summarize([])
    s = session("1", [2])
    s.results[0].evaluation.evidence = "fabricated quotation"
    assert "submitted answers: 0/1 (0%)" in summarize([s])


def test_progress_requires_identical_question_criteria_model_and_distinct_session():
    first, latest = session("1", [1]), session("2", [2])
    assert "1 → 2 (+1 rubric points" in summarize([latest, first])
    for changed in [session("2", [3], prompt_suffix=" harder"), session("2", [3], model="other")]:
        assert "no repeated identical questions" in summarize([first, changed])
    changed = session("2", [3])
    changed.results[0].question.criteria = ["Different criterion"]
    assert "no repeated identical questions" in summarize([first, changed])
    assert "no repeated identical questions" in summarize([first, first])
    assert "does not establish learning" in summarize([first, latest])


def test_benchmark_agreement_records_measured_cases_and_errors():
    ai = Mock()
    ai.evaluate.side_effect = [
        Evaluation(
            score=1, evidence="I do not know", feedback="weak", gap="practice", follow_up="Why?"
        ),
        Evaluation(score=1, evidence="loop", feedback="partial", gap="explain", follow_up="Why?"),
        Evaluation(score=3, evidence="seen elements", feedback="good", gap="", follow_up=None),
    ]
    run = run_evaluation(ai, "test-model")
    assert len(run["cases"]) == 3
    assert all(c["passed"] for c in run["cases"])
    assert "Scores within expected ranges: 3/3 (100%)" in summarize([], run)
    assert "not validated grading accuracy" in summarize([], run)
    ai.evaluate.side_effect = RuntimeError("private error body")
    failed = run_evaluation(ai, "test-model")
    assert all(c["error"] == "internal_error" for c in failed["cases"])
    assert "Scores within expected ranges: 0/3 (0%)" in summarize([], failed)
    assert "private error body" not in str(failed)


def test_retake_preserves_questions_but_clears_results_and_requires_completion():
    store = MemoryStore()
    service = Service(store, DemoAI(), demo=True)
    intake(service)
    assert "Complete the current assessment" in service.handle("/retake")
    for _ in range(4):
        service.handle("my answer")
        service.handle("my concrete example")
    previous = store.load()
    reply = service.handle("/retake")
    current = store.load()
    assert current.id != previous.id
    assert current.assessment == previous.assessment
    assert current.model == previous.model
    assert current.results == []
    assert current.stage == "assessment"
    assert current.profile == previous.profile
    assert "same questions" in reply
    assert "Practice effects" in reply
    store.metrics = Mock(return_value="Measured metrics")
    assert service.handle("/metrics") == "Measured metrics"
    store.metrics.assert_called_once()
