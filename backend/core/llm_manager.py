"""
LLM Manager - Abstraction layer for multiple LLM providers
Supports Ollama (local), OpenAI, and Anthropic
"""
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod
import httpx
import json
from loguru import logger

from backend.config import settings


class BaseLLM(ABC):
    """Base class for LLM providers"""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Generate text from prompt"""
        pass

    @abstractmethod
    async def generate_with_history(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Generate text with conversation history"""
        pass


class OllamaLLM(BaseLLM):
    """Ollama local LLM provider"""

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.client = httpx.AsyncClient(timeout=120.0)

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Generate text from Ollama"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        return await self.generate_with_history(messages, temperature, max_tokens)

    async def generate_with_history(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Generate with conversation history"""
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }
            }

            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            return result["message"]["content"]

        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            raise


class OpenAILLM(BaseLLM):
    """OpenAI LLM provider (for future use)"""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        # Implementar con openai library
        raise NotImplementedError("OpenAI provider not implemented yet")

    async def generate_with_history(self, messages: List[Dict[str, str]], **kwargs) -> str:
        raise NotImplementedError("OpenAI provider not implemented yet")


class AnthropicLLM(BaseLLM):
    """Anthropic Claude LLM provider (for future use)"""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        # Implementar con anthropic library
        raise NotImplementedError("Anthropic provider not implemented yet")

    async def generate_with_history(self, messages: List[Dict[str, str]], **kwargs) -> str:
        raise NotImplementedError("Anthropic provider not implemented yet")


class LLMManager:
    """
    Main LLM Manager that routes to the appropriate provider
    """
    _instance: Optional['LLMManager'] = None
    _llm: Optional[BaseLLM] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._llm is None:
            self._initialize_llm()

    def _initialize_llm(self):
        """Initialize the LLM based on configuration"""
        provider = settings.llm_provider.lower()

        if provider == "ollama":
            self._llm = OllamaLLM(
                base_url=settings.ollama_base_url,
                model=settings.ollama_model
            )
            logger.info(f"Initialized Ollama LLM: {settings.ollama_model}")

        elif provider == "openai":
            if not settings.openai_api_key:
                raise ValueError("OpenAI API key not configured")
            self._llm = OpenAILLM(
                api_key=settings.openai_api_key,
                model=settings.openai_model
            )
            logger.info(f"Initialized OpenAI LLM: {settings.openai_model}")

        elif provider == "anthropic":
            if not settings.anthropic_api_key:
                raise ValueError("Anthropic API key not configured")
            self._llm = AnthropicLLM(
                api_key=settings.anthropic_api_key,
                model=settings.anthropic_model
            )
            logger.info(f"Initialized Anthropic LLM: {settings.anthropic_model}")

        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Generate text using the configured LLM"""
        return await self._llm.generate(prompt, system_prompt, temperature, max_tokens)

    async def generate_with_history(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Generate with conversation history"""
        return await self._llm.generate_with_history(messages, temperature, max_tokens)

    def get_provider_name(self) -> str:
        """Get the current provider name"""
        return settings.llm_provider
