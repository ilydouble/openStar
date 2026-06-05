"""Pi agent runner — proxies chat turns to the pi-service Node.js microservice.

PiAgentRunner implements the AgentRunner protocol so ChatTurnService can
call it the same way as the Strands orchestrator: runner.messages = history,
then result = runner(user_message).

SSE event format from pi-service:
  {"type": "token",      "text": "..."}
  {"type": "tool_start", "name": "...", "args": {...}}
  {"type": "tool_end",   "name": "...", "is_error": bool}
  {"type": "error",      "message": "..."}
  {"type": "done"}
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx

from icore_agent.config import settings
from icore_agent.shared.logging.app_logger import get_logger

log = get_logger(__name__)

_REQUEST_TIMEOUT_SEC = 600.0


class PiAgentRunner:
    """Synchronous runner that streams chat turns through pi-service."""

    def __init__(
        self,
        *,
        session_id: str,
        system_prompt: str = "",
        callback_handler: Callable[..., None] | None = None,
    ) -> None:
        self.session_id = session_id
        self.system_prompt = system_prompt
        self.callback_handler = callback_handler
        self.messages: list[dict[str, Any]] = []

    def __call__(self, message: str) -> str:
        """Send one turn to pi-service and return the assembled reply."""
        url = f"{settings.pi_service_url}/v1/chat"
        payload: dict[str, Any] = {
            "session_id": self.session_id,
            "message": message,
            "system_prompt": self.system_prompt,
        }

        full_reply: list[str] = []
        cb = self.callback_handler

        log.info("pi_agent_turn_start", session_id=self.session_id, url=url)

        try:
            with httpx.Client(timeout=_REQUEST_TIMEOUT_SEC) as client:
                with client.stream("POST", url, json=payload) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line.startswith("data: "):
                            continue
                        try:
                            event = json.loads(line[6:])
                        except json.JSONDecodeError:
                            continue

                        etype = event.get("type")

                        if etype == "token":
                            text: str = event.get("text", "")
                            full_reply.append(text)
                            if cb:
                                cb(data=text)

                        elif etype == "tool_start":
                            name: str = event.get("name", "unknown")
                            args: Any = event.get("args", {})
                            log.info("pi_tool_start", tool=name, session_id=self.session_id)
                            if cb:
                                cb(
                                    current_tool_use={
                                        "name": name,
                                        "toolUseId": f"pi_{name}",
                                        "input": args,
                                    }
                                )

                        elif etype == "error":
                            msg = event.get("message", "unknown pi-service error")
                            log.error("pi_agent_stream_error", session_id=self.session_id, message=msg)
                            raise RuntimeError(f"pi-service error: {msg}")

                        elif etype == "done":
                            break

        except httpx.HTTPStatusError as exc:
            log.error(
                "pi_service_http_error",
                session_id=self.session_id,
                status=exc.response.status_code,
                url=url,
            )
            raise

        reply = "".join(full_reply)
        log.info("pi_agent_turn_end", session_id=self.session_id, reply_len=len(reply))
        return reply


def create_pi_orchestrator(
    *,
    callback_handler: Callable[..., None] | None = None,
    session_id: str = "",
    summary: str | None = None,
    **_kwargs: Any,
) -> PiAgentRunner:
    """Factory matching the OrchestratorFactory signature used by ChatTurnService."""
    return PiAgentRunner(
        session_id=session_id,
        system_prompt=summary or "",
        callback_handler=callback_handler,
    )
