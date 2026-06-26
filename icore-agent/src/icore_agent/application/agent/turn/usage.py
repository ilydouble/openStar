"""Usage and quota side effects for agent turns."""

from __future__ import annotations

from typing import Any

from icore_agent.application.agent.loop.types import PreparedAgentRunner
from icore_agent.application.usage.recording import (
    begin_turn_usage_capture,
    end_turn_usage_capture,
    flush_turn_usage_capture,
)
from icore_agent.config import settings
from icore_agent.domain.agent import ChatCompletionRole
from icore_agent.domain.agent.prompt import PromptEnvelope
from icore_agent.shared.logging.app_logger import get_logger
from icore_agent.shared.runtime.user_context import clear_runtime_user, set_runtime_user

token_counter = None

log = get_logger(__name__)


class TurnUsageRecorder:
    """Keep turn quota and LLM usage accounting outside lifecycle orchestration."""

    def __init__(self, usage_service: Any | None) -> None:
        """Create a usage recorder around the optional usage service."""
        self._usage_service = usage_service

    def check_task_quota(self, command: Any) -> None:
        """Raise PermissionError if the user's monthly task quota is exhausted."""
        if self._usage_service is None:
            return
        allowed, reason = self._usage_service.check_quota(
            command.user_id,
            "tasks",
        )
        if not allowed:
            raise PermissionError(
                f"task_quota_exceeded:{reason or 'monthly task quota exhausted'}"
            )

    def record_attachment_quota(self, command: Any, context: Any) -> None:
        """Persist attachment quota counters for files uploaded in this turn."""
        if self._usage_service is None:
            return
        try:
            attachment_count = (
                len(context.image_attachments)
                + len(context.file_attachments)
            )
            if attachment_count:
                self._usage_service.consume_quota(
                    command.user_id,
                    "attachments",
                    attachment_count,
                )
        except KeyError:
            log.warning(
                "turn_quota_user_missing",
                user_id=command.user_id,
                session_id=command.session_id,
            )

    def consume_task(self, command: Any) -> None:
        """Consume one completed task quota unit."""
        if self._usage_service is not None:
            self._usage_service.consume_task(command.user_id)

    def invoke_with_usage(self, command: Any):
        """Return a runner invoker that records actual or estimated LLM usage."""
        def _invoke(
            runner: PreparedAgentRunner,
            prompt_envelope: PromptEnvelope,
        ) -> Any:
            capture_token = begin_turn_usage_capture()
            runtime_token = set_runtime_user(command.user)
            result = None
            try:
                result = runner(prompt_envelope)
                return result
            finally:
                if self._usage_service is not None:
                    recorded = flush_turn_usage_capture(
                        user_id=command.user_id,
                        session_id=command.session_id,
                        record_usage=self._usage_service.record_llm_usage,
                    )
                    if recorded == 0 and result is not None:
                        self.record_estimated_turn_usage(
                            command,
                            prompt=prompt_envelope.usage_text(),
                            reply=str(result),
                        )
                end_turn_usage_capture(capture_token)
                clear_runtime_user(runtime_token)

        return _invoke

    def record_estimated_turn_usage(
        self,
        command: Any,
        *,
        prompt: str,
        reply: str,
    ) -> None:
        """Persist estimated token usage when LiteLLM callbacks did not fire."""
        if self._usage_service is None:
            return
        prompt_text = (prompt or "").strip()
        reply_text = (reply or "").strip()
        if not prompt_text and not reply_text:
            return
        model = settings.effective_model_id()
        prompt_tokens = self._count_tokens(
            model=model,
            prompt_text=prompt_text,
        )
        completion_tokens = self._count_tokens(
            model=model,
            reply_text=reply_text,
        )
        total_tokens = prompt_tokens + completion_tokens
        if total_tokens <= 0:
            return
        try:
            self._usage_service.record_llm_usage(
                user_id=command.user_id,
                session_id=command.session_id,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )
        except KeyError:
            log.warning(
                "estimated_turn_usage_user_missing",
                user_id=command.user_id,
                session_id=command.session_id,
            )

    def _count_tokens(
        self,
        *,
        model: str,
        prompt_text: str = "",
        reply_text: str = "",
    ) -> int:
        """Count tokens with LiteLLM when available and use a safe estimate otherwise."""
        text = prompt_text or reply_text
        if not text:
            return 0
        counter = _get_token_counter()
        if counter is not None:
            try:
                if prompt_text:
                    return int(
                        counter(
                            model=model,
                            messages=[{
                                "role": ChatCompletionRole.USER.value,
                                "content": prompt_text,
                            }],
                        )
                        or 0
                    )
                return int(counter(model=model, text=reply_text) or 0)
            except Exception:
                pass
        return max(len(text) // 4, 1)


def _get_token_counter():
    """Load LiteLLM token counting lazily to keep imports side-effect-light."""
    global token_counter
    if token_counter is not None:
        return token_counter
    try:
        from litellm import token_counter as litellm_token_counter
    except Exception as exc:
        log.warning("estimated_turn_usage_failed", error=str(exc))
        return None
    token_counter = litellm_token_counter
    return token_counter
