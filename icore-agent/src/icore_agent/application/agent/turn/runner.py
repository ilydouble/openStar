"""Prepared-runner construction for agent turns."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from icore_agent.application.agent.loop.agent_loop import AgentLoopRequest
from icore_agent.application.agent.loop.types import PreparedAgentRunner
from icore_agent.application.agent.tool import StrandsToolEventBridge
from icore_agent.shared.logging.app_logger import get_logger

log = get_logger(__name__)

OrchestratorFactory = Callable[..., PreparedAgentRunner]


class AgentTurnRunnerFactory:
    """Build provider-specific runners while exposing an agent-turn request."""

    def __init__(
        self,
        orchestrator_factory: OrchestratorFactory,
        *,
        file_service: Any | None = None,
        pi_workspace_service: Any | None = None,
    ) -> None:
        """Create a runner factory from the existing orchestrator factory."""
        self._orchestrator_factory = orchestrator_factory
        self._file_service = file_service
        self._pi_workspace_service = pi_workspace_service

    def build_loop_request(
        self,
        *,
        command: Any,
        context: Any,
        turn_id: str,
        invoke: Callable[[PreparedAgentRunner, str], Any] | None,
    ) -> AgentLoopRequest:
        """Build an AgentLoopRequest for one turn."""
        tool_bridge = StrandsToolEventBridge(
            session_id=command.session_id,
            turn_id=turn_id,
        )
        runner = self.build_runner(
            command=command,
            context=context,
            tool_bridge=tool_bridge,
        )
        return AgentLoopRequest(
            session_id=command.session_id,
            turn_id=turn_id,
            message=_message_with_attachment_refs(
                command.agent_message or command.message,
                context,
            ),
            runner=runner,
            history_messages=context.strands_history,
            tool_bridge=tool_bridge,
            invoke=invoke,
        )

    def build_runner(
        self,
        *,
        command: Any,
        context: Any,
        tool_bridge: StrandsToolEventBridge,
    ) -> PreparedAgentRunner:
        """Create one prepared Strands runner for AgentLoop."""
        orchestrator = self._orchestrator_factory(
            callback_handler=tool_bridge.on_callback,
            summary=context.summary,
            session_id=command.session_id,
            hooks=[tool_bridge],
            user_id=command.user_id,
            user_memory_prompt=context.user_memory_prompt,
            file_service=self._file_service,
            pi_workspace_dir=self._resolve_pi_workspace_dir(command),
        )
        return cast(PreparedAgentRunner, orchestrator)

    def _resolve_pi_workspace_dir(self, command: Any) -> str | None:
        """Extract the user's selected Pi project into its sandbox directory.

        Returns the absolute path Pi should be confined to, or ``None`` when
        Pi mode isn't using an uploaded project (falls back to pi-service's
        default read-only workspace). Never raises — a missing/foreign/corrupt
        workspace silently degrades to "no project selected" rather than
        failing the whole turn, since the user can simply re-pick a project.
        """
        workspace_id = (getattr(command, "pi_workspace_id", None) or "").strip()
        if not workspace_id or self._pi_workspace_service is None:
            return None
        try:
            from icore_agent.config import settings

            sandbox_root = Path(settings.pi_workspace_sandbox_root) / command.user_id / workspace_id
            resolved = self._pi_workspace_service.extract_into_sandbox(
                owner_user_id=command.user_id,
                workspace_id=workspace_id,
                destination_root=sandbox_root,
            )
            return str(resolved)
        except Exception:
            log.warning(
                "pi_workspace_resolve_failed",
                session_id=command.session_id,
                user_id=command.user_id,
                workspace_id=workspace_id,
                exc_info=True,
            )
            return None


def _message_with_attachment_refs(message: str, context: Any) -> str:
    """Append compact attachment references to the current turn message."""
    note = _attachment_reference_note(context)
    if not note:
        return message
    return f"{message.rstrip()}\n\n{note}"


def _attachment_reference_note(context: Any) -> str:
    """Build a compact metadata-only attachment note for the agent."""
    image_refs = getattr(context, "image_attachment_payloads", []) or []
    file_refs = getattr(context, "file_attachment_payloads", []) or []
    if not image_refs and not file_refs:
        return ""

    lines = ["Attached files for this turn:"]
    for attachment in image_refs:
        lines.append(
            "- image_attachment "
            f"filename={_json_value(attachment.get('filename'))} "
            f"uuid={_json_value(attachment.get('file_uuid'))} "
            f"ref={_json_value(attachment.get('ref'))}"
        )
    for attachment in file_refs:
        lines.append(
            "- file_attachment "
            f"filename={_json_value(attachment.get('filename'))} "
            f"uuid={_json_value(attachment.get('file_uuid'))}"
        )
    if file_refs:
        lines.append(
            "Use read_uploaded_file with the uuid when file_attachment "
            "contents are needed."
        )
    return "\n".join(lines)


def _json_value(value: Any) -> str:
    """Render one attachment metadata value as a quoted JSON string."""
    return json.dumps(str(value or ""), ensure_ascii=False)
