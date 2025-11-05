"""
Configuration management for the Node-RED Multi-Agent System
"""
from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # LLM Configuration
    llm_provider: Literal["ollama", "openai", "anthropic"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "mistral"

    openai_api_key: str = ""
    openai_model: str = "gpt-4-turbo-preview"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-opus-20240229"

    # Vector Database
    chroma_persist_dir: str = "./data/chroma_db"

    # Node-RED
    nodered_url: str = "http://localhost:1880"
    nodered_admin_auth: str = ""

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True

    # Reinforcement Learning
    min_feedback_score: int = 3
    similarity_threshold: float = 0.95

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
