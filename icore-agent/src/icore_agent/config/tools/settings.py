from __future__ import annotations

from ..base import DomainSettings


class ToolsSettings(DomainSettings):
    env_domains = ("tools",)

    tavily_api_key: str = ""
    file_ops_max_size_mb: int = 10
    zhipu_search_engine: str = "search_std"


tools_settings = ToolsSettings()
