from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from icore_agent.lib.audio_convert import (
    AudioConversionError,
    prepare_audio_for_zai_asr,
)


def test_prepare_audio_passthrough_wav_without_conversion():
    audio, name, mime = prepare_audio_for_zai_asr(
        b"RIFF....",
        "clip.wav",
        "audio/wav",
    )
    assert audio == b"RIFF...."
    assert name == "clip.wav"
    assert mime == "audio/wav"


@patch("icore_agent.lib.audio_convert._convert_to_wav_with_ffmpeg")
def test_prepare_audio_converts_webm_to_wav(mock_convert):
    mock_convert.return_value = b"RIFFconverted"
    audio, name, mime = prepare_audio_for_zai_asr(
        b"\x1a\x45\xdf\xa3",
        "speech.webm",
        "audio/webm",
    )
    mock_convert.assert_called_once()
    assert mock_convert.call_args.args[1] == ".webm"
    assert audio == b"RIFFconverted"
    assert name == "speech.wav"
    assert mime == "audio/wav"


@patch("icore_agent.lib.audio_convert.shutil.which", return_value=None)
def test_prepare_audio_reports_missing_ffmpeg(mock_which):
    _ = mock_which
    with pytest.raises(AudioConversionError, match="ffmpeg is not installed"):
        prepare_audio_for_zai_asr(b"webm", "speech.webm", "audio/webm")


@patch("icore_agent.lib.audio_convert.shutil.which", return_value="/usr/bin/ffmpeg")
@patch("icore_agent.lib.audio_convert.subprocess.run")
def test_convert_to_wav_invokes_ffmpeg(mock_run, mock_which):
    _ = mock_which

    def _fake_run(cmd, **_kwargs):
        output_path = next(arg for arg in cmd if str(arg).endswith(".wav"))
        Path(output_path).write_bytes(b"RIFFout")
        return MagicMock(returncode=0, stderr=b"")

    mock_run.side_effect = _fake_run
    audio, name, mime = prepare_audio_for_zai_asr(b"input", "note.webm", "audio/webm")

    assert audio == b"RIFFout"
    assert name == "note.wav"
    assert mime == "audio/wav"
    cmd = mock_run.call_args.args[0]
    assert cmd[0] == "/usr/bin/ffmpeg"
    assert "-ar" in cmd and "16000" in cmd
