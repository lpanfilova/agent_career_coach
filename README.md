# nextLevelPersonalCoachForCareerLevel

Local, single-user career coach: Python + LangGraph + OpenAI + PostgreSQL + private Telegram polling.

1. Intake: target, self-reported experience, preparation deadline, pasted opportunity.
2. Four tasks: two technical questions, a coding exercise, an interview scenario. One at a time; up to one focused follow-up each. Review tasks include their function in a separate validated code field, displayed with the question and follow-up. Submitted code is **read, never executed**.
3. Career Readiness Report: evidence, strengths, gaps, feedback, curated learning links and deadline-based practice steps. No overall readiness score.
4. `/opportunities` ranks curated public sources across jobs, internships, research and entrepreneurship. `/match <description>` compares recognized requirement keywords with reported skills and demonstrated evidence. Neither checks eligibility or live availability.

## Run today

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/) and Docker Compose.

```sh
uv sync --extra dev
cp .env.example .env     # only on first setup; keep an existing .env
# Edit .env: set matching PostgreSQL password/URL and your OpenAI key.
docker compose up -d --wait
uv run career-coach chat
```

**In this workspace, `.env` already contains generated local database credentials.** Add your OpenAI key there; do not overwrite it. `.env` is ignored. The database binds only to localhost:5433 and persists in a Docker volume. Python runs locally. Stop the database with `docker compose stop`.

Your Amazon SDE Intern Summer 2027 intake is in `examples/amazon-intern.json` (user-supplied excerpt; not verified). It assumes **November 8, 2026** for “ASAP”; edit the deadline and add your programming experience as needed. Loading a profile starts a new assessment and keeps previous evidence in history.

```sh
uv run career-coach chat --profile examples/amazon-intern.json
# No API key needed for a SCRIPTED walkthrough (not a real assessment):
uv run career-coach chat --demo --profile examples/amazon-intern.json
```

In the CLI, `/paste` accepts multiline descriptions or code; finish with `/end` on its own line. `/quit` exits. Restart and use `/resume` to continue, including mid-follow-up. Switching between demo/live or model configurations requires `/new` (or `--profile`). Demo questions are fixed and are not tailored to the target.

Commands: `/start`, `/resume`, `/new`, `/report`, `/history`, `/opportunities`, `/match <description>`, `/help`. In Telegram, paste multiline text directly.

## Telegram

Create a bot through [BotFather](https://core.telegram.org/bots/tutorial#obtain-your-bot-token). Set `TELEGRAM_BOT_TOKEN` and your numeric `TELEGRAM_USER_ID` in `.env`. Your ID is `message.from.id` in a private message's [getUpdates response](https://core.telegram.org/bots/api#getupdates); retrieve it before starting polling and keep the token private. The bot ignores other users and all groups. Use one polling process and remove any existing webhook first if reusing a bot.

```sh
uv run career-coach telegram
```

Send `/start` privately. CLI and Telegram share the same active session. Your terminal must stay running. No hosting or scheduling is required.

If a turn fails, the bot and terminal show a safe error code (for example `openai_quota`, `database_unavailable` or `ai_invalid_output`) and recovery instructions. No raw exception bodies, credentials or answer content are logged. The model selects a numbered answer excerpt, and the app copies its text exactly; it never asks the model to reproduce a quote. If a turn fails, use `/resume` and resend the answer. Restart the app after code or `.env` changes.

## Memory and checks

PostgreSQL stores versioned session snapshots (profile, goal, transcript, follow-up, results, report/plan), per-question evidence observations, and processed Telegram update IDs. Each turn commits atomically under a single-user lock; failed model calls roll back. History preserves skill, criteria, score, evidence, model and rubric across `/new`. Compare similar questions manually; difficulty is not calibrated.

Rubric v1: **0** no relevant evidence; **1** partial/unclear; **2** correct with explanation; **3** correct with trade-offs/edge cases. Evidence quotes are copied directly from numbered answer excerpts selected by the model, with the selection constrained to valid IDs. AI judgments can be wrong; four questions cannot establish overall readiness. Demo observations are labeled. Missing evidence does not establish lack of ability.

```sh
uv run python scripts/check.py             # offline checks
uv run python scripts/check.py --postgres  # also isolated PostgreSQL + CLI restart checks
uv run python scripts/check.py --live      # also billable rubric, generation and multiline evidence checks; needs API key
uv run ruff check src tests scripts
```

The optional live checks include assessment generation and three examples covering weak, uncertain and well-supported answers with score ranges, including an instruction to inflate a grade. They are a small regression check, not a validated benchmark.

Session snapshots are application-managed around a LangGraph turn; no separate graph checkpoint service is needed. OpenAI uses [Responses structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs) with `store=False`; model is configurable via `OPENAI_MODEL`. Profile and answer text are sent to OpenAI in live mode; Telegram transports bot messages. Local transcripts remain in PostgreSQL. No automatic deletion or encryption at rest is implemented.

Deferred: live listing retrieval and eligibility checks, calibrated progress metrics, durable Telegram delivery, retention tools, hosting and scheduling. Follow-up notes are kept locally in Git-ignored `ISSUES.md`.
