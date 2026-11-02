from contextlib import contextmanager

import psycopg
from psycopg.types.json import Jsonb

from .models import Session

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id text PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now(),
    active boolean NOT NULL DEFAULT true, state jsonb NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_session ON sessions (active) WHERE active;
CREATE TABLE IF NOT EXISTS observations (
    session_id text NOT NULL REFERENCES sessions(id), question_index integer NOT NULL,
    skill text NOT NULL, kind text NOT NULL, score integer NOT NULL CHECK(score BETWEEN 0 AND 3),
    evidence text NOT NULL, criteria jsonb NOT NULL, model text NOT NULL, demo boolean NOT NULL,
    rubric text NOT NULL DEFAULT 'v1', created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (session_id, question_index)
);
CREATE TABLE IF NOT EXISTS processed_events (
    event_id text PRIMARY KEY, reply text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
"""


class Store:
    def __init__(self, url):
        self.url = url

    def initialize(self):
        with psycopg.connect(self.url) as conn:
            conn.execute(SCHEMA)

    @contextmanager
    def turn(self):
        with psycopg.connect(self.url) as conn:
            # Serialize CLI and Telegram turns for this single-user database.
            conn.execute("SELECT pg_advisory_xact_lock(718322)")
            yield Transaction(conn)


class Transaction:
    def __init__(self, conn):
        self.conn = conn

    def load(self):
        row = self.conn.execute("SELECT state FROM sessions WHERE active").fetchone()
        return Session.model_validate(row[0]) if row else None

    def save(self, session):
        self.conn.execute(
            "UPDATE sessions SET active=false WHERE active AND id <> %s", (session.id,)
        )
        self.conn.execute(
            """INSERT INTO sessions(id,state) VALUES (%s,%s)
            ON CONFLICT(id) DO UPDATE SET state=EXCLUDED.state""",
            (session.id, Jsonb(session.model_dump(mode="json"))),
        )
        for i, r in enumerate(session.results):
            self.conn.execute(
                """INSERT INTO observations
                (session_id,question_index,skill,kind,score,evidence,criteria,model,demo)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (
                    session.id,
                    i,
                    r.question.skill,
                    r.question.kind,
                    r.evaluation.score,
                    r.evaluation.evidence,
                    Jsonb(r.question.criteria),
                    session.model,
                    session.demo,
                ),
            )

    def cached(self, event_id):
        row = self.conn.execute(
            "SELECT reply FROM processed_events WHERE event_id=%s", (event_id,)
        ).fetchone()
        return row[0] if row else None

    def remember(self, event_id, reply):
        self.conn.execute(
            "INSERT INTO processed_events(event_id,reply) VALUES (%s,%s)", (event_id, reply)
        )

    def history(self):
        rows = self.conn.execute("""SELECT skill,kind,score,evidence,model,demo,created_at,rubric,criteria
             FROM observations ORDER BY created_at DESC, session_id, question_index LIMIT 40""").fetchall()
        if not rows:
            return "No completed question evidence yet."
        return (
            "Evidence history (ordinal scores; compare only similar criteria/difficulty/model):\n"
            + "\n".join(
                f"{dt.date()} | {skill}/{kind} | {score}/3 | {model} | {rubric}"
                f"{' | DEMO' if demo else ''}\nCriteria: {', '.join(criteria)}\nEvidence: {evidence!r}"
                for skill, kind, score, evidence, model, demo, dt, rubric, criteria in rows
            )
        )
