"""全局配置管理"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ===== 推理 LLM =====
    llm_api_key: str = ""
    llm_base_url: str = "https://api.longcat.chat/openai"
    llm_model: str = "LongCat-Flash-Chat"

    # ===== 视觉模型（可独立切换）=====
    # 可选：dashscope(Qwen-VL) / openai(GPT-4o) / local(本地模型)
    vision_provider: str = "dashscope"
    vision_api_key: str = ""
    vision_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    vision_model: str = "qwen-vl-plus"

    # ===== Neo4j =====
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "lego123456"

    # ===== Redis =====
    redis_url: str = "redis://localhost:6379/0"

    # ===== 飞书 =====
    feishu_webhook_url: str = ""

    # ===== App =====
    app_env: str = "development"
    log_level: str = "INFO"
    use_real_vl: bool = False  # False=使用 Mock


@lru_cache
def get_settings() -> Settings:
    return Settings()
