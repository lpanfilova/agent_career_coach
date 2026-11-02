"""Run three billable scoring examples and save their measured results."""

import os

from dotenv import load_dotenv

from career_coach.ai import CoachAI
from career_coach.errors import explain_failure
from career_coach.evaluation import run_evaluation
from career_coach.metrics import fraction
from career_coach.store import Store


def main():
    load_dotenv(".env")
    if not os.getenv("OPENAI_API_KEY") or not os.getenv("DATABASE_URL"):
        raise SystemExit("Set OPENAI_API_KEY and DATABASE_URL in .env.")
    try:
        store = Store(os.environ["DATABASE_URL"])
        store.initialize()
        model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        run = run_evaluation(CoachAI(model), model)
        with store.turn() as tx:
            tx.save_evaluation(run)
        cases = run["cases"]
        print("Scoring agreement: " + fraction(sum(c["score_in_range"] for c in cases), len(cases)))
        print("All case checks passed: " + fraction(sum(c["passed"] for c in cases), len(cases)))
        for case in cases:
            print(
                f"{case['name']}: score={case['score']}, expected={case['expected_range']}, error={case['error'] or 'none'}"
            )
        print(
            "Saved to PostgreSQL. Use /metrics in the app. This is a regression check, not validated accuracy."
        )
        return 0 if all(c["passed"] for c in cases) else 1
    except Exception as exc:
        failure = explain_failure(exc)
        print(f"Evaluation failed [{failure.code}]. {failure.advice}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
