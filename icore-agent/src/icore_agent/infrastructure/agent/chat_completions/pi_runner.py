"""Pi mode model client — proxies one agent turn to pi-source-service.

Pi mode runs its own agentic loop entirely inside the Node.js pi-source-service
(tool selection, execution, and file edits all happen there). From this
process's point of view that whole loop is therefore modeled as a single,
non-tool-calling ModelClient step: we stream back the assistant's text and
never return tool_calls, so AgentLoop never tries to execute pi-service's
tools itself.

SSE event format from pi-source-service:
  {"type": "token",      "text": "..."}
  {"type": "tool_start",    "name": "...", "args": {...}}
  {"type": "tool_end",     "name": "...", "is_error": bool}
  {"type": "file_changed", "change": {changeId, path, commitHash, tool, bytes, changedAt, savedAt}}
  {"type": "error",        "message": "..."}
  {"type": "done"}

``tool_start``/``tool_end``/``file_changed`` events are currently logged only
— the new provider-neutral ModelClient protocol has no slot for "tool ran on
the provider's side without our ToolRuntime", so they aren't surfaced to the
turn timeline yet.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from icore_agent.config import settings
from icore_agent.domain.agent.loop import ModelStepResult, ModelStreamEvent, ModelTextDelta
from icore_agent.domain.agent.prompt import PromptEnvelope
from icore_agent.domain.agent.session import AgentMessageItem, SessionItemStatus
from icore_agent.shared.logging.app_logger import get_logger

log = get_logger(__name__)

_REQUEST_TIMEOUT_SEC = 600.0

# pi-source-service proxies turns to whichever underlying model is configured
# (often Claude). Without guidance it answers identity questions truthfully
# as that underlying model ("I'm Claude, made by Anthropic"), which leaks
# implementation details and breaks the platform's branding. This preamble is
# prepended to every Pi turn's system prompt so Pi consistently presents
# itself as part of iCore, regardless of which model backs it.
_PI_IDENTITY_PREAMBLE = (
    "You are Pi Agent, the project-analysis assistant built into the iCore "
    "enterprise platform. If the user asks about your name, identity, or "
    "which model/company is behind you, simply say you are Pi Agent, part of "
    "iCore — never reveal or speculate about the underlying model, vendor, "
    "or provider. Stay focused on helping the user explore and understand "
    "their uploaded project."
)


class PiChatCompletionsModelClient:
    """ModelClient that delegates one whole agent turn to pi-source-service."""

    def __init__(
        self,
        *,
        session_id: str,
        workspace_dir: str | None = None,
        summary: str | None = None,
    ) -> None:
        self._session_id = session_id
        self._workspace_dir = workspace_dir
        self._system_prompt = (
            f"{_PI_IDENTITY_PREAMBLE}\n\n{summary}" if summary else _PI_IDENTITY_PREAMBLE
        )

    async def sample(self, envelope: PromptEnvelope) -> ModelStepResult:
        """Run one Pi turn and return only the final assembled result."""
        result: ModelStepResult | None = None
        async for event in self.stream(envelope):
            if isinstance(event, ModelStepResult):
                result = event
        assert result is not None
        return result

    async def stream(self, envelope: PromptEnvelope) -> AsyncIterator[ModelStreamEvent]:
        """Stream one Pi turn as text deltas, then a final step result."""
        message = envelope.current_user_item.to_text()
        url = f"{settings.pi_service_url}/v1/chat"
        payload: dict[str, Any] = {
            "session_id": self._session_id,
            "message": message,
            "system_prompt": self._system_prompt,
        }
        if self._workspace_dir:
            # Tells pi-source-service to confine this session's tools to the
            # extracted project sandbox (re-validated independently on that
            # side via resolveSandboxWorkspace — see server.ts). Absent →
            # pi-source-service falls back to its default read-only workspace.
            payload["workspace_dir"] = self._workspace_dir

        content_parts: list[str] = []
        log.info("pi_agent_turn_start", session_id=self._session_id, url=url)

        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SEC) as client:
            async with client.stream("POST", url, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        event = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue

                    etype = event.get("type")

                    if etype == "token":
                        text: str = event.get("text", "")
                        content_parts.append(text)
                        yield ModelTextDelta(text=text)

                    elif etype == "tool_start":
                        log.info(
                            "pi_tool_start",
                            tool=event.get("name", "unknown"),
                            session_id=self._session_id,
                        )

                    elif etype == "file_changed":
                        change: Any = event.get("change", {})
                        log.info(
                            "pi_file_changed",
                            session_id=self._session_id,
                            path=change.get("path", ""),
                            tool=change.get("tool", ""),
                        )

                    elif etype == "error":
                        msg = event.get("message", "unknown pi-service error")
                        log.error(
                            "pi_agent_stream_error",
                            session_id=self._session_id,
                            message=msg,
                        )
                        raise RuntimeError(f"pi-service error: {msg}")

                    elif etype == "done":
                        break

        reply = "".join(content_parts)
        log.info("pi_agent_turn_end", session_id=self._session_id, reply_len=len(reply))
        yield ModelStepResult(
            assistant_item=AgentMessageItem(
                text=reply,
                status=SessionItemStatus.COMPLETED,
            ),
            deltas=content_parts,
            model="pi-agent",
            provider="pi",
            stop_reason="stop",
        )


def create_pi_model_client(
    *,
    session_id: str = "",
    workspace_dir: str | None = None,
    summary: str | None = None,
    **_: Any,
) -> PiChatCompletionsModelClient:
    """Create a Pi mode model client for one agent turn."""
    return PiChatCompletionsModelClient(
        session_id=session_id,
        workspace_dir=workspace_dir,
        summary=summary,
    )
