from unittest.mock import Mock

import httpx
import openai
import psycopg
import pytest

from career_coach.ai import CoachAI, DemoAI, answer_excerpts
from career_coach.errors import ModelOutputError, explain_failure
from career_coach.models import ModelEvaluation


def evaluation(evidence_id):
    return ModelEvaluation(
        score=1, evidence_id=evidence_id, feedback="Partial", gap="Explain why", follow_up=None
    )


def test_evidence_is_copied_from_answer_without_a_quote_retry():
    ai = object.__new__(CoachAI)
    ai.parse = Mock(return_value=evaluation(1))
    answers = ["First line.\nI use a dictionary for lookup."]
    result = ai.evaluate(DemoAI().analyze({}).questions[0], answers, None)
    assert result.evidence == "I use a dictionary for lookup."
    assert result.evidence in answers[0]
    assert ai.parse.call_count == 1
    assert (
        ai.parse.call_args.args[0].model_json_schema()["properties"]["evidence_id"]["maximum"] == 1
    )


def test_invalid_excerpt_id_cannot_fabricate_evidence():
    ai = object.__new__(CoachAI)
    ai.parse = Mock(return_value=evaluation(50))
    with pytest.raises(ModelOutputError, match="ai_invalid_output"):
        ai.evaluate(DemoAI().analyze({}).questions[0], ["One line"], None)


def test_excerpts_preserve_code_whitespace_unicode_and_followup_source():
    answers = ['```python\n    return ‘café’ + "😀"\n```', "  My follow-up\n" + "x" * 900]
    excerpts = answer_excerpts(answers)
    for excerpt in excerpts:
        assert excerpt["text"] in answers[excerpt["answer_index"]]
        assert len(excerpt["text"]) <= 400
    assert [item["id"] for item in excerpts] == list(range(len(excerpts)))
    ai = object.__new__(CoachAI)
    ai.parse = Mock(return_value=evaluation(3))
    result = ai.evaluate(DemoAI().analyze({}).questions[0], answers, "Explain further")
    assert result.evidence == "  My follow-up\n"
    assert ai.parse.call_args.args[2]["previous_follow_up"] == "Explain further"


def test_empty_excerpts_do_not_trigger_an_api_call():
    ai = object.__new__(CoachAI)
    ai.parse = Mock()
    with pytest.raises(ValueError):
        ai.evaluate(DemoAI().analyze({}).questions[0], [" \n\t"], None)
    ai.parse.assert_not_called()


@pytest.mark.parametrize(
    "exception_class,status,body,code",
    [
        (openai.AuthenticationError, 401, {}, "openai_authentication"),
        (openai.PermissionDeniedError, 403, {}, "openai_permission"),
        (openai.RateLimitError, 429, {"code": "insufficient_quota"}, "openai_quota"),
        (openai.RateLimitError, 429, {}, "openai_rate_limit"),
        (openai.BadRequestError, 400, {}, "openai_request"),
    ],
)
def test_api_errors_have_safe_actionable_messages(exception_class, status, body, code):
    secret = "secret-token-and-private-answer"
    response = httpx.Response(
        status, request=httpx.Request("POST", "https://example.test/" + secret)
    )
    exc = exception_class(secret, response=response, body=body)
    failure = explain_failure(exc)
    assert failure.code == code
    assert secret not in failure.turn_reply()
    assert "previous progress is saved" in failure.turn_reply()


@pytest.mark.parametrize(
    "exc,code",
    [
        (
            openai.APITimeoutError(request=httpx.Request("POST", "https://example.test/secret")),
            "openai_timeout",
        ),
        (
            openai.APIConnectionError(request=httpx.Request("POST", "https://example.test/secret")),
            "openai_connection",
        ),
        (psycopg.OperationalError("secret database credentials"), "database_unavailable"),
        (psycopg.IntegrityError("private answer"), "database_error"),
        (RuntimeError("secret exception body"), "internal_error"),
        (ModelOutputError("unknown private data"), "ai_invalid_output"),
    ],
)
def test_other_failures_do_not_expose_exception_details(exc, code):
    failure = explain_failure(exc)
    assert failure.code == code
    assert "secret" not in failure.turn_reply()
    assert "private" not in failure.turn_reply()
