"""Fixed diagnostic messages: never expose exception bodies, URLs or user input."""

from dataclasses import dataclass

import openai
import psycopg
from pydantic import ValidationError


class ModelOutputError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class Failure:
    code: str
    advice: str

    def turn_reply(self):
        return (
            f"That turn failed [{self.code}]. {self.advice} "
            "Your previous progress is saved. Use /resume to see the current question, "
            "then resend your answer."
        )


OUTPUT_FAILURES = {
    "ai_invalid_output": "The model returned an invalid assessment response. Please try again.",
    "ai_no_output": "The model returned no usable assessment response. Please try again.",
}


def explain_failure(exc):
    if isinstance(exc, ModelOutputError):
        if exc.code in OUTPUT_FAILURES:
            return Failure(exc.code, OUTPUT_FAILURES[exc.code])
        return Failure("ai_invalid_output", OUTPUT_FAILURES["ai_invalid_output"])
    if isinstance(exc, openai.AuthenticationError):
        return Failure("openai_authentication", "Check OPENAI_API_KEY in .env and restart the app.")
    if isinstance(exc, openai.PermissionDeniedError):
        return Failure("openai_permission", "Check your API project's model permissions.")
    if isinstance(exc, openai.RateLimitError):
        if exc.code == "insufficient_quota":
            return Failure("openai_quota", "Check your OpenAI API billing and available credits.")
        return Failure(
            "openai_rate_limit", "OpenAI is rate limiting requests. Wait briefly and retry."
        )
    if isinstance(exc, openai.APITimeoutError):
        return Failure("openai_timeout", "OpenAI timed out. Wait briefly and retry.")
    if isinstance(exc, openai.APIConnectionError):
        return Failure("openai_connection", "Check internet connectivity and retry.")
    if isinstance(exc, openai.APIStatusError):
        return Failure(
            "openai_request",
            "OpenAI rejected or could not complete the request. Check OPENAI_MODEL and retry.",
        )
    if isinstance(exc, psycopg.OperationalError):
        return Failure(
            "database_unavailable", "Check PostgreSQL is running: docker compose up -d --wait."
        )
    if isinstance(exc, psycopg.Error):
        return Failure(
            "database_error", "A database operation failed. Check the database configuration."
        )
    if isinstance(exc, ValidationError):
        return Failure(
            "invalid_state",
            "Saved state or response validation failed. Report this error code before starting a new session.",
        )
    return Failure(
        "internal_error", "An unexpected application error occurred. Report this error code."
    )
