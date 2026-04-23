"""Image tools — vision understanding + text-to-image generation.

- understand_image: GLM-4.6V-Flash（免费）通过 LiteLLM vision completion
- generate_image:   CogView-4 直调 Zhipu /images/generations REST 端点

Both are exposed as Strands @tool for the image sub-agent to call.
"""

from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path

import httpx
import structlog
from litellm import completion as litellm_completion
from strands import tool

from ..config import settings

log = structlog.get_logger()

_SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
_VISION_TIMEOUT = 60
_GEN_TIMEOUT = 60


def _resolve_image_source(image_source: str) -> str:
    """Return a URL or `data:` URI usable by vision APIs.

    - http(s) URL → returned as-is
    - Local path (absolute or relative to image_save_dir) → base64 data URI
    """
    s = image_source.strip()
    if s.startswith(("http://", "https://", "data:")):
        return s

    path = Path(s)
    if not path.is_absolute():
        path = Path(settings.image_save_dir) / s
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_source}")
    mime, _ = mimetypes.guess_type(str(path))
    if not mime or not mime.startswith("image/"):
        mime = "image/jpeg"
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


@tool
def understand_image(image_source: str, question: str = "") -> str:
    """Analyze an image and answer questions about it using a vision model.

    Args:
        image_source: Either a public http(s) URL or a session-scoped filename
                      (relative to the session's image store) or an absolute
                      local path to an image file.
        question:     What to ask about the image. If empty, a general
                      description is produced.

    Returns:
        Text describing / answering the question about the image.
    """
    prompt = question.strip() or "请详细描述这张图片的内容，包括主要元素、场景、文字和任何值得关注的细节。"
    log.info("understand_image", source=image_source[:120], q_preview=prompt[:80])

    try:
        image_ref = _resolve_image_source(image_source)
    except FileNotFoundError as exc:
        return f"[ERROR] {exc}"
    except Exception as exc:
        return f"[ERROR] Invalid image_source: {exc}"

    litellm_params: dict = {
        "model": settings.vision_model_id,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_ref}},
                ],
            }
        ],
        "max_tokens": 2048,
        "temperature": 0.3,
        "timeout": _VISION_TIMEOUT,
    }
    # Route to the Z.AI / Zhipu endpoint via LiteLLM's OpenAI-compatible layer.
    if settings.zai_api_key:
        litellm_params["api_key"] = settings.zai_api_key
    if settings.model_api_base:
        litellm_params["api_base"] = settings.model_api_base

    try:
        resp = litellm_completion(**litellm_params)
        content = resp["choices"][0]["message"]["content"]
        return content or "(vision model returned empty response)"
    except Exception as exc:
        log.error("understand_image_error", error=str(exc))
        return f"[ERROR] Vision call failed: {exc}"


def _gen_api_key() -> str:
    return settings.zai_api_key or os.getenv("ZAI_API_KEY", "")


@tool
def generate_image(
    prompt: str,
    size: str = "1024x1024",
    session_id: str = "",
) -> str:
    """Generate an image from a text prompt using CogView-4.

    The image URL returned by Zhipu is downloaded and saved locally under
    `{image_save_dir}/{session_id}/` so the frontend can reference it via a
    stable path. Both the remote URL and a relative local path are returned.

    Args:
        prompt:     Natural-language description of the image to generate.
        size:       Output resolution. Supported: 1024x1024, 768x1344,
                    864x1152, 1344x768, 1152x864, 1440x720, 720x1440.
        session_id: Optional session identifier for storing the image locally.

    Returns:
        A human-readable line containing the remote URL and (when saved)
        the local filename, plus an embeddable markdown image link.
    """
    log.info("generate_image", prompt_preview=prompt[:120], size=size)

    api_key = _gen_api_key()
    if not api_key:
        return "[ERROR] ZAI_API_KEY is not configured."

    url = f"{settings.image_gen_base.rstrip('/')}/images/generations"
    payload = {
        "model": settings.image_gen_model_id,
        "prompt": prompt,
        "size": size,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=_GEN_TIMEOUT) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        log.warning("generate_image_http_error",
                    status=exc.response.status_code, body=exc.response.text[:500])
        return f"[ERROR] Image generation HTTP {exc.response.status_code}: {exc.response.text[:400]}"
    except Exception as exc:
        log.error("generate_image_error", error=str(exc))
        return f"[ERROR] Image generation failed: {exc}"

    items = data.get("data") or []
    if not items or not items[0].get("url"):
        return f"[ERROR] Unexpected response: {str(data)[:400]}"

    remote_url = items[0]["url"]

    # Best-effort local save for frontend stability
    local_rel: str | None = None
    try:
        session_dir = Path(settings.image_save_dir) / (session_id or "_shared")
        session_dir.mkdir(parents=True, exist_ok=True)
        filename = f"cogview_{os.urandom(6).hex()}.png"
        with httpx.Client(timeout=_GEN_TIMEOUT) as client:
            r = client.get(remote_url)
            r.raise_for_status()
            (session_dir / filename).write_bytes(r.content)
        local_rel = f"{session_id or '_shared'}/{filename}"
        log.info("generate_image_saved", path=str(session_dir / filename))
    except Exception as exc:
        log.warning("generate_image_local_save_failed", error=str(exc))

    # Prefer our own /images endpoint so the link does not expire with the
    # 7-day signature on the Zhipu CDN URL.
    display_url = f"/api/v1/agent/images/{local_rel}" if local_rel else remote_url
    lines = [
        f"Image generated for prompt: {prompt[:200]}",
        f"Markdown: ![generated]({display_url})",
    ]
    if local_rel:
        lines.append(f"Local path: {local_rel}")
    lines.append(f"Remote URL (expires in ~7 days): {remote_url}")
    return "\n".join(lines)


__all__ = ["understand_image", "generate_image", "_SUPPORTED_IMAGE_EXTS"]
