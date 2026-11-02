from contextlib import contextmanager
from copy import deepcopy
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from career_coach.ai import CoachAI, DemoAI
from career_coach.models import Evaluation
from career_coach.service import Service
from career_coach.telegram import authorized, chunks


class MemoryStore:
    def __init__(self):
        self.state = None
        self.events = {}

    @contextmanager
    def turn(self):
        snapshot, events = deepcopy(self.state), deepcopy(self.events)
        try:
            yield self
        except Exception:
            self.state, self.events = snapshot, events
            raise

    def load(self):
        return deepcopy(self.state)

    def save(self, session):
        self.state = deepcopy(session)

    def cached(self, event_id):
        return self.events.get(event_id)

    def remember(self, event_id, reply):
        self.events[event_id] = reply

    def history(self):
        return "history"


def intake(service):
    service.handle("/start")
    service.handle("Software Engineering Intern")
    service.handle("MS SWE student; Python is self-reported")
    service.handle(str(date.today() + timedelta(days=7)))
    return service.handle("Build scalable cloud services and own code lifecycle")


def test_complete_and_resume_each_followup():
    store = MemoryStore()
    service = Service(store, DemoAI(), demo=True)
    intake(service)
    for i in range(4):
        reply = service.handle("I would use a concrete example")
        assert "What concrete example" in reply
        assert len(store.state.results) == i
        service = Service(store, DemoAI(), demo=True)
        assert (
            service.handle("/resume")
            == "DEMO MODE: scripted questions and scores; no real assessment.\nWhat concrete example supports your reasoning?"
        )
        reply = service.handle("Here is my example and reasoning")
        assert len(store.state.results) == i + 1
    assert store.state.stage == "complete"
    assert "Career Readiness Report" in reply
    assert "not an overall career readiness judgment" in reply
    assert "Self-reported background (unverified)" in reply
    assert "DEMO" in reply
    assert service.handle("/report") == store.state.report
    old_id = store.state.id
    service.handle("/new")
    assert store.state.id != old_id
    assert store.state.stage == "role"


def test_invalid_deadline_and_duplicate_delivery():
    store = MemoryStore()
    service = Service(store, DemoAI(), demo=True)
    service.handle("/start")
    service.handle("Engineer", "telegram:1")
    assert (
        service.handle("Engineer", "telegram:1")
        == "What is your experience and which skills do you self-report?"
    )
    assert store.state.stage == "background"
    service.handle("Student")
    for bad in ["ASAP", "2020-01-01", "2026-99-99"]:
        assert "YYYY-MM-DD" in service.handle(bad)
        assert store.state.stage == "deadline"


def test_failed_ai_turn_rolls_back():
    store = MemoryStore()
    ai = DemoAI()
    service = Service(store, ai, demo=True)
    intake(service)
    before = store.state.model_dump()
    ai.evaluate = Mock(side_effect=ValueError("failed model"))
    with pytest.raises(ValueError):
        service.handle("My answer", "telegram:99")
    assert store.state.model_dump() == before
    assert "telegram:99" not in store.events


@pytest.mark.parametrize("score", [-1, 4])
def test_rubric_bounds(score):
    with pytest.raises(ValueError):
        Evaluation(score=score, evidence="x", feedback="x", gap="", follow_up=None)


def test_ai_requires_verbatim_evidence():
    ai = object.__new__(CoachAI)
    ai.parse = Mock(
        return_value=Evaluation(score=3, evidence="invented", feedback="x", gap="", follow_up=None)
    )
    with pytest.raises(ValueError, match="evidence"):
        ai.evaluate(DemoAI().analyze({}).questions[0], ["I do not know"], None)


def test_responses_structured_output_contract():
    ai = object.__new__(CoachAI)
    ai.model = "configured-model"
    ai.client = Mock()
    assessment = DemoAI().analyze({})
    ai.client.responses.parse.return_value = SimpleNamespace(output_parsed=assessment)
    assert ai.analyze({"description": "untrusted text"}) == assessment
    kwargs = ai.client.responses.parse.call_args.kwargs
    assert kwargs["store"] is False
    assert kwargs["model"] == "configured-model"
    ai.client.responses.parse.return_value = SimpleNamespace(output_parsed=None)
    with pytest.raises(ValueError, match="refused"):
        ai.analyze({})


def test_private_owner_only_and_utf16_chunks():
    message = {"chat": {"type": "private", "id": 42}, "from": {"id": 42}}
    assert authorized(message, 42)
    assert not authorized(message, 7)
    message["chat"]["type"] = "group"
    assert not authorized(message, 42)
    text = "😀" * 4000 + "hello"
    parts = list(chunks(text))
    assert "".join(parts) == text
    assert all(len(p.encode("utf-16-le")) // 2 <= 3500 for p in parts)


def test_discovery_does_not_claim_live_matches():
    service = Service(MemoryStore(), DemoAI(), demo=True)
    reply = service.handle("/opportunities")
    assert "NOT verified open opportunities" in reply
    for kind in ["jobs:", "internships:", "research:", "entrepreneurial:"]:
        assert kind in reply


def test_match_separates_reported_and_demonstrated():
    service = Service(MemoryStore(), DemoAI(), demo=True)
    intake(service)
    reply = service.handle("/match Python and SQL required")
    assert "Self-reported overlap (unverified): python" in reply
    assert "Demonstrated overlap (score 2+ in this short sample): none identified" in reply
    assert "Topics without demonstrated evidence: python, sql" in reply


def test_telegram_transport_ignores_other_users(monkeypatch):
    import asyncio

    import httpx

    import career_coach.telegram as telegram

    calls = []
    polls = 0

    def handler(request):
        nonlocal polls
        import json

        payload = json.loads(request.content)
        method = request.url.path.rsplit("/", 1)[1]
        calls.append((method, payload))
        if method == "getUpdates":
            polls += 1
            if polls > 1:
                raise asyncio.CancelledError()
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": [
                        {
                            "update_id": 1,
                            "message": {
                                "chat": {"type": "private", "id": 8},
                                "from": {"id": 8},
                                "text": "/start",
                            },
                        },
                        {
                            "update_id": 2,
                            "message": {
                                "chat": {"type": "private", "id": 42},
                                "from": {"id": 42},
                                "text": "/start",
                            },
                        },
                    ],
                },
            )
        return httpx.Response(200, json={"ok": True, "result": {}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(telegram.httpx, "AsyncClient", lambda **kwargs: client)
    service = Service(MemoryStore(), DemoAI(), demo=True)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(telegram.run_bot(service, "fake-token", 42))
    sends = [payload for method, payload in calls if method == "sendMessage"]
    assert len(sends) == 1
    assert sends[0]["chat_id"] == 42
    assert "target role" in sends[0]["text"]
    assert calls[-1][1]["offset"] == 3
