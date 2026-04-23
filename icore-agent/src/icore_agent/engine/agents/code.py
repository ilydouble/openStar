"""Code sub-agent — writes, debugs, and executes code via sequential runner.

For multi-step coding tasks it delegates to the mini-SWE-agent style
SequentialAgent (linear bash history, subprocess.run execution).
For quick code generation it uses Strands directly.
"""

import json

from strands import Agent, tool
from strands.models.litellm import LiteLLMModel

from ...config import settings
from ...tools.code_executor import run_python_snippet
from ...tools.file_ops import read_file, write_file, list_files
from ..sequential.agent import SequentialAgent

_SYSTEM_PROMPT = """
You are a software engineering assistant. You can:
- Write, review, and debug code in any language.
- Execute Python snippets directly via run_python_snippet.
- Explore the workspace with list_files, then read or edit files via read_file / write_file.
- For complex multi-step tasks (e.g. "set up a project", "fix a GitHub issue"),
  delegate to the sequential bash runner instead of doing everything in one shot.

Always use list_files first when you need to understand the project structure.
Return clean, well-commented code. Prefer correctness over brevity.
""".strip()


def _create_code_agent() -> Agent:
    model = LiteLLMModel(
        model_id=settings.model_id,
        params={
            "max_tokens": settings.agent_max_tokens,
            "temperature": 0.05,
            **settings.litellm_kwargs(),
        },
    )
    return Agent(
        model=model,
        system_prompt=_SYSTEM_PROMPT,
        tools=[run_python_snippet, list_files, read_file, write_file],
    )


@tool
def code_agent_tool(task: str, use_sequential: bool = False) -> str:
    """Delegate a coding task to the code sub-agent.

    For simple code generation / review set use_sequential=False (default).
    For multi-step bash-based tasks (e.g. project scaffolding, bug fixing
    across multiple files) set use_sequential=True to use the mini-SWE-agent
    style sequential runner.

    Args:
        task: Description of the coding task to perform.
        use_sequential: If True, runs as a sequential bash agent (mini-SWE style).

    Returns:
        Code, execution output, or task completion report.
    """
    if use_sequential:
        runner = SequentialAgent()
        result = runner.run(task)
        return json.dumps(result, ensure_ascii=False, indent=2)

    agent = _create_code_agent()
    result = agent(task)
    return str(result)
