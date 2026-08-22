"""Dynamic LLM gateway using Strategy pattern with runtime routing."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from langchain.schema import AIMessage, HumanMessage, SystemMessage

from resilience import AsyncCircuitBreaker, with_retry_and_circuit_breaker


@dataclass
class GatewayMessage:
    role: str
    content: str


@dataclass
class LLMGenerateRequest:
    messages: Sequence[GatewayMessage]
    provider: str = "auto"
    model: Optional[str] = None
    max_tokens: int = 2048
    temperature: float = 0.2


class LLMProvider(ABC):
    """Strategy interface for pluggable LLM providers."""

    name: str
    default_model: str
    estimated_cost_per_1k_tokens: float

    def __init__(self) -> None:
        self.circuit_breaker = AsyncCircuitBreaker()

    @abstractmethod
    def is_configured(self) -> bool:
        pass

    @abstractmethod
    async def generate(self, request: LLMGenerateRequest) -> str:
        pass


class OpenAIProvider(LLMProvider):
    name = "openai"
    default_model = "gpt-4o-mini"
    estimated_cost_per_1k_tokens = 0.004

    def __init__(self, api_key: str, default_model: Optional[str] = None) -> None:
        super().__init__()
        self.api_key = api_key
        if default_model:
            self.default_model = default_model

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate(self, request: LLMGenerateRequest) -> str:
        from langchain_openai import ChatOpenAI

        model_name = request.model or self.default_model
        client = ChatOpenAI(
            openai_api_key=self.api_key,
            model_name=model_name,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )

        async def _invoke() -> str:
            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: client.invoke(_to_langchain_messages(request.messages))
            )
            return response.content if hasattr(response, "content") else str(response)

        return await with_retry_and_circuit_breaker(_invoke, self.circuit_breaker)


class AnthropicProvider(LLMProvider):
    name = "anthropic"
    default_model = "claude-3-5-sonnet-latest"
    estimated_cost_per_1k_tokens = 0.006

    def __init__(self, api_key: str, default_model: Optional[str] = None) -> None:
        super().__init__()
        self.api_key = api_key
        if default_model:
            self.default_model = default_model

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate(self, request: LLMGenerateRequest) -> str:
        from langchain_anthropic import ChatAnthropic

        model_name = request.model or self.default_model
        client = ChatAnthropic(
            anthropic_api_key=self.api_key,
            model_name=model_name,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )

        async def _invoke() -> str:
            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: client.invoke(_to_langchain_messages(request.messages))
            )
            return response.content if hasattr(response, "content") else str(response)

        return await with_retry_and_circuit_breaker(_invoke, self.circuit_breaker)


class GroqLlamaProvider(LLMProvider):
    name = "groq"
    default_model = "llama-3.3-70b-versatile"
    estimated_cost_per_1k_tokens = 0.0015

    def __init__(self, api_key: str, default_model: Optional[str] = None) -> None:
        super().__init__()
        self.api_key = api_key
        if default_model:
            self.default_model = default_model

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate(self, request: LLMGenerateRequest) -> str:
        from langchain_groq import ChatGroq

        model_name = request.model or self.default_model
        client = ChatGroq(
            groq_api_key=self.api_key,
            model_name=model_name,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )

        async def _invoke() -> str:
            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: client.invoke(_to_langchain_messages(request.messages))
            )
            return response.content if hasattr(response, "content") else str(response)

        return await with_retry_and_circuit_breaker(_invoke, self.circuit_breaker)


class DemoProvider(LLMProvider):
    """Offline, zero-cost provider for demos/screenshots/tests.

    Never auto-selected by the "auto" cost router — only used when a user or
    test explicitly requests provider="demo" — so real vs. synthetic content
    is never ambiguous.
    """
    name = "demo"
    default_model = "demo-stub-v1"
    estimated_cost_per_1k_tokens = 0.0

    def __init__(self) -> None:
        super().__init__()

    def is_configured(self) -> bool:
        return True

    async def generate(self, request: LLMGenerateRequest) -> str:
        last_user_msg = next(
            (m.content for m in reversed(request.messages) if m.role.lower() == "user"), ""
        )
        topic = last_user_msg.strip().splitlines()[0][:120] if last_user_msg.strip() else "this section"
        return (
            f"This is placeholder content generated by Demo Mode for: \"{topic}\".\n\n"
            "Demo Mode returns deterministic, illustrative text instantly and at no cost, "
            "so the full workflow (upload -> process -> generate -> export) can be "
            "demonstrated end-to-end without a live LLM API key. Configure a real "
            "provider (OpenAI, Anthropic, or Groq) in Settings to generate content "
            "grounded in your uploaded documents."
        )


class LLMGateway:
    """Routes generation requests to the requested or cheapest configured provider."""

    def __init__(self, providers: Dict[str, LLMProvider]) -> None:
        self.providers = providers

    @classmethod
    def from_config(cls, cfg: Dict[str, Any]) -> "LLMGateway":
        llm_api_key = cfg.get("llm_api_key", "")

        provider_map: Dict[str, LLMProvider] = {
            "openai": OpenAIProvider(
                api_key=cfg.get("openai_api_key") or llm_api_key,
                default_model=cfg.get("openai_model") or cfg.get("llm_model"),
            ),
            "anthropic": AnthropicProvider(
                api_key=cfg.get("anthropic_api_key") or llm_api_key,
                default_model=cfg.get("anthropic_model") or cfg.get("llm_model"),
            ),
            "groq": GroqLlamaProvider(
                api_key=cfg.get("groq_api_key") or llm_api_key,
                default_model=cfg.get("groq_model") or cfg.get("llm_model"),
            ),
            "demo": DemoProvider(),
        }
        return cls(provider_map)

    async def generate(self, request: LLMGenerateRequest) -> str:
        provider = self._select_provider(request.provider)
        return await provider.generate(request)

    def _select_provider(self, requested_provider: str) -> LLMProvider:
        normalized = (requested_provider or "auto").lower().strip()

        if normalized != "auto":
            provider = self.providers.get(normalized)
            if not provider:
                raise ValueError(f"Unsupported provider: {normalized}")
            if not provider.is_configured():
                raise ValueError(f"Provider not configured: {normalized}")
            return provider

        configured = [
            p for p in self.providers.values() if p.name != "demo" and p.is_configured()
        ]
        if not configured:
            raise ValueError("No LLM providers are configured")

        configured.sort(key=lambda p: p.estimated_cost_per_1k_tokens)
        return configured[0]


def _to_langchain_messages(messages: Sequence[GatewayMessage]) -> List[Any]:
    mapped: List[Any] = []
    for msg in messages:
        role = msg.role.lower().strip()
        if role == "system":
            mapped.append(SystemMessage(content=msg.content))
        elif role == "assistant":
            mapped.append(AIMessage(content=msg.content))
        else:
            mapped.append(HumanMessage(content=msg.content))
    return mapped
