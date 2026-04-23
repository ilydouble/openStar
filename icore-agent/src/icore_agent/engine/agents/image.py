"""Image sub-agent — vision understanding + text-to-image generation.

Routes between two tools:
  understand_image  — GLM-4.6V-Flash vision (free) for analysing images the
                      user uploaded or URLs they provided.
  generate_image    — CogView-4 for producing images from a text prompt.

Exposed as a Strands @tool so the orchestrator can delegate to it.
"""

from __future__ import annotations

from strands import Agent, tool
from strands.models.litellm import LiteLLMModel
from strands.tools.executors import SequentialToolExecutor

from ...config import settings
from ...tools.image_tools import understand_image, generate_image
from ..callback_ctx import sub_agent_callback

_SYSTEM_PROMPT = """
You are a multimodal image specialist. You have two capabilities:

1. understand_image — given an image_source (URL or session-scoped filename)
   and a question, analyze the image and answer. Use this when the user
   uploaded an image or provided an image URL and wants information about it.

2. generate_image — given a descriptive prompt, create a new image via
   CogView-4. Use this when the user asks you to "draw", "generate",
   "create", or "design" an image.

Workflow:
- If the user provides or references an existing image → understand_image.
- If the user asks you to create/draw/design something new → generate_image.
- For ambiguous cases, prefer understand_image when an image_source is present.
- Always return the image URL or markdown link produced by generate_image so
  the orchestrator can display it to the user.
""".strip()


def _create_image_agent(session_id: str = "") -> Agent:
    """Create an image Agent with session_id captured for generate_image."""

    @tool
    def generate_image_scoped(prompt: str, size: str = "1024x1024") -> str:
        """Generate an image from a text prompt using CogView-4.

        Args:
            prompt: Natural-language description of the image to generate.
            size:   Output resolution (e.g. 1024x1024, 768x1344, 1344x768).

        Returns:
            A human-readable message with the remote URL and markdown link.
        """
        return generate_image(prompt=prompt, size=size, session_id=session_id)

    model = LiteLLMModel(
        model_id=settings.model_id,
        params={
            "max_tokens": settings.agent_max_tokens,
            "temperature": 0.3,
            **settings.litellm_kwargs(),
        },
    )
    return Agent(
        model=model,
        system_prompt=_SYSTEM_PROMPT,
        tools=[understand_image, generate_image_scoped],
        callback_handler=sub_agent_callback(),
        tool_executor=SequentialToolExecutor(),
    )


@tool
def image_agent_tool(
    task: str,
    image_source: str = "",
    session_id: str = "",
) -> str:
    """Delegate a vision / image-generation task to the image sub-agent.

    Use this when the user:
      - asks you to analyze / describe / read an uploaded image,
      - or asks you to draw / generate / create a new image from a prompt.

    Args:
        task:         Natural-language description of what to do with images.
        image_source: Optional URL or session-scoped filename pointing to an
                      existing image to analyze. Leave empty for pure
                      text-to-image generation requests.
        session_id:   Session identifier so generated images are stored in a
                      stable per-session folder.

    Returns:
        The sub-agent's synthesised answer, including any image URL or
        markdown link to render in the final reply.
    """
    agent = _create_image_agent(session_id=session_id)
    if image_source:
        query = f"{task}\n\nImage source: {image_source}"
    else:
        query = task
    result = agent(query)
    return str(result)


__all__ = ["image_agent_tool"]
