"""Account billing schemas."""

from pydantic import BaseModel


class ByokRequest(BaseModel):
    api_key: str = ""
    api_base: str = ""
    model: str = ""
