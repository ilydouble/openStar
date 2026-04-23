"""Conversation memory backed by Redis — with rolling summary.

Storage format (per session_id):
  {
    "summary":  "<GLM-generated summary of older turns>",
    "messages": [<last N raw messages>]
  }

When the raw message list exceeds settings.memory_max_messages, the oldest
messages are compressed into the summary via an LLM call, and only
settings.memory_keep_recent messages are kept verbatim.

This keeps the Redis payload small while preserving important context
from earlier in the conversation.
"""

from __future__ import annotations

import json
import structlog
import redis.asyncio as aioredis
from typing import Any

import litellm

from ..config import settings

log = structlog.get_logger()

_Message = dict[str, Any]

_SUMMARY_SYSTEM = (
    "You are a conversation summarizer. "
    "Given a previous summary (may be empty) and a list of new conversation turns, "
    "produce a concise updated summary in the same language as the conversation. "
    "Preserve key facts: names, goals, decisions, preferences, and any unresolved tasks. "
    "Output ONLY the summary text, no preamble."
)


class ConversationMemory:
    """Async Redis-backed conversation history store with rolling summary."""

    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _get_client(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    def _key(self, session_id: str) -> str:
        return f"icore:conv:{session_id}"

    async def _load(self, session_id: str) -> dict[str, Any]:
        """Load raw store dict; handles legacy plain-list format."""
        client = await self._get_client()
        raw = await client.get(self._key(session_id))
        if raw is None:
            return {"summary": "", "messages": []}
        try:
            data = json.loads(raw)
            # Backward-compat: old format was a plain list
            if isinstance(data, list):
                return {"summary": "", "messages": data}
            return data
        except json.JSONDecodeError:
            log.warning("conversation_memory_decode_error", session_id=session_id)
            return {"summary": "", "messages": []}

    async def _save(self, session_id: str, data: dict[str, Any]) -> None:
        client = await self._get_client()
        await client.set(
            self._key(session_id),
            json.dumps(data, ensure_ascii=False),
            ex=settings.memory_ttl_seconds,
        )

    async def _compress(self, existing_summary: str, to_compress: list[_Message]) -> str:
        """Call GLM to merge old summary + overflow messages into a new summary."""
        turns = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in to_compress
        )
        user_content = (
            f"Previous summary:\n{existing_summary}\n\nNew conversation turns:\n{turns}"
            if existing_summary
            else f"Conversation turns:\n{turns}"
        )
        try:
            resp = await litellm.acompletion(
                model=settings.model_id,
                messages=[
                    {"role": "system", "content": _SUMMARY_SYSTEM},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=512,
                temperature=0.1,
                **settings.litellm_kwargs(),
            )
            summary = resp.choices[0].message.content.strip()
            log.info("conversation_summary_updated", chars=len(summary))
            return summary
        except Exception as exc:
            log.warning("conversation_summary_failed", error=str(exc))
            # Fallback: plain concatenation so we never lose data silently
            return (existing_summary + "\n" + turns).strip()

    # ── Public API ────────────────────────────────────────────────────────────

    async def get_context(self, session_id: str) -> tuple[str, list[_Message]]:
        """Return (summary, recent_messages) for building the prompt."""
        data = await self._load(session_id)
        return data["summary"], data["messages"]

    async def get_messages(self, session_id: str) -> list[_Message]:
        """Return recent raw messages (kept for backward compatibility)."""
        data = await self._load(session_id)
        return data["messages"]

    async def append_message(self, session_id: str, role: str, content: str) -> None:
        """Append a message; triggers rolling compression when threshold is hit."""
        data = await self._load(session_id)
        data["messages"].append({"role": role, "content": content})

        if len(data["messages"]) > settings.memory_max_messages:
            keep = settings.memory_keep_recent
            to_compress = data["messages"][:-keep]
            data["summary"] = await self._compress(data["summary"], to_compress)
            data["messages"] = data["messages"][-keep:]
            log.info(
                "conversation_rolled",
                session_id=session_id,
                compressed=len(to_compress),
                kept=keep,
            )

        await self._save(session_id, data)
        log.debug(
            "conversation_memory_append",
            session_id=session_id,
            role=role,
            total_messages=len(data["messages"]),
            has_summary=bool(data["summary"]),
        )

    async def clear(self, session_id: str) -> None:
        """Delete all messages and summary for a session."""
        client = await self._get_client()
        await client.delete(self._key(session_id))
        log.info("conversation_memory_cleared", session_id=session_id)

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()
            self._redis = None


# App-level singleton — import from here
memory = ConversationMemory()
