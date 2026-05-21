"""Convert uploaded audio into formats accepted by Z.AI GLM-ASR (WAV / MP3)."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

_ZAI_SUPPORTED_EXTENSIONS = frozenset({".wav", ".mp3", ".mpeg", ".mpga"})
_MIME_TO_SUFFIX: dict[str, str] = {
    "audio/webm": ".webm",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/wave": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/ogg": ".ogg",
    "audio/opus": ".opus",
}


class AudioConversionError(Exception):
    """Raised when ffmpeg cannot normalize audio for GLM-ASR."""


def _ffmpeg_executable() -> str:
    """Return the ffmpeg binary path or raise when it is not installed."""
    path = shutil.which("ffmpeg")
    if not path:
        raise AudioConversionError(
            "ffmpeg is not installed; install ffmpeg to transcribe WebM and other formats."
        )
    return path


def _guess_input_suffix(filename: str, mime: str | None) -> str:
    """Infer a file suffix from the upload name or MIME type."""
    suffix = Path(filename or "audio").suffix.lower()
    if suffix:
        return suffix
    if mime:
        base = mime.split(";")[0].strip().lower()
        mapped = _MIME_TO_SUFFIX.get(base)
        if mapped:
            return mapped
    return ".bin"


def _convert_to_wav_with_ffmpeg(audio: bytes, input_suffix: str) -> bytes:
    """Run ffmpeg to produce mono 16 kHz WAV bytes from arbitrary input audio."""
    ffmpeg = _ffmpeg_executable()
    with tempfile.TemporaryDirectory(prefix="icore-asr-") as tmpdir:
        root = Path(tmpdir)
        input_path = root / f"input{input_suffix}"
        output_path = root / "output.wav"
        input_path.write_bytes(audio)
        cmd = [
            ffmpeg,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(input_path),
            "-ac",
            "1",
            "-ar",
            "16000",
            str(output_path),
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=60,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise AudioConversionError("Audio conversion timed out.") from exc
        except OSError as exc:
            raise AudioConversionError(
                f"Audio conversion failed: {exc}") from exc

        if proc.returncode != 0:
            stderr = (proc.stderr or b"").decode(
                "utf-8", errors="replace").strip()
            detail = stderr or f"ffmpeg exited with code {proc.returncode}"
            raise AudioConversionError(f"Audio conversion failed: {detail}")

        if not output_path.is_file():
            raise AudioConversionError("Audio conversion produced no output.")

        wav = output_path.read_bytes()
        if not wav:
            raise AudioConversionError(
                "Audio conversion produced an empty file.")
        return wav


def prepare_audio_for_zai_asr(
    audio: bytes,
    filename: str,
    mime: str | None,
) -> tuple[bytes, str, str]:
    """Return WAV (or passthrough MP3/WAV) bytes and upload metadata for GLM-ASR."""
    safe_name = (filename or "audio").replace(
        "\r", "").replace("\n", "").strip() or "audio.webm"
    input_suffix = _guess_input_suffix(safe_name, mime)

    if input_suffix in _ZAI_SUPPORTED_EXTENSIONS:
        content_type = (
            mime or "application/octet-stream").split(";")[0].strip()
        if input_suffix == ".wav" and not content_type.startswith("audio/"):
            content_type = "audio/wav"
        if input_suffix in {".mp3", ".mpeg", ".mpga"} and not content_type.startswith("audio/"):
            content_type = "audio/mpeg"
        return audio, safe_name, content_type

    wav = _convert_to_wav_with_ffmpeg(audio, input_suffix)
    stem = Path(safe_name).stem or "speech"
    return wav, f"{stem}.wav", "audio/wav"
