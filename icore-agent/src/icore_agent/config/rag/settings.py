from __future__ import annotations

from ..base import DomainSettings


class RagSettings(DomainSettings):
    env_domains = ("rag",)

    zhipu_api_base: str = "https://open.bigmodel.cn/api/paas/v4"
    zhipu_embed_model: str = "embedding-3"
    chroma_path: str = "/tmp/icore-chroma"
    chroma_collection: str = "icore_docs"
    rag_chunk_size: int = 500
    rag_chunk_overlap: int = 50
    rag_top_k: int = 5


rag_settings = RagSettings()
