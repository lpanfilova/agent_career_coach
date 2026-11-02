from unittest.mock import Mock

import pytest
from pydantic import ValidationError
from test_coach import MemoryStore, intake

from career_coach.ai import CoachAI, DemoAI
from career_coach.errors import ModelOutputError
from career_coach.graph import current_prompt
from career_coach.models import Assessment, GeneratedAssessment, Session
from career_coach.service import Service

CODE = "def factorial(n):\n    result = 1\n    for i in range(1, n):\n        result *= i\n    return result"


def assessment(mode="review", code=CODE):
    plan = DemoAI().analyze({})
    plan.questions[
        2
    ].prompt = "Review this factorial function without running it. Explain your reasoning."
    plan.questions[2].coding_mode = mode
    plan.questions[2].code_to_review = code
    return plan


@pytest.mark.parametrize("code", [None, "", "  \n"])
def test_generated_review_requires_code(code):
    with pytest.raises(ValidationError, match="complete code_to_review"):
        GeneratedAssessment.model_validate(assessment(code=code).model_dump())


def test_generation_retries_missing_code_once():
    ai = object.__new__(CoachAI)
    ai.parse = Mock(side_effect=[assessment(code=None), assessment()])
    plan = ai.analyze({})
    assert ai.parse.call_count == 2
    assert plan.questions[2].code_to_review == CODE
    assert "include complete code" in ai.parse.call_args.args[1]


def test_invalid_generation_does_not_save_missing_material():
    ai = object.__new__(CoachAI)
    ai.parse = Mock(return_value=assessment(code=None))
    with pytest.raises(ModelOutputError, match="ai_invalid_output"):
        ai.analyze({})
    assert ai.parse.call_count == 2


def test_write_mode_and_legacy_snapshots_still_supported():
    GeneratedAssessment.model_validate(DemoAI().analyze({}).model_dump())
    old = assessment(mode=None, code=None).model_dump()
    for q in old["questions"]:
        q.pop("coding_mode")
        q.pop("code_to_review")
    assert Assessment.model_validate(old).questions[2].code_to_review is None


def test_review_code_survives_followup_and_resume_and_reaches_evaluator():
    store = MemoryStore()
    ai = DemoAI()
    ai.analyze = Mock(return_value=assessment())
    service = Service(store, ai, demo=True)
    intake(service)
    # Finish the first two tasks without introducing any executed-code path.
    for _ in range(2):
        service.handle("initial answer")
        reply = service.handle("concrete example")
    assert CODE in reply
    ai.evaluate = Mock(wraps=ai.evaluate)
    reply = service.handle("My static review reasoning")
    assert CODE in reply
    assert ai.evaluate.call_args.args[0].code_to_review == CODE
    restored = Session.model_validate_json(store.state.model_dump_json())
    assert CODE in current_prompt(restored)
    restarted = Service(store, ai, demo=True)
    assert CODE in restarted.handle("/resume")
