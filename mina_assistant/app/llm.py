from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, AsyncIterator

import httpx

from mina_assistant.app.config import Settings


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str
    provider: str = "ollama"
    prompt_eval_count: int | None = None
    eval_count: int | None = None


@dataclass(frozen=True)
class LLMStreamChunk:
    content: str
    model: str
    provider: str = "ollama"
    done: bool = False
    prompt_eval_count: int | None = None
    eval_count: int | None = None


@dataclass(frozen=True)
class LLMProviderStatus:
    name: str
    label: str
    available: bool
    default_model: str
    models: list[str]
    requires_api_key: bool = False
    detail: str | None = None


class LLMError(RuntimeError):
    pass


class LLMService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.ollama = OllamaClient(
            base_url=settings.ollama_base_url,
            model=settings.ollama_chat_model,
            timeout_seconds=settings.request_timeout_seconds,
        )
        self.openai = OpenAIClient(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.openai_chat_model,
            timeout_seconds=settings.request_timeout_seconds,
        )
        self.openrouter = OpenRouterClient(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            model=settings.openrouter_chat_model,
            app_title=settings.openrouter_app_title,
            referer=settings.openrouter_referer,
            timeout_seconds=settings.request_timeout_seconds,
        )
        self.anthropic = AnthropicClient(
            api_key=settings.anthropic_api_key,
            base_url=settings.anthropic_base_url,
            model=settings.anthropic_chat_model,
            max_tokens=settings.anthropic_max_tokens,
            timeout_seconds=settings.request_timeout_seconds,
        )

    def default_provider(self) -> str:
        return _normalize_provider(self.settings.llm_provider)

    def default_model(self, provider: str | None = None) -> str:
        active_provider = _normalize_provider(provider or self.default_provider())
        if active_provider == "ollama":
            return self.settings.ollama_chat_model
        if active_provider == "openai":
            return self.settings.openai_chat_model
        if active_provider == "openrouter":
            return self.settings.openrouter_chat_model
        if active_provider == "anthropic":
            return self.settings.anthropic_chat_model
        raise LLMError(f"Unsupported LLM provider: {active_provider}")

    async def provider_statuses(self) -> list[LLMProviderStatus]:
        statuses: list[LLMProviderStatus] = []

        ollama_models: list[str] = []
        ollama_available = False
        ollama_detail: str | None = None
        try:
            tags = await self.ollama.health()
            ollama_models = [
                model.get("name", "")
                for model in tags.get("models", [])
                if model.get("name")
            ]
            ollama_available = True
        except LLMError as exc:
            ollama_detail = str(exc)

        statuses.append(
            LLMProviderStatus(
                name="ollama",
                label="Ollama",
                available=ollama_available,
                default_model=self.settings.ollama_chat_model,
                models=ollama_models or [self.settings.ollama_chat_model],
                detail=ollama_detail,
            )
        )
        statuses.append(
            LLMProviderStatus(
                name="openai",
                label="OpenAI",
                available=bool(self.settings.openai_api_key),
                default_model=self.settings.openai_chat_model,
                models=[self.settings.openai_chat_model],
                requires_api_key=True,
                detail=None if self.settings.openai_api_key else "Set MINA_OPENAI_API_KEY in .env.",
            )
        )
        statuses.append(
            LLMProviderStatus(
                name="openrouter",
                label="OpenRouter",
                available=bool(self.settings.openrouter_api_key),
                default_model=self.settings.openrouter_chat_model,
                models=_unique_models([self.settings.openrouter_chat_model, *self.settings.openrouter_models]),
                requires_api_key=True,
                detail=(
                    None
                    if self.settings.openrouter_api_key
                    else "Set MINA_OPENROUTER_API_KEY in .env."
                ),
            )
        )
        statuses.append(
            LLMProviderStatus(
                name="anthropic",
                label="Anthropic",
                available=bool(self.settings.anthropic_api_key),
                default_model=self.settings.anthropic_chat_model,
                models=[self.settings.anthropic_chat_model],
                requires_api_key=True,
                detail=(
                    None
                    if self.settings.anthropic_api_key
                    else "Set MINA_ANTHROPIC_API_KEY in .env."
                ),
            )
        )
        return statuses

    async def health(self) -> dict[str, Any]:
        return await self.ollama.health()

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.4,
    ) -> LLMResponse:
        client = self._client(provider)
        return await client.chat(messages, model=model, temperature=temperature)

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        *,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.4,
    ) -> AsyncIterator[LLMStreamChunk]:
        client = self._client(provider)
        async for chunk in client.chat_stream(messages, model=model, temperature=temperature):
            yield chunk

    def _client(self, provider: str | None) -> Any:
        active_provider = _normalize_provider(provider or self.default_provider())
        if active_provider == "ollama":
            return self.ollama
        if active_provider == "openai":
            return self.openai
        if active_provider == "openrouter":
            return self.openrouter
        if active_provider == "anthropic":
            return self.anthropic
        raise LLMError(f"Unsupported LLM provider: {active_provider}")


class OllamaClient:
    provider = "ollama"

    def __init__(self, base_url: str, model: str, timeout_seconds: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def health(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            raise LLMError(f"Ollama is not available at {self.base_url}: {exc}") from exc

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.4,
    ) -> LLMResponse:
        active_model = model or self.model
        payload: dict[str, Any] = {
            "model": active_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise LLMError(f"Could not complete the Ollama request: {exc}") from exc

        message = data.get("message") or {}
        content = (message.get("content") or "").strip()
        if not content:
            raise LLMError("Ollama returned an empty response.")

        return LLMResponse(
            content=content,
            model=data.get("model") or active_model,
            provider=self.provider,
            prompt_eval_count=data.get("prompt_eval_count"),
            eval_count=data.get("eval_count"),
        )

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.4,
    ) -> AsyncIterator[LLMStreamChunk]:
        active_model = model or self.model
        payload: dict[str, Any] = {
            "model": active_model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError as exc:
                            raise LLMError(f"Ollama returned an invalid chunk: {line}") from exc

                        if data.get("error"):
                            raise LLMError(str(data["error"]))

                        message = data.get("message") or {}
                        yield LLMStreamChunk(
                            content=message.get("content") or "",
                            model=data.get("model") or active_model,
                            provider=self.provider,
                            done=bool(data.get("done")),
                            prompt_eval_count=data.get("prompt_eval_count"),
                            eval_count=data.get("eval_count"),
                        )
        except httpx.HTTPError as exc:
            raise LLMError(f"Could not complete the Ollama stream: {exc}") from exc


class OpenAIClient:
    provider = "openai"

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        model: str,
        timeout_seconds: float,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.4,
    ) -> LLMResponse:
        active_model = model or self.model
        payload: dict[str, Any] = {
            "model": active_model,
            "messages": messages,
            "stream": False,
            **openai_request_options(self.base_url),
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            raise LLMError(f"{self._provider_label()} returned an error: {_response_error(exc.response)}") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"Could not complete the {self._provider_label()} request: {exc}") from exc

        choices = data.get("choices") or []
        message = choices[0].get("message") if choices else {}
        content = _openai_content_to_text((message or {}).get("content")).strip()
        if not content:
            raise LLMError(f"{self._provider_label()} returned an empty response.")

        usage = data.get("usage") or {}
        return LLMResponse(
            content=content,
            model=data.get("model") or active_model,
            provider=self.provider,
            prompt_eval_count=usage.get("prompt_tokens"),
            eval_count=usage.get("completion_tokens"),
        )

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.4,
    ) -> AsyncIterator[LLMStreamChunk]:
        active_model = model or self.model
        payload: dict[str, Any] = {
            "model": active_model,
            "messages": messages,
            "stream": True,
            **openai_request_options(self.base_url),
            "stream_options": {"include_usage": True},
        }

        prompt_tokens: int | None = None
        completion_tokens: int | None = None

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                ) as response:
                    if response.is_error:
                        await response.aread()
                    response.raise_for_status()
                    async for data in _iter_sse_json(response):
                        if data == "[DONE]":
                            yield LLMStreamChunk(
                                content="",
                                model=active_model,
                                provider=self.provider,
                                done=True,
                                prompt_eval_count=prompt_tokens,
                                eval_count=completion_tokens,
                            )
                            return

                        usage = data.get("usage") or {}
                        prompt_tokens = usage.get("prompt_tokens", prompt_tokens)
                        completion_tokens = usage.get("completion_tokens", completion_tokens)

                        choices = data.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        content = _openai_content_to_text(delta.get("content"))
                        yield LLMStreamChunk(
                            content=content,
                            model=data.get("model") or active_model,
                            provider=self.provider,
                            done=False,
                            prompt_eval_count=prompt_tokens,
                            eval_count=completion_tokens,
                        )
        except httpx.HTTPStatusError as exc:
            raise LLMError(f"{self._provider_label()} returned an error: {_response_error(exc.response)}") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"Could not complete the {self._provider_label()} stream: {exc}") from exc

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise LLMError("OpenAI API key is not configured. Set MINA_OPENAI_API_KEY in .env.")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _provider_label(self) -> str:
        return "OpenAI"


class OpenRouterClient(OpenAIClient):
    provider = "openrouter"

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        model: str,
        app_title: str,
        referer: str | None,
        timeout_seconds: float,
    ):
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout_seconds=timeout_seconds,
        )
        self.app_title = app_title
        self.referer = referer

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise LLMError("OpenRouter API key is not configured. Set MINA_OPENROUTER_API_KEY in .env.")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-OpenRouter-Title": self.app_title,
        }
        if self.referer:
            headers["HTTP-Referer"] = self.referer
        return headers

    def _provider_label(self) -> str:
        return "OpenRouter"


class AnthropicClient:
    provider = "anthropic"

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        model: str,
        max_tokens: int,
        timeout_seconds: float,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.4,
    ) -> LLMResponse:
        active_model = model or self.model
        payload = self._payload(messages, active_model, stream=False)

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/v1/messages",
                    headers=self._headers(),
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            raise LLMError(f"Anthropic returned an error: {_response_error(exc.response)}") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"Could not complete the Anthropic request: {exc}") from exc

        content = _anthropic_content_to_text(data.get("content") or []).strip()
        if not content:
            raise LLMError("Anthropic returned an empty response.")

        usage = data.get("usage") or {}
        return LLMResponse(
            content=content,
            model=data.get("model") or active_model,
            provider=self.provider,
            prompt_eval_count=usage.get("input_tokens"),
            eval_count=usage.get("output_tokens"),
        )

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.4,
    ) -> AsyncIterator[LLMStreamChunk]:
        active_model = model or self.model
        payload = self._payload(messages, active_model, stream=True)
        input_tokens: int | None = None
        output_tokens: int | None = None

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/v1/messages",
                    headers=self._headers(),
                    json=payload,
                ) as response:
                    if response.is_error:
                        await response.aread()
                    response.raise_for_status()
                    async for data in _iter_sse_json(response):
                        event_type = data.get("type")
                        if event_type == "message_start":
                            message = data.get("message") or {}
                            usage = message.get("usage") or {}
                            input_tokens = usage.get("input_tokens", input_tokens)
                            continue

                        if event_type == "content_block_delta":
                            delta = data.get("delta") or {}
                            text = delta.get("text") if delta.get("type") == "text_delta" else ""
                            yield LLMStreamChunk(
                                content=text or "",
                                model=active_model,
                                provider=self.provider,
                                prompt_eval_count=input_tokens,
                                eval_count=output_tokens,
                            )
                            continue

                        if event_type == "message_delta":
                            usage = data.get("usage") or {}
                            output_tokens = usage.get("output_tokens", output_tokens)
                            continue

                        if event_type == "message_stop":
                            yield LLMStreamChunk(
                                content="",
                                model=active_model,
                                provider=self.provider,
                                done=True,
                                prompt_eval_count=input_tokens,
                                eval_count=output_tokens,
                            )
                            return

                        if event_type == "error":
                            error = data.get("error") or {}
                            raise LLMError(str(error.get("message") or error or data))
        except httpx.HTTPStatusError as exc:
            raise LLMError(f"Anthropic returned an error: {_response_error(exc.response)}") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"Could not complete the Anthropic stream: {exc}") from exc

    def _payload(self, messages: list[dict[str, str]], active_model: str, *, stream: bool) -> dict[str, Any]:
        system_messages = [message["content"] for message in messages if message.get("role") == "system"]
        conversation = [
            {"role": message["role"], "content": message["content"]}
            for message in messages
            if message.get("role") in {"user", "assistant"}
        ]
        payload: dict[str, Any] = {
            "model": active_model,
            "max_tokens": self.max_tokens,
            "messages": conversation,
            "stream": stream,
        }
        if system_messages:
            payload["system"] = "\n\n".join(system_messages)
        return payload

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise LLMError(
                "Anthropic API key is not configured. Set MINA_ANTHROPIC_API_KEY in .env."
            )
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }


async def _iter_sse_json(response: httpx.Response) -> AsyncIterator[Any]:
    async for line in response.aiter_lines():
        if not line or not line.startswith("data:"):
            continue
        data = line.removeprefix("data:").strip()
        if data == "[DONE]":
            yield "[DONE]"
            continue
        try:
            yield json.loads(data)
        except json.JSONDecodeError as exc:
            raise LLMError(f"Provider returned an invalid streaming chunk: {data}") from exc


def _normalize_provider(provider: str) -> str:
    return provider.strip().lower()


def _unique_models(models: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for model in models:
        cleaned = str(model or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _openai_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") in {"text", "output_text"}:
                parts.append(str(item.get("text") or ""))
        return "".join(parts)
    return ""


def _anthropic_content_to_text(content: list[Any]) -> str:
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text") or ""))
    return "".join(parts)


def openai_request_options(base_url: str) -> dict[str, Any]:
    """Keep OpenAI storage settings out of Google's compatibility requests."""
    if httpx.URL(base_url).host == "generativelanguage.googleapis.com":
        return {}
    return {"store": False}


def _response_error(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return f"{response.status_code} {response.text[:500]}"

    if isinstance(data, list) and len(data) == 1:
        data = data[0]
    error = data.get("error") if isinstance(data, dict) else None
    if isinstance(error, dict):
        return f"{response.status_code} {error.get('message') or error}"
    return f"{response.status_code} {data}"
