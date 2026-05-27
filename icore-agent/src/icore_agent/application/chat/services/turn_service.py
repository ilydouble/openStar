"""Application service for executing chat turns."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from concurrent.futures import ThreadPoolExecutor
import threading
from typing import Any, Protocol, cast

from icore_agent.application.files import FileAssetService
from icore_agent.application.usage import UsageService
from icore_agent.application.usage.recording import (
    begin_turn_usage_capture,
    end_turn_usage_capture,
    flush_turn_usage_capture,
)
from icore_agent.config import settings
from icore_agent.shared.logging.app_logger import get_logger
from icore_agent.shared.runtime.user_context import clear_runtime_user, set_runtime_user

from ..callback_ctx import reset_parent_callback, set_parent_callback
from ..commands import ChatTurnCommand
from ..context import ConversationMemory, dedupe_file_uuids, load_chat_context
from ..events import ChatStreamEvent, ChatTurnResult
from ..routing import AgentHint, ChatIntent, ChatRoutingDecision, resolve_routing
from .history_service import ChatHistoryService

log = get_logger(__name__)

CHAT_STREAM_WALL_BUDGET_SEC = 600


class AgentRunner(Protocol):
    """Minimal orchestrator surface used by chat turn workflows."""

    messages: list[dict[str, Any]]

    def __call__(self, message: str) -> Any:
        """Run one user message through the orchestrator."""
        ...


OrchestratorFactory = Callable[..., AgentRunner]


class ChatTurnService:
    """Coordinate chat session persistence, context loading, and agent execution."""

    def __init__(
        self,
        *,
        chat_history: ChatHistoryService,
        file_service: FileAssetService,
        conversation_memory: ConversationMemory,
        orchestrator_factory: OrchestratorFactory,
        usage_service: UsageService,
        wall_budget_sec: int = CHAT_STREAM_WALL_BUDGET_SEC,
    ) -> None:
        """Create a chat turn service with its application dependencies."""
        self._chat_history = chat_history
        self._file_service = file_service
        self._conversation_memory = conversation_memory
        self._orchestrator_factory = orchestrator_factory
        self._usage_service = usage_service
        self._wall_budget_sec = wall_budget_sec

    def _check_task_quota(self, command: ChatTurnCommand) -> None:
        """Raise PermissionError if the user's monthly task quota is exhausted.

        Called before any LLM work begins so users are never billed for a turn
        that would be denied.  Skipped when no usage_service is wired (tests).
        """
        if self._usage_service is None:
            return
        allowed, reason = self._usage_service.check_quota(
            command.user_id, "tasks"
        )
        if not allowed:
            raise PermissionError(
                f"task_quota_exceeded:{reason or 'monthly task quota exhausted'}"
            )

    async def run(self, command: ChatTurnCommand) -> ChatTurnResult:
        """Execute one non-streaming chat turn."""
        self._check_task_quota(command)
        route = await self._prepare_turn(command)
        context = await self._load_context(command)
        self._record_turn_quota(command, context)
        enable_tools = route.enable_tools or context.has_attachments
        loop = asyncio.get_running_loop()
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                result = await loop.run_in_executor(
                    executor,
                    lambda: self._invoke_agent(
                        command=command,
                        route=route,
                        context=context,
                        enable_tools=enable_tools,
                    ),
                )
        except Exception:
            log.exception("chat_turn_failed", session_id=command.session_id)
            raise

        reply = str(result)
        await self._append_memory_pair(command, reply)
        self._save_assistant_message(command, reply)
        # Deduct one task after the turn is fully persisted.
        if self._usage_service is not None:
            self._usage_service.consume_task(command.user_id)
        return ChatTurnResult(session_id=command.session_id, reply=reply)

    async def stream(
        self,
        command: ChatTurnCommand,
    ) -> AsyncIterator[ChatStreamEvent]:
        """Prepare one streaming chat turn and return its application event stream."""
        self._check_task_quota(command)
        route = await self._prepare_turn(command)
        context = await self._load_context(command)
        self._record_turn_quota(command, context)
        enable_tools = route.enable_tools or context.has_attachments
        return self._stream_prepared_turn(
            command=command,
            route=route,
            context=context,
            enable_tools=enable_tools,
        )

    async def _prepare_turn(
        self,
        command: ChatTurnCommand,
    ) -> ChatRoutingDecision:
        """Persist the user turn and return its routing decision."""
        file_uuids = dedupe_file_uuids(command.file_uuids)
        self._chat_history.ensure_owned_session(
            command.session_id,
            command.user_id,
            title=command.message.strip()[:255],
        )
        metadata = None
        if file_uuids:
            metadata = {"file_uuids": list(file_uuids)}
            caption = (command.display_caption or "").strip()
            if caption:
                metadata["display_caption"] = caption
        template_id = (command.template_id or "").strip()
        if template_id:
            metadata = metadata or {}
            metadata["template_id"] = template_id
        self._chat_history.save_user_message(
            command.session_id,
            command.user_id,
            command.message,
            metadata=metadata,
        )
        route = resolve_routing(
            command.agent_message or command.message,
            command.agent_hint,
        )
        log.info(
            "chat_request",
            session_id=command.session_id,
            stream=command.stream,
            intent=route.intent.value,
            enable_tools=route.enable_tools,
            agent_hint=route.agent_hint.value if route.agent_hint else None,
        )
        return route

    async def _load_context(self, command: ChatTurnCommand):
        """Load prompt context for one prepared command."""
        return await load_chat_context(
            session_id=command.session_id,
            file_uuids=command.file_uuids,
            user_id=command.user_id,
            file_service=self._file_service,
            chat_history=self._chat_history,
            conversation_memory=self._conversation_memory,
        )

    def _invoke_agent(
        self,
        *,
        command: ChatTurnCommand,
        route: ChatRoutingDecision,
        context,
        enable_tools: bool,
        callback_handler: Callable[..., None] | None = None,
    ) -> Any:
        """Invoke the blocking orchestrator for one chat turn."""
        capture_token = begin_turn_usage_capture()
        runtime_token = set_runtime_user(command.user)
        result = None
        try:
            orchestrator = self._orchestrator_factory(
                callback_handler=callback_handler,
                summary=context.summary,
                attachments_text=context.attachments_text,
                image_attachments=context.image_attachment_payloads,
                data_attachments=context.data_attachment_payloads,
                enable_tools=enable_tools,
                agent_hint=route.agent_hint.value if route.agent_hint else None,
                session_id=command.session_id,
                user_id=command.user_id,
            )
            runner = cast(AgentRunner, orchestrator)
            runner.messages = context.strands_history
            agent_input = command.agent_message or command.message
            result = runner(agent_input)
            return result
        finally:
            recorded = flush_turn_usage_capture(
                user_id=command.user_id,
                session_id=command.session_id,
                record_usage=self._usage_service.record_llm_usage,
            )
            if recorded == 0 and result is not None:
                self._record_estimated_turn_usage(
                    command,
                    prompt=command.agent_message or command.message,
                    reply=str(result),
                )
            end_turn_usage_capture(capture_token)
            clear_runtime_user(runtime_token)

    async def _stream_prepared_turn(
        self,
        *,
        command: ChatTurnCommand,
        route: ChatRoutingDecision,
        context,
        enable_tools: bool,
    ) -> AsyncIterator[ChatStreamEvent]:
        """Stream typed application events for a prepared chat turn."""
        yield self._initial_status_event(route, context)

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[tuple[str, object]] = asyncio.Queue()
        full_reply: list[str] = []
        seen_tool_ids: set[str] = set()

        def on_stream_event(**kwargs) -> None:
            """Forward Strands callbacks from the worker thread into the event queue."""
            current_tool = kwargs.get("current_tool_use")
            if current_tool:
                tool_id = str(current_tool.get("toolUseId") or "")
                if tool_id and tool_id not in seen_tool_ids:
                    seen_tool_ids.add(tool_id)
                    tool_name = str(current_tool.get("name", "unknown"))
                    tool_input = current_tool.get("input", {})
                    log.info(
                        "tool_call",
                        tool=tool_name,
                        input_preview=str(tool_input)[:120],
                        session_id=command.session_id,
                    )
                    asyncio.run_coroutine_threadsafe(
                        queue.put((
                            "status",
                            {
                                "tool": tool_name,
                                "input_preview": str(tool_input)[:200],
                            },
                        )),
                        loop,
                    )
            token = kwargs.get("data")
            if token and isinstance(token, str):
                asyncio.run_coroutine_threadsafe(
                    queue.put(("token", token)),
                    loop,
                )

        def run_agent() -> None:
            """Run the blocking orchestrator in a worker thread."""
            callback_token = set_parent_callback(on_stream_event)
            try:
                self._invoke_agent(
                    command=command,
                    route=route,
                    context=context,
                    enable_tools=enable_tools,
                    callback_handler=on_stream_event,
                )
            except Exception as exc:
                asyncio.run_coroutine_threadsafe(
                    queue.put(("error", str(exc))),
                    loop,
                )
            finally:
                reset_parent_callback(callback_token)
                asyncio.run_coroutine_threadsafe(
                    queue.put(("done", "")),
                    loop,
                )

        threading.Thread(target=run_agent, daemon=True).start()

        start = loop.time()
        step_idx = 1
        timed_out = False
        while True:
            if loop.time() - start > self._wall_budget_sec:
                timed_out = True
                break
            try:
                kind, payload = await asyncio.wait_for(
                    queue.get(),
                    timeout=1,
                )
            except TimeoutError:
                continue

            if kind == "token":
                text = payload if isinstance(payload, str) else str(payload)
                full_reply.append(text)
                for character in text:
                    yield ChatStreamEvent.token(character)
            elif kind == "status":
                step_idx += 1
                status_payload = payload if isinstance(payload, dict) else {}
                yield ChatStreamEvent.status(
                    step=step_idx,
                    tool=str(status_payload.get("tool", "")),
                    input_preview=str(status_payload.get("input_preview", "")),
                )
            elif kind == "error":
                message = payload if isinstance(payload, str) else str(payload)
                log.error(
                    "agent_stream_error",
                    error=message,
                    session_id=command.session_id,
                )
                yield ChatStreamEvent.error(message)
                break
            else:
                break

        if timed_out:
            log.warning(
                "agent_stream_wall_timeout",
                session_id=command.session_id,
                budget_sec=self._wall_budget_sec,
            )
            yield ChatStreamEvent.error(
                f"Agent run exceeded {self._wall_budget_sec}s budget and was stopped"
            )

        reply = "".join(full_reply)
        await self._append_memory_pair(command, reply)
        self._save_assistant_message(command, reply)
        # Deduct one task only on clean completion (not on error or timeout).
        if not timed_out and self._usage_service is not None:
            self._usage_service.consume_task(command.user_id)
        yield ChatStreamEvent.done()

    def _initial_status_event(
        self,
        route: ChatRoutingDecision,
        context,
    ) -> ChatStreamEvent:
        """Return the first stream status event for a routed chat turn."""
        route_label_map = {
            AgentHint.RESEARCH: "research_agent",
            AgentHint.KNOWLEDGE: "knowledge_agent",
            AgentHint.IMAGE: "image_agent",
            AgentHint.DATA: "data_agent",
            AgentHint.CODE: "code_agent",
            AgentHint.CHAT: "chat",
            ChatIntent.CHAT: "chat",
            ChatIntent.TASK: "orchestrator",
        }
        label = route_label_map.get(
            route.agent_hint or route.intent, "orchestrator")
        summary_bits: list[str] = []
        if context.has_rag:
            summary_bits.append("RAG 知识库已载入")
        if context.image_attachments:
            summary_bits.append(f"图片 {len(context.image_attachments)} 张")
        if context.data_attachments:
            summary_bits.append(f"数据 {len(context.data_attachments)} 份")
        preview = "，".join(summary_bits) or f"启动 {label}"
        return ChatStreamEvent.status(
            step=1,
            tool=label,
            input_preview=preview,
        )

    async def _append_memory_pair(
        self,
        command: ChatTurnCommand,
        reply: str,
    ) -> None:
        """Append completed turn messages to the conversation cache."""
        await self._conversation_memory.append_message(
            command.session_id,
            "user",
            command.message,
        )
        await self._conversation_memory.append_message(
            command.session_id,
            "assistant",
            reply,
        )

    def _save_assistant_message(
        self,
        command: ChatTurnCommand,
        reply: str,
    ) -> None:
        """Persist assistant output without failing an already completed turn."""
        try:
            self._chat_history.save_assistant_message(
                command.session_id,
                command.user_id,
                reply,
            )
        except (PermissionError, LookupError) as exc:
            log.warning(
                "assistant_message_persist_failed",
                session_id=command.session_id,
                error=str(exc),
            )

    def _record_turn_quota(self, command: ChatTurnCommand, context) -> None:
        """Persist attachment quota counters for files uploaded in this turn."""
        try:
            attachment_count = (
                len(context.image_attachments)
                + len(context.data_attachments)
            )
            if context.attachments_text:
                attachment_count += 1
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

    def _record_estimated_turn_usage(
        self,
        command: ChatTurnCommand,
        *,
        prompt: str,
        reply: str,
    ) -> None:
        """Persist estimated token usage when LiteLLM callbacks did not fire for a turn."""
        prompt_text = (prompt or "").strip()
        reply_text = (reply or "").strip()
        if not prompt_text and not reply_text:
            return
        try:
            from litellm import token_counter
        except Exception as exc:
            log.warning("estimated_turn_usage_failed", error=str(exc))
            return
        model = settings.effective_model_id()
        prompt_tokens = 0
        if prompt_text:
            try:
                prompt_tokens = int(
                    token_counter(
                        model=model,
                        messages=[{"role": "user", "content": prompt_text}],
                    )
                    or 0
                )
            except Exception:
                prompt_tokens = max(len(prompt_text) // 4, 1)
        completion_tokens = 0
        if reply_text:
            try:
                completion_tokens = int(
                    token_counter(model=model, text=reply_text) or 0
                )
            except Exception:
                completion_tokens = max(len(reply_text) // 4, 1)
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
