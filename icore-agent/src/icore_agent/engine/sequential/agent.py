"""Sequential Agent — inspired by mini-SWE-agent.

Design principles (mirroring mini-SWE-agent v2):
  - Completely linear message history: every step just appends → easy to debug.
  - Only bash commands — no custom tool-calling interface needed.
  - subprocess.run per step → stateless, trivially sandboxable (swap for docker exec).
  - Pluggable environment (local / docker) and model (any LiteLLM-supported string).
"""

from __future__ import annotations

import re
import structlog
from dataclasses import dataclass, field
from typing import Any

from litellm import completion

from ...config import settings
from .environment import LocalEnvironment, BaseEnvironment

log = structlog.get_logger()

_SYSTEM_PROMPT = """
You are a sequential task executor. You solve tasks by running bash commands one at a time.

Rules:
1. Think briefly about your plan, then output EXACTLY ONE bash command in a ```bash ... ``` block.
2. After seeing the command output, decide the next command.
3. When the task is complete, output:
       TASK_COMPLETE: <concise result summary>
4. If you cannot proceed, output:
       TASK_FAILED: <reason>

Do NOT output multiple commands at once. Do NOT use Python unless bash cannot do it.
""".strip()

_CMD_PATTERN = re.compile(r"```bash\s*\n(.*?)```", re.DOTALL)
_DONE_PATTERN = re.compile(r"^(TASK_COMPLETE|TASK_FAILED):\s*(.*)", re.DOTALL)


@dataclass
class SequentialResult:
    status: str                    # "complete" | "failed" | "timeout"
    output: str                    # final result or failure reason
    steps: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SequentialAgent:
    """mini-SWE-agent style sequential executor."""

    model: str = field(default_factory=lambda: settings.effective_sequential_model)
    max_steps: int = field(default_factory=lambda: settings.sequential_max_steps)
    timeout: int = field(default_factory=lambda: settings.sequential_timeout_per_step)
    environment: BaseEnvironment = field(default_factory=LocalEnvironment)

    def run(self, task: str) -> SequentialResult:
        """Execute a task sequentially. Returns when done, failed, or max_steps reached."""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Task: {task}"},
        ]

        log.info("sequential_agent_start", task=task[:120], model=self.model)

        for step in range(1, self.max_steps + 1):
            model_kwargs = settings.litellm_kwargs()
            model_kwargs["model"] = self.model
            model_kwargs["messages"] = messages
            resp = completion(**model_kwargs)
            content: str = resp.choices[0].message.content or ""
            messages.append({"role": "assistant", "content": content})

            log.debug("sequential_agent_step", step=step, content_preview=content[:200])

            # ── Terminal conditions ────────────────────────
            done = _DONE_PATTERN.match(content.strip())
            if done:
                status_word, output = done.group(1), done.group(2).strip()
                status = "complete" if status_word == "TASK_COMPLETE" else "failed"
                log.info("sequential_agent_done", status=status, steps=step)
                return SequentialResult(status=status, output=output, steps=step,
                                        history=messages)

            # ── Extract and run bash command ───────────────
            cmd_match = _CMD_PATTERN.search(content)
            if not cmd_match:
                feedback = "No ```bash ... ``` block found. Please output exactly one bash command."
                messages.append({"role": "user", "content": feedback})
                continue

            cmd = cmd_match.group(1).strip()
            cmd_output = self.environment.execute(cmd, timeout=self.timeout)
            messages.append({"role": "user", "content": f"Output:\n{cmd_output}"})

        log.warning("sequential_agent_timeout", max_steps=self.max_steps)
        return SequentialResult(
            status="timeout",
            output=f"Reached max_steps={self.max_steps} without completing the task.",
            steps=self.max_steps,
            history=messages,
        )
