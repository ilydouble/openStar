"""Direct LiteLLM Chat Completions model client for prompt envelopes."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import litellm

from icore_agent.config import settings
from icore_agent.contexts.agent.domain.loop import (
    ModelReasoningDelta,
    ModelStepResult,
    ModelStreamEvent,
    ModelTextDelta,
)
from icore_agent.contexts.agent.domain.prompt import PromptEnvelope
from icore_agent.contexts.agent.domain.session import (
    AgentMessageItem,
    ReasoningItem,
    SessionItemStatus,
)

from .renderer import (
    render_chat_completions_messages,
    render_chat_completions_tool_choice,
    render_chat_completions_tools,
)
from .request_policy import build_chat_completions_request
from .stream_adapter import (
    LiteLLMStreamAdapter,
    adapt_complete_response,
    is_stream_response,
    iter_stream_chunks,
)


class ChatCompletionsModelClient:
    """Model client that performs one LiteLLM Chat Completions sampling step."""

    def __init__(
        self,
        *,
        model_id: str,
        client_args: dict[str, Any],
        params: dict[str, Any],
    ) -> None:
        """Create a model client with resolved provider config."""
        self._model_id = model_id
        self._client_args = dict(client_args)
        self._params = dict(params)
        provider, separator, _model_name = model_id.partition("/")
        self._provider = provider if separator and provider else None

    async def sample(self, envelope: PromptEnvelope) -> ModelStepResult:
        """Call LiteLLM once and return provider-neutral assistant/tool items."""
        deltas: list[str] = []
        reasoning_parts: list[str] = []
        result: ModelStepResult | None = None
        async for event in self.stream(envelope):
            if isinstance(event, ModelTextDelta):
                deltas.append(event.text)
            elif isinstance(event, ModelReasoningDelta):
                reasoning_parts.append(event.text)
            elif isinstance(event, ModelStepResult):
                result = event
        if result is None:
            reasoning_text = "".join(reasoning_parts)
            return ModelStepResult(
                assistant_item=AgentMessageItem(
                    text="".join(deltas),
                    status=SessionItemStatus.COMPLETED,
                ),
                reasoning_item=(
                    ReasoningItem(
                        text=reasoning_text,
                        status=SessionItemStatus.COMPLETED,
                    )
                    if reasoning_text.strip()
                    else None
                ),
                deltas=deltas,
                model=self._model_id,
                provider=self._provider,
                stop_reason="stop",
            )
        return _model_step_result_copy(result, deltas=deltas)

    async def stream(
        self,
        envelope: PromptEnvelope,
    ) -> AsyncIterator[ModelStreamEvent]:
        """Call LiteLLM once and yield provider-neutral streaming events."""
        request = build_chat_completions_request(
            model_id=self._model_id,
            messages=render_chat_completions_messages(envelope),
            tools=render_chat_completions_tools(envelope),
            tool_choice=render_chat_completions_tool_choice(envelope),
            client_args=self._client_args,
            params=self._params,
        )
        response = await litellm.acompletion(**request)
        if not is_stream_response(response):
            for event in adapt_complete_response(
                response,
                model_id=self._model_id,
                provider=self._provider,
            ):
                yield event
            return

        adapter = LiteLLMStreamAdapter(
            model_id=self._model_id,
            provider=self._provider,
        )
        async for chunk in iter_stream_chunks(response):
            for event in adapter.consume(chunk):
                yield event
        for event in adapter.finalize():
            yield event


def create_chat_completions_model_client(
    *,
    session_id: str = "",
    user_id: str = "",
    **_: Any,
) -> ChatCompletionsModelClient:
    """Create a LiteLLM Chat Completions model client for one agent turn."""
    selected_model = settings.effective_model_id()
    resolved = settings.resolve_litellm_config(
        model_id=selected_model,
        user_id=user_id,
        session_id=session_id,
        max_tokens=settings.agent_max_tokens,
        temperature=settings.agent_temperature,
    )
    return ChatCompletionsModelClient(
        model_id=resolved.model_id,
        client_args=resolved.client_args,
        params=resolved.params,
    )


def _model_step_result_copy(
    result: ModelStepResult,
    *,
    deltas: list[str],
) -> ModelStepResult:
    """Return a model step result with collected compatibility deltas."""
    return ModelStepResult(
        assistant_item=result.assistant_item,
        reasoning_item=result.reasoning_item,
        tool_calls=result.tool_calls,
        deltas=deltas,
        usage=result.usage,
        model=result.model,
        provider=result.provider,
        stop_reason=result.stop_reason,
        raw_response_id=result.raw_response_id,
        raw_payload=result.raw_payload,
    )
