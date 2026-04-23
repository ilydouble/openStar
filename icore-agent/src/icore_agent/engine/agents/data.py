"""Data sub-agent — SQL + pandas data-analysis specialist.

Reuses the existing code-execution tools (run_python_snippet, read_file,
list_files) but with a prompt focused on structured data work: CSV / Excel
inspection, pandas transformations, SQL query drafting, and light
statistical summarisation.

Exposed as a Strands @tool so the orchestrator can delegate to it.
"""

from __future__ import annotations

from strands import Agent, tool
from strands.models.litellm import LiteLLMModel
from strands.tools.executors import SequentialToolExecutor

from ...config import settings
from ...tools.code_executor import run_python_snippet
from ...tools.file_ops import read_file, list_files
from ..callback_ctx import sub_agent_callback

_SYSTEM_PROMPT = """
You are a data-analysis specialist. You help the user explore, transform and
summarise structured data (CSV, TSV, JSON, Excel, SQL-style tables).

Capabilities:
- Use list_files and read_file to inspect the workspace and sample data.
- Use run_python_snippet to execute pandas / numpy / sqlite3 / json code
  for real analysis — do not guess numbers, compute them.
- Draft SQL queries (SQLite dialect by default) when the user asks for a
  query; explain the logic briefly.
- Produce concise insights: describe the schema, key statistics, outliers,
  and answer the user's question with numbers.

Workflow:
1. If data is referenced but not provided, list_files to find it, then
   read a small head with run_python_snippet (e.g. pandas.read_csv(...).head()).
2. Run focused computations instead of dumping raw data.
3. Return: Schema → Approach → Result (numbers/tables) → Brief interpretation.
Return Markdown-formatted tables for small results.
""".strip()


def _create_data_agent() -> Agent:
    model = LiteLLMModel(
        model_id=settings.model_id,
        params={
            "max_tokens": settings.agent_max_tokens,
            "temperature": 0.1,
            **settings.litellm_kwargs(),
        },
    )
    return Agent(
        model=model,
        system_prompt=_SYSTEM_PROMPT,
        tools=[run_python_snippet, read_file, list_files],
        callback_handler=sub_agent_callback(),
        tool_executor=SequentialToolExecutor(),
    )


@tool
def data_agent_tool(task: str) -> str:
    """Delegate a data-analysis task to the data sub-agent.

    Use this for questions involving tabular data: CSV/Excel exploration,
    pandas transformations, SQL query authoring, aggregate statistics, or
    finding patterns / outliers in structured data. The agent can execute
    Python on the workspace to produce real numbers.

    Args:
        task: Natural-language description of the data question or
              transformation to perform.

    Returns:
        A markdown-formatted analysis with schema, method and results.
    """
    agent = _create_data_agent()
    result = agent(task)
    return str(result)


__all__ = ["data_agent_tool"]
