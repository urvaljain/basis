"""LLM provider abstraction, with a genuinely useful no-model mode.

## The design decision this file encodes

Basis has two modes, and the distinction is architectural rather than a graceful-degradation
afterthought:

**Extractive mode (no model).** Every claim is a verbatim passage from the corpus with its
page and character span. The system composes, orders and qualifies evidence but writes no
prose of its own about what the regulation says. It is incapable of hallucinating, because it
never generates a claim — it only selects and cites one.

**Generative mode (model available).** The same retrieval, the same epistemic types, the same
critic. The model adds synthesis: phrasing an answer, relating clauses, drafting the
conflict narrative. Everything it produces is still checked against retrieved evidence, and
anything unsupported is demoted by the critic.

The ordering matters and it is not an accident of having no API key. **The guarantees live in
the deterministic layer.** Passage-level provenance, blind-spot reporting, table-structure
warnings, epistemic typing and critic demotion all work with no model at all. The model
improves readability; it is not what makes the output trustworthy.

That is the opposite of the usual arrangement, where an LLM produces the answer and a
retrieval layer is bolted on to justify it after the fact. A product arguing that users should
be able to verify AI claims should be able to state precisely which parts stop working when
the model is removed. Here: the prose gets worse, and nothing else changes.

## Everything is logged

Every call records model, tokens, latency and cost. Those numbers feed the evaluation
harness, and a cost figure nobody measured is exactly the kind of fabricated metric this
project refuses to display.
"""

from __future__ import annotations

import json
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class LLMMode(str, Enum):
    EXTRACTIVE = "extractive"
    """No model. Claims are verbatim passages. Cannot hallucinate."""

    GENERATIVE = "generative"
    """Model available. Synthesis permitted, subject to the critic."""


@dataclass
class LLMUsage:
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    estimated_cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class LLMResponse:
    text: str
    usage: LLMUsage
    ok: bool = True
    error: str | None = None
    raw: Any = None
    called_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def as_json(self) -> Any | None:
        """Parse the response as JSON, tolerating fenced code blocks.

        Returns None rather than raising: a schema failure is a condition the caller handles
        with a repair pass, not an exception that aborts an analysis.
        """
        body = self.text.strip()
        if body.startswith("```"):
            body = body.split("```")[1] if "```" in body[3:] else body[3:]
            if body.lstrip().startswith("json"):
                body = body.lstrip()[4:]
        try:
            return json.loads(body.strip())
        except json.JSONDecodeError:
            start, end = body.find("{"), body.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(body[start : end + 1])
                except json.JSONDecodeError:
                    return None
            return None


class LLMProvider(ABC):
    """A chat-completion backend."""

    name: str
    model: str

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.0,
    ) -> LLMResponse: ...

    @property
    def available(self) -> bool:
        return True


class NullLLM(LLMProvider):
    """The no-model backend.

    Returns an explicit refusal rather than a plausible string. Every caller must therefore
    handle the extractive path deliberately; there is no way to accidentally treat an empty
    completion as an answer.
    """

    name = "null"
    model = "none"

    @property
    def available(self) -> bool:
        return False

    async def complete(self, prompt: str, **kwargs: Any) -> LLMResponse:
        return LLMResponse(
            text="",
            usage=LLMUsage(model="none"),
            ok=False,
            error=(
                "No language model is configured. Basis is running in extractive mode: "
                "claims are verbatim passages with citations, and no prose is generated."
            ),
        )


# Published per-million-token prices, used for cost estimation. Out-of-date entries produce
# a wrong cost, so an unknown model estimates 0.0 and the UI reports cost as unavailable
# rather than inventing a number.
_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-5": (15.0, 75.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
}


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    prices = _PRICING.get(model)
    if not prices:
        return 0.0
    in_price, out_price = prices
    return round(
        (prompt_tokens / 1_000_000) * in_price + (completion_tokens / 1_000_000) * out_price,
        6,
    )


class AnthropicLLM(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str = "claude-sonnet-5") -> None:
        self.api_key = api_key
        self.model = model

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.0,
    ) -> LLMResponse:
        import httpx

        from app.providers.base import _ssl_context

        started = time.monotonic()
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system

        try:
            async with httpx.AsyncClient(timeout=120.0, verify=_ssl_context()) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json=body,
                )
                response.raise_for_status()
                payload = response.json()

            text = "".join(
                block.get("text", "") for block in payload.get("content", [])
            )
            usage_block = payload.get("usage", {})
            prompt_tokens = usage_block.get("input_tokens", 0)
            completion_tokens = usage_block.get("output_tokens", 0)

            return LLMResponse(
                text=text,
                usage=LLMUsage(
                    model=self.model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    latency_ms=int((time.monotonic() - started) * 1000),
                    estimated_cost_usd=_estimate_cost(
                        self.model, prompt_tokens, completion_tokens
                    ),
                ),
                raw=payload,
            )
        except Exception as e:  # noqa: BLE001 - surfaced as a result, never raised
            logger.exception("Anthropic call failed")
            return LLMResponse(
                text="",
                usage=LLMUsage(
                    model=self.model, latency_ms=int((time.monotonic() - started) * 1000)
                ),
                ok=False,
                error=f"{type(e).__name__}: {str(e)[:200]}",
            )


class OpenAILLM(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o") -> None:
        self.api_key = api_key
        self.model = model

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.0,
    ) -> LLMResponse:
        import httpx

        from app.providers.base import _ssl_context

        started = time.monotonic()
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            async with httpx.AsyncClient(timeout=120.0, verify=_ssl_context()) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    },
                )
                response.raise_for_status()
                payload = response.json()

            text = payload["choices"][0]["message"]["content"]
            usage_block = payload.get("usage", {})
            prompt_tokens = usage_block.get("prompt_tokens", 0)
            completion_tokens = usage_block.get("completion_tokens", 0)

            return LLMResponse(
                text=text,
                usage=LLMUsage(
                    model=self.model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    latency_ms=int((time.monotonic() - started) * 1000),
                    estimated_cost_usd=_estimate_cost(
                        self.model, prompt_tokens, completion_tokens
                    ),
                ),
                raw=payload,
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("OpenAI call failed")
            return LLMResponse(
                text="",
                usage=LLMUsage(
                    model=self.model, latency_ms=int((time.monotonic() - started) * 1000)
                ),
                ok=False,
                error=f"{type(e).__name__}: {str(e)[:200]}",
            )


def get_llm() -> LLMProvider:
    """Resolve a provider from the environment, falling back to extractive mode.

    Resolution order is Anthropic, then OpenAI, then :class:`NullLLM`. The fallback is
    silent by design: extractive mode is a supported way to run the product, not a broken
    state, and the interface labels which mode produced any given output.
    """
    if key := os.getenv("ANTHROPIC_API_KEY"):
        return AnthropicLLM(key, os.getenv("BASIS_MODEL", "claude-sonnet-5"))
    if key := os.getenv("OPENAI_API_KEY"):
        return OpenAILLM(key, os.getenv("BASIS_MODEL", "gpt-4o"))
    logger.info("no LLM key configured — running in extractive mode")
    return NullLLM()


def current_mode(provider: LLMProvider | None = None) -> LLMMode:
    provider = provider or get_llm()
    return LLMMode.GENERATIVE if provider.available else LLMMode.EXTRACTIVE
