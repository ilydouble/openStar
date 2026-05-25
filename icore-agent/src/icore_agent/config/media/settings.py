from __future__ import annotations

from ..base import DomainSettings


class MediaSettings(DomainSettings):
    env_domains = ("media",)

    vision_model_id: str = "zai/glm-4.6v-flash"
    image_gen_model_id: str = "cogview-4"
    image_gen_base: str = "https://api.z.ai/api/paas/v4"
    image_save_dir: str = "/tmp/icore-images"
    image_upload_max_mb: int = 5
    data_upload_max_mb: int = 20
    data_preview_rows: int = 10


media_settings = MediaSettings()
