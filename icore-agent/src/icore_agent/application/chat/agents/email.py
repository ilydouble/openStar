"""Email sub-agent — sends, reads, and manages emails.

Exposed as a Strands @tool so the orchestrator can delegate to it.
"""

from __future__ import annotations

from strands import Agent, tool
from strands.tools.executors import SequentialToolExecutor

from ...config import settings
from ...tools.email_tools import send_email, list_inbox, search_emails
from ..callback_ctx import sub_agent_callback
from ..model_factory import create_litellm_model

_SYSTEM_PROMPT = """
You are an email specialist. You can:

1. send_email — compose and send emails to recipients
2. list_inbox — retrieve recent emails from inbox
3. search_emails — search for specific emails by keyword or sender

Always confirm with the user before sending important emails.
Keep responses concise and actionable.
""".strip()


def _create_email_agent() -> Agent:
    """Create an email processing agent."""
    model = create_litellm_model(
        max_tokens=settings.agent_max_tokens,
        temperature=0.1,
    )
    return Agent(
        model=model,
        system_prompt=_SYSTEM_PROMPT,
        tools=[send_email, list_inbox, search_emails],
        callback_handler=sub_agent_callback(),
        tool_executor=SequentialToolExecutor(),
    )


@tool
def email_agent_tool(task: str) -> str:
    """Handle email-related requests: sending, reading, or searching emails.

    Use this when the user wants to:
    - Send an email to someone
    - Check recent emails in their inbox
    - Search for specific emails

    Args:
        task: The email task description (e.g., "send email to john@example.com about meeting")

    Returns:
        Result of the email operation
    """
    agent = _create_email_agent()
    return str(agent(task))
