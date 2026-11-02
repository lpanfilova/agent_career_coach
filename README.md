# nextLevelPersonalCoachForCareerLevel

## What it does

An AI career coach that helps students and professionals prepare for jobs, internships, research and entrepreneurial opportunities through a terminal or private Telegram chat. Each installation supports one user.

Provide a target opportunity or job description, background and preparation deadline. The coach asks two technical questions, a coding exercise and an interview scenario, with follow-ups when reasoning needs clarification. It produces a **Career Readiness Report** with demonstrated strengths, knowledge gaps, feedback, learning resources and a preparation plan.

Progress is saved between sessions. Submitted code is reviewed without execution. Opportunity discovery currently provides curated source suggestions and keyword matching against pasted descriptions; it does not retrieve live listings or verify eligibility.

## How to run

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/), Docker Compose and an OpenAI API key. Docker must be running.

```sh
git clone https://github.com/lpanfilova/agent_career_coach.git
cd agent_career_coach
uv sync
cp .env.example .env
```

Configure `.env`:

- Set `OPENAI_API_KEY`.
- Choose `POSTGRES_PASSWORD` and update the password in `DATABASE_URL` to match. Keep the example host, port and database settings for the default Compose setup.
- For Telegram, set `TELEGRAM_BOT_TOKEN` from [BotFather](https://core.telegram.org/bots/tutorial#obtain-your-bot-token) and `TELEGRAM_USER_ID` to the account's numeric `message.from.id` from [getUpdates](https://core.telegram.org/bots/api#getupdates). Retrieve the ID after messaging the bot, before starting polling.

Keep `.env` private; it is excluded from Git.

```sh
docker compose up -d --wait
uv run career-coach chat
```

For Telegram, run `uv run career-coach telegram` instead, keep the process running and send `/start` privately to the bot. Only the configured user is accepted; group messages are ignored. Both interfaces share the same session.

Use `/resume` to continue, `/report` to retrieve the completed report, `/new` to start another assessment and `/help` for all commands. Terminal users can enter multiline text with `/paste`, finish with `/end`, and exit with `/quit`.

For a scripted walkthrough without OpenAI calls, run `uv run career-coach chat --demo`. PostgreSQL is still required. Stop the application with Ctrl+C and the database with `docker compose stop`.

## High-level architecture

```mermaid
flowchart LR
    CLI[Terminal] <--> Service
    Telegram[Telegram private chat] <--> Owner[Owner ID check]
    subgraph Local[Local Python application]
        Owner <--> Service[Session service]
        Service <--> Graph[LangGraph assessment flow]
        Graph --> Report[Report and preparation plan]
        Report --> Service
    end
    Graph <--> OpenAI[OpenAI API]
    Service <--> DB[(PostgreSQL in Docker Compose)]
```

OpenAI generates questions and evaluates answers. PostgreSQL stores profiles, goals, conversations, results and reports. The Python application runs locally; assessment content is sent to OpenAI, and Telegram transports messages when enabled.

## Evaluation

Answers are scored from **0** (no relevant evidence) to **3** (correct reasoning with trade-offs and edge cases). Reported experience is kept separate from demonstrated evidence. These short assessments do not establish overall career readiness, and scores across sessions are not calibrated.

To run the automated checks:

```sh
uv sync --extra dev
uv run python scripts/check.py
uv run python scripts/check.py --postgres
uv run python scripts/check.py --postgres --live
```

The checks cover session recovery, transaction rollback, duplicate updates, access restrictions, complete coding prompts and evidence extraction. `--postgres` requires the database; `--live` additionally uses the configured OpenAI key and incurs API charges. Live checks cover question generation, multiline code, follow-ups and three rubric examples. This small regression suite is not a validated assessment benchmark.
