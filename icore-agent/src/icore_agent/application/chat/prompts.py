"""Prompt policy for chat orchestration."""

from __future__ import annotations

from typing import Any

from .routing import AgentHint

ORCHESTRATOR_SYSTEM_PROMPT_BASE = """
You are iCore Agent, an intelligent assistant running on the iCore enterprise platform.
The application layer has already made a coarse routing decision for this turn.
Your role is to use the available specialist tools when the turn requires them
and synthesize their results into a final user-facing response.

## Sub-agents available

- research_agent_tool
    For: public web research, multi-source synthesis, competitive analysis,
         fact verification, fetching live data from URLs or REST APIs.
    NOT for: internal company documents.

- code_agent_tool
    For: writing, reviewing, debugging, or executing code; project scaffolding;
         reading / writing files in the workspace.
    Set use_sequential=True for multi-step bash tasks.

- knowledge_agent_tool
    For: questions answered by INTERNAL uploaded documents — company policies,
         product manuals, contracts, proprietary data.
    NOT for: general web knowledge.

- image_agent_tool
    For: analysing uploaded images (OCR, description, visual Q&A) OR
         generating new images from a text prompt (CogView-4).
    Pass image_source when the user uploaded an image or gave a URL.

- data_agent_tool
    For: tabular data analysis — CSV/Excel exploration, pandas transforms,
         SQL query drafting, aggregate statistics, outlier detection.
    Actually executes Python to compute real numbers.

## Dispatch rules
1. If tools are available, call exactly the sub-agent that fits the user's task.
2. If multiple domains apply (e.g. "research the topic AND write code for it"),
   call sub-agents sequentially and combine their outputs.
3. For pure conversational replies (greetings, clarifications, simple reasoning)
   that require no tool use, respond directly without calling any sub-agent.
4. Always synthesise sub-agent results into a clear, user-facing final answer.
   Do not just forward raw tool output.
5. If a sub-agent's result is insufficient, try calling it again with a more
   refined query before giving up.
""".strip()

AGENT_HINT_DIRECTIVES: dict[AgentHint, str] = {
    AgentHint.RESEARCH: "The user clicked the Research shortcut — prefer research_agent_tool for this turn unless the request is clearly unrelated.",
    AgentHint.CODE: "The user clicked the Code shortcut — prefer code_agent_tool for this turn unless the request is clearly unrelated.",
    AgentHint.KNOWLEDGE: "The user clicked the Knowledge shortcut — prefer knowledge_agent_tool for this turn, scoped to their uploaded documents.",
    AgentHint.IMAGE: "The user clicked the Image shortcut — prefer image_agent_tool; if an image is attached, analyze it; otherwise generate one.",
    AgentHint.DATA: "The user clicked the Data shortcut — prefer data_agent_tool for tabular analysis, SQL drafting or pandas work.",
    AgentHint.CHAT: "The user clicked the Chat shortcut — answer directly as a conversational assistant; do not call any sub-agent.",
}


def build_orchestrator_system_prompt(
    summary: str | None,
    attachments_text: str | None = None,
    image_attachments: list[dict[str, Any]] | None = None,
    data_attachments: list[dict[str, Any]] | None = None,
    agent_hint: AgentHint | str | None = None,
) -> str:
    """Combine chat prompt policy with context prepared for one turn."""
    parts = [ORCHESTRATOR_SYSTEM_PROMPT_BASE]
    hint = _coerce_agent_hint(agent_hint)
    if hint is not None:
        parts.append("## Routing hint\n" + AGENT_HINT_DIRECTIVES[hint])
    if attachments_text:
        parts.append(
            "## 用户上传的文档（直接阅读，无需调用工具）\n\n" + attachments_text
        )
    if image_attachments:
        lines = ["## 用户上传的图片（可通过 image_agent_tool 分析）"]
        for img in image_attachments:
            lines.append(
                f"- filename: `{img['filename']}`  ref: `{img['ref']}`"
            )
        lines.append(
            "需要分析时，调用 image_agent_tool 并传入 image_source=上面的 ref。"
        )
        parts.append("\n".join(lines))
    if data_attachments:
        parts.append(_build_data_attachment_prompt(data_attachments))
    if summary:
        parts.append("## Earlier conversation summary\n" + summary)
    return "\n\n".join(parts)


def _coerce_agent_hint(agent_hint: AgentHint | str | None) -> AgentHint | None:
    """Return a typed agent hint when the input is a valid hint value."""
    if agent_hint is None:
        return None
    if isinstance(agent_hint, AgentHint):
        return agent_hint
    hint = str(agent_hint).strip().lower()
    if not hint:
        return None
    try:
        return AgentHint(hint)
    except ValueError:
        return None


def _build_data_attachment_prompt(data_attachments: list[dict[str, Any]]) -> str:
    """Return prompt context for structured data attachments."""
    lines = [
        "## 用户上传的数据文件（通过 data_agent_tool 用 pandas 真实计算）",
        "每个文件已落盘到服务器本地路径，可在 run_python_snippet 中直接 `pd.read_csv(abs_path)` / `pd.read_excel(abs_path)`。",
    ]
    for data in data_attachments:
        cols = ", ".join(
            f"{column['name']}({column['dtype']})"
            for column in (data.get("columns") or [])[:20]
        )
        rows = data.get("row_count")
        rows_txt = f"{rows} 行" if rows is not None else "行数未知"
        lines.append(
            f"\n### `{data['filename']}`\n"
            f"- abs_path: `{data['abs_path']}`\n"
            f"- size: {rows_txt}，{len(data.get('columns') or [])} 列\n"
            f"- columns: {cols or '(未解析)'}"
        )
        if data.get("preview_error"):
            lines.append(f"- preview_error: {data['preview_error']}")
        if data.get("preview_md"):
            lines.append(f"- head preview:\n\n{data['preview_md']}")
    lines.append(
        "\n分析这些文件时，请优先调用 data_agent_tool，并把具体问题连同 abs_path 一起传入。"
    )
    return "\n".join(lines)
