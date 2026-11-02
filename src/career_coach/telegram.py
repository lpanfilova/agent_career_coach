import asyncio
import logging

import httpx

from .errors import explain_failure

log = logging.getLogger(__name__)


def authorized(message, owner):
    return (
        message.get("chat", {}).get("type") == "private"
        and message.get("from", {}).get("id") == owner
        and message.get("chat", {}).get("id") == owner
    )


def chunks(text, size=3500):
    # Telegram's limit is measured in UTF-16 code units.
    part, units = "", 0
    for char in text:
        width = 2 if ord(char) > 0xFFFF else 1
        if units + width > size:
            yield part
            part, units = "", 0
        part += char
        units += width
    if part:
        yield part


async def run_bot(service, token, owner):
    base = f"https://api.telegram.org/bot{token}/"
    async with httpx.AsyncClient(timeout=45) as client:

        async def api(method, payload):
            response = await client.post(base + method, json=payload)
            response.raise_for_status()
            data = response.json()
            if not data.get("ok"):
                raise RuntimeError("Telegram rejected request")
            return data["result"]

        offset = 0
        log.info("Telegram polling started; only the configured private user is accepted.")
        while True:
            try:
                updates = await api(
                    "getUpdates", {"offset": offset, "timeout": 30, "allowed_updates": ["message"]}
                )
                for update in updates:
                    message = update.get("message", {})
                    if authorized(message, owner):
                        text = message.get("text", "")
                        try:
                            reply = (
                                await asyncio.to_thread(
                                    service.handle, text, f"telegram:{update['update_id']}"
                                )
                                if text
                                else "Please send text; file uploads are not supported."
                            )
                        except Exception as exc:
                            failure = explain_failure(exc)
                            log.error(
                                "Assessment turn failed [%s] (%s); state rolled back. No message content logged.",
                                failure.code,
                                type(exc).__name__,
                            )
                            reply = failure.turn_reply()
                        for part in chunks(reply):
                            await api("sendMessage", {"chat_id": owner, "text": part})
                    offset = update["update_id"] + 1
            except (httpx.HTTPError, RuntimeError):
                # Never log httpx exception URLs: they contain the bot token.
                log.error("Telegram request failed; retrying in 5 seconds.")
                await asyncio.sleep(5)
