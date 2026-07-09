"""Speech-to-text handlers."""

import asyncio

import httpx
from fastapi import Depends, File, Form, HTTPException, UploadFile

from icore_agent.config import settings
from icore_agent.domain.user import AuthenticatedUser
from icore_agent.shared.audio_convert import AudioConversionError, prepare_audio_for_zai_asr
from icore_agent.shared.logging.app_logger import get_logger

from icore_agent.interfaces.http.v1.dependencies import get_current_user
from ..schemas.transcribe import TranscribeResponse

log = get_logger(__name__)

_TRANSCRIBE_MAX_BYTES = 25 * 1024 * 1024
_ZAI_ASR_MODEL = "glm-asr-2512"
_ZAI_DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"


def _zai_transcribe_url() -> str:
    """Build the Z.AI audio transcriptions endpoint from configured base URL."""
    base = (settings.zai_base_url or _ZAI_DEFAULT_BASE_URL).rstrip("/")
    return f"{base}/audio/transcriptions"


def _zai_transcribe_error_detail(resp: httpx.Response) -> str:
    """Extract a human-readable error message from a Z.AI API error response."""
    detail = resp.text
    try:
        payload = resp.json()
        if not isinstance(payload, dict):
            return detail
        err = payload.get("error")
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
        if isinstance(err, str):
            return err
        if payload.get("message"):
            return str(payload["message"])
    except Exception:
        pass
    return detail


async def _prepare_audio_upload(
    *,
    audio: bytes,
    filename: str,
    mime: str | None,
) -> tuple[bytes, str, str]:
    """Normalize uploaded browser audio before forwarding it to Z.AI."""
    if len(audio) > _TRANSCRIBE_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Audio exceeds {_TRANSCRIBE_MAX_BYTES // (1024 * 1024)} MB "
                "transcription limit"
            ),
        )
    try:
        prepared_audio, safe_name, content_type = await asyncio.to_thread(
            prepare_audio_for_zai_asr,
            audio,
            filename,
            mime,
        )
    except AudioConversionError as exc:
        log.warning("zai_transcribe_convert_error", error=str(exc))
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if len(prepared_audio) > _TRANSCRIBE_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Converted audio exceeds {_TRANSCRIBE_MAX_BYTES // (1024 * 1024)} MB "
                "transcription limit"
            ),
        )
    return prepared_audio, safe_name, content_type


async def _zai_transcribe(
    *,
    audio: bytes,
    filename: str,
    mime: str | None,
    language: str | None,
) -> str:
    """Send normalized audio bytes to Z.AI GLM-ASR and return transcript text."""
    api_key = (settings.zai_api_key or "").strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Z.AI API key is not configured (ZAI_API_KEY / zai_api_key).",
        )
    files = {"file": (filename, audio, mime or "application/octet-stream")}
    data: dict[str, str] = {
        "model": _ZAI_ASR_MODEL,
        "stream": "false",
    }
    if language == "zh":
        data["prompt"] = "请使用中文转写。"
    elif language == "en":
        data["prompt"] = "Transcribe in English."
    headers = {"Authorization": f"Bearer {api_key}"}
    url = _zai_transcribe_url()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=30.0)) as client:
            resp = await client.post(url, headers=headers, files=files, data=data)
    except httpx.RequestError as exc:
        log.warning("zai_transcribe_request_error", error=str(exc))
        raise HTTPException(
            status_code=502,
            detail=f"Z.AI transcription request failed: {exc}",
        ) from exc

    if resp.status_code >= 400:
        detail = _zai_transcribe_error_detail(resp)
        log.warning(
            "zai_transcribe_api_error",
            status=resp.status_code,
            detail_preview=detail[:200],
        )
        raise HTTPException(
            status_code=502,
            detail=detail or f"Z.AI transcription HTTP {resp.status_code}",
        )

    try:
        payload = resp.json()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Invalid JSON from Z.AI transcription API",
        ) from exc
    text = (payload.get("text") or "").strip(
    ) if isinstance(payload, dict) else ""
    return text


async def transcribe_audio(
    file: UploadFile = File(
        description="Audio file (webm, mp3, wav, m4a, ...)"),
    language: str = Form(""),
    user: AuthenticatedUser = Depends(get_current_user),
) -> TranscribeResponse:
    """Accept multipart audio from the browser and return ASR text."""
    _ = user
    lang_norm = language.strip().lower()[:16]
    base = lang_norm.split("-")[0] if lang_norm else ""
    asr_lang = base if base in {"zh", "en"} else ""
    audio = await file.read()
    if not audio:
        raise HTTPException(status_code=400, detail="Empty audio upload")
    prepared_audio, safe_name, content_type = await _prepare_audio_upload(
        audio=audio,
        filename=file.filename or "speech.webm",
        mime=file.content_type,
    )
    text = await _zai_transcribe(
        audio=prepared_audio,
        filename=safe_name,
        mime=content_type,
        language=asr_lang or None,
    )
    log.info("zai_transcribed", chars=len(text), asr_lang=asr_lang or "auto")
    return TranscribeResponse(text=text)
