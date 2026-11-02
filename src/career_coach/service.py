from datetime import UTC, datetime
from uuid import uuid4

from .graph import build_graph, current_prompt
from .models import Session
from .opportunities import discover, match_opportunity

HELP = "Commands: /start or /resume, /new, /report, /history, /metrics, /retake, /opportunities, /match <description>, /help. CLI: /quit."


class Service:
    def __init__(self, store, ai, demo=False, model="gpt-4.1-mini"):
        self.store, self.ai, self.demo, self.model = store, ai, demo, model
        self.graph = build_graph(ai)

    def handle(self, text, event_id=None):
        text = text.strip()
        if not text:
            return "Please send a text answer."
        if len(text) > 24000:
            return "Please keep each message under 24,000 characters."
        with self.store.turn() as tx:
            if event_id:
                cached = tx.cached(event_id)
                if cached is not None:
                    return cached
            s = tx.load()
            command = text.split()[0].split("@")[0].lower()
            if command == "/new" or s is None:
                s = Session(
                    id=str(uuid4()),
                    created_at=datetime.now(UTC).isoformat(),
                    demo=self.demo,
                    model="scripted-demo" if self.demo else self.model,
                )
                created = True
            else:
                created = False
            s.messages.append({"role": "user", "content": text})
            if command == "/help":
                reply = HELP
            elif command == "/metrics":
                reply = tx.metrics()
            elif command == "/retake":
                if s.stage != "complete":
                    reply = (
                        "Complete the current assessment before /retake. Use /resume to continue."
                    )
                elif s.demo != self.demo or (not s.demo and s.model != self.model):
                    reply = "Restore the session's model/mode before /retake so scores remain comparable."
                else:
                    s = Session(
                        id=str(uuid4()),
                        created_at=datetime.now(UTC).isoformat(),
                        demo=s.demo,
                        model=s.model,
                        stage="assessment",
                        profile=s.profile.copy(),
                        assessment=s.assessment.model_copy(deep=True),
                        messages=[{"role": "user", "content": text}],
                    )
                    reply = (
                        "Retake: same questions, criteria and model. Practice effects may influence scores.\n\n"
                        + current_prompt(s)
                    )
            elif command == "/history":
                reply = tx.history()
            elif command == "/opportunities":
                reply = discover(s.profile)
            elif command == "/match":
                description = text.partition(" ")[2].strip()
                reply = (
                    match_opportunity(description, s.profile, s.results)
                    if description
                    else "Use /match followed by a pasted opportunity description."
                )
            elif command == "/report":
                reply = (
                    s.report
                    or "Report is available after the four assessment tasks. " + current_prompt(s)
                )
            elif command in ("/start", "/resume", "/new") or created:
                reply = (
                    "DEMO MODE: scripted questions and scores; no real assessment.\n"
                    if s.demo
                    else ""
                ) + current_prompt(s)
            elif text.startswith("/"):
                reply = HELP
            else:
                if s.demo != self.demo or (not s.demo and s.model != self.model):
                    return "Session model/mode differs from configuration. Restore it or use /new."
                reply = self.graph.invoke({"session": s, "text": text, "reply": ""})["reply"]
            s.messages.append({"role": "assistant", "content": reply})
            tx.save(s)
            if event_id:
                tx.remember(event_id, reply)
            return reply
