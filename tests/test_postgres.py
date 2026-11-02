"""Opt-in integration check, isolated in a temporary schema."""

import os
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo
from test_coach import intake

from career_coach.ai import DemoAI
from career_coach.service import Service
from career_coach.store import Store


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="Set TEST_DATABASE_URL to run PostgreSQL integration"
)
def test_postgres_restart_idempotency_and_rollback(tmp_path):
    url = os.environ["TEST_DATABASE_URL"]
    schema = "test_" + uuid4().hex
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    try:
        store = Store(make_conninfo(url, options=f"-c search_path={schema}"))
        store.initialize()
        service = Service(store, DemoAI(), demo=True)
        intake(service)
        reply = service.handle("A dictionary maps keys to values", "telegram:test")
        restarted = Service(Store(store.url), DemoAI(), demo=True)
        assert restarted.handle("A dictionary maps keys to values", "telegram:test") == reply
        assert "concrete example" in restarted.handle("/resume")
        restarted.handle("Look up customer records by customer ID")
        for _ in range(3):
            restarted.handle("initial response")
            restarted.handle("follow-up response")
        assert "Career Readiness Report" in restarted.handle("/report")
        assert "python/technical" in restarted.handle("/history")
        assert "not measured (0 samples)" in restarted.handle("/metrics")
        # Store an actual fixture-run result in the isolated test schema, using a test double.
        from unittest.mock import Mock

        from career_coach.evaluation import run_evaluation
        from career_coach.models import Evaluation

        ai = Mock()
        ai.evaluate.return_value = Evaluation(
            score=1, evidence="I", feedback="test", gap="", follow_up="Why?"
        )
        benchmark = run_evaluation(ai, "test-model")
        with store.turn() as tx:
            tx.save_evaluation(benchmark)
        assert "duplicate-detection-v1" in restarted.handle("/metrics")
        assert "Scores within expected ranges: 2/3 (67%)" in restarted.handle("/metrics")
        # Reuse completed questions without losing the first session's evidence.
        restarted.handle("/retake")
        with psycopg.connect(store.url) as conn:
            assert conn.execute("SELECT count(*) FROM sessions").fetchone()[0] == 2
        with psycopg.connect(store.url) as conn:
            assert conn.execute("SELECT count(*) FROM observations").fetchone()[0] == 4
        with pytest.raises(RuntimeError):
            with store.turn() as tx:
                session = tx.load()
                session.profile["role"] = "should roll back"
                tx.save(session)
                raise RuntimeError()
        with store.turn() as tx:
            assert tx.load().profile["role"] != "should roll back"
        restarted.handle("/new")
        assert "python/technical" in restarted.handle("/history")
        import json
        import subprocess
        import sys
        from datetime import date, timedelta

        profile = tmp_path / "intake.json"
        profile.write_text(
            json.dumps(
                {
                    "role": "SDE Intern",
                    "background": "Student",
                    "deadline": str(date.today() + timedelta(days=7)),
                    "description": "Scalable cloud systems and ownership",
                }
            )
        )
        env = {**os.environ, "DATABASE_URL": store.url}
        first = subprocess.run(
            [sys.executable, "-m", "career_coach.cli", "--demo", "--profile", str(profile)],
            input="/paste\nA dictionary maps keys\nto values\n/end\n/quit\n",
            text=True,
            capture_output=True,
            env=env,
            timeout=20,
        )
        assert first.returncode == 0, "CLI demo failed"
        assert "What concrete example" in first.stdout
        second = subprocess.run(
            [sys.executable, "-m", "career_coach.cli", "--demo"],
            input="/quit\n",
            text=True,
            capture_output=True,
            env=env,
            timeout=20,
        )
        assert second.returncode == 0
        assert "What concrete example" in second.stdout
    finally:
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
