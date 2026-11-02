import argparse
import asyncio
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from .ai import CoachAI, DemoAI
from .errors import explain_failure
from .service import Service
from .store import Store
from .telegram import run_bot


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="nextLevelPersonalCoachForCareerLevel")
    parser.add_argument("mode", choices=["chat", "telegram", "init-db"], nargs="?", default="chat")
    parser.add_argument("--demo", action="store_true", help="Scripted flow, not a real assessment")
    parser.add_argument(
        "--profile", type=Path, help="Start a new CLI assessment from an intake JSON file"
    )
    args = parser.parse_args()
    if args.profile and args.mode != "chat":
        parser.error("--profile is supported only in chat mode")
    logging.basicConfig(level=logging.WARNING)
    # httpx INFO logging exposes Telegram token-bearing request URLs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    url = os.getenv("DATABASE_URL")
    if not url:
        parser.error("Set DATABASE_URL in .env (see .env.example).")
    demo = args.demo or os.getenv("COACH_DEMO", "false").lower() == "true"
    if (
        args.mode != "init-db"
        and not demo
        and not os.getenv("OPENAI_API_KEY", "").startswith("sk-")
    ):
        parser.error("Set OPENAI_API_KEY in .env, or use --demo for a scripted walkthrough.")
    token, owner = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_USER_ID", "")
    if args.mode == "telegram" and (not token or not owner.isdigit()):
        parser.error("Set TELEGRAM_BOT_TOKEN and numeric TELEGRAM_USER_ID in .env.")
    store = Store(url)
    try:
        store.initialize()
        if args.mode == "init-db":
            print("Database initialized.")
            return
        model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        service = Service(store, DemoAI() if demo else CoachAI(model), demo, model)
        if args.mode == "telegram":
            asyncio.run(run_bot(service, token, int(owner)))
            return
        if args.profile:
            profile = json.loads(args.profile.read_text())
            values = [profile[key] for key in ("role", "background", "deadline", "description")]
            if not all(isinstance(value, str) and value.strip() for value in values):
                raise ValueError("Profile fields must be nonempty strings")
            from datetime import date

            if date.fromisoformat(profile["deadline"]) < date.today():
                raise ValueError("Profile deadline has passed; edit the JSON")
            service.handle("/new")
            for value in values:
                reply = service.handle(value)
            print(reply)
        else:
            print(service.handle("/resume"))
        while True:
            try:
                text = input("\nYou> ")
                if text.strip() == "/paste":
                    print("Paste your description or code. Finish with /end on its own line.")
                    lines = []
                    while (line := input()) != "/end":
                        lines.append(line)
                    text = "\n".join(lines)
            except (EOFError, KeyboardInterrupt):
                print("\nSaved. Restart to resume.")
                break
            if text.strip() == "/quit":
                break
            try:
                print("\nCoach> " + service.handle(text))
            except Exception as exc:
                print(explain_failure(exc).turn_reply())
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        failure = explain_failure(exc)
        parser.exit(1, f"Startup failed [{failure.code}]. {failure.advice}\n")


if __name__ == "__main__":
    main()
