"""Speech-to-text schemas."""

from pydantic import BaseModel, Field


class TranscribeResponse(BaseModel):
    text: str = Field(..., description="Plain text from GLM-ASR transcription")
