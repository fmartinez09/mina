from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from mina_assistant.app.config import Settings
from mina_assistant.app.llm import openai_request_options


LANGUAGE_GUARD = """Language rule: answer only in Spanish or English. Prefer Spanish when the user's prompt is Spanish or unclear. Never answer in Chinese."""

DEFAULT_VISION_PROMPT = """Analyze this image for Mina, a personal fashion assistant.
Focus on:
- what is visible
- garment/product attributes
- colors, materials, silhouette, pattern, condition
- styling suggestions and outfit compatibility
- uncertainties or details that cannot be confirmed
Do not claim this is owned by the user unless the image is attached to a wardrobe item."""

DEFAULT_COMPARISON_PROMPT = """Compare these images for Mina, a personal fashion assistant.
Return concise Markdown.
Focus on:
- similarities and differences
- which pieces work better for the user's wardrobe and style
- color, silhouette, material and occasion compatibility
- outfit ideas using the visible pieces
- uncertainties or details that cannot be confirmed."""


@dataclass(frozen=True)
class VisionResult:
    analysis: str
    provider: str
    model: str


@dataclass(frozen=True)
class VisionProviderStatus:
    name: str
    label: str
    available: bool
    default_model: str
    models: list[str]
    requires_api_key: bool = False
    detail: str | None = None


class VisionError(RuntimeError):
    pass


class VisionService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.ollama = OllamaVisionClient(
            base_url=settings.ollama_base_url,
            model=settings.ollama_vision_model,
            timeout_seconds=settings.request_timeout_seconds,
        )
        self.openai = OpenAIVisionClient(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.openai_vision_model,
            timeout_seconds=settings.request_timeout_seconds,
        )
        self.openrouter = OpenRouterVisionClient(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            model=settings.openrouter_vision_model,
            app_title=settings.openrouter_app_title,
            referer=settings.openrouter_referer,
            timeout_seconds=settings.request_timeout_seconds,
        )

    def default_provider(self) -> str:
        return _normalize_provider(self.settings.vision_provider)

    def default_model(self, provider: str | None = None) -> str:
        active_provider = _normalize_provider(provider or self.default_provider())
        if active_provider == "ollama":
            return self.settings.ollama_vision_model
        if active_provider == "openai":
            return self.settings.openai_vision_model
        if active_provider == "openrouter":
            return self.settings.openrouter_vision_model
        raise VisionError(f"Unsupported vision provider: {active_provider}")

    async def provider_statuses(self) -> list[VisionProviderStatus]:
        statuses: list[VisionProviderStatus] = []
        ollama_available = False
        ollama_detail: str | None = None
        try:
            tags = await self.ollama.health()
            models = [
                model.get("name", "")
                for model in tags.get("models", [])
                if model.get("name")
            ]
            if models and self.settings.ollama_vision_model not in models:
                ollama_detail = f"Ollama is running, but {self.settings.ollama_vision_model} is not pulled."
            else:
                ollama_available = True
        except VisionError as exc:
            ollama_detail = str(exc)

        statuses.append(
            VisionProviderStatus(
                name="ollama",
                label="Ollama Vision",
                available=ollama_available,
                default_model=self.settings.ollama_vision_model,
                models=_unique_models([self.settings.ollama_vision_model]),
                detail=ollama_detail,
            )
        )
        statuses.append(
            VisionProviderStatus(
                name="openai",
                label="OpenAI Vision",
                available=bool(self.settings.openai_api_key),
                default_model=self.settings.openai_vision_model,
                models=_unique_models([self.settings.openai_vision_model]),
                requires_api_key=True,
                detail=None if self.settings.openai_api_key else "Set MINA_OPENAI_API_KEY in .env.",
            )
        )
        statuses.append(
            VisionProviderStatus(
                name="openrouter",
                label="OpenRouter Vision",
                available=bool(self.settings.openrouter_api_key),
                default_model=self.settings.openrouter_vision_model,
                models=_unique_models([self.settings.openrouter_vision_model, *self.settings.openrouter_vision_models]),
                requires_api_key=True,
                detail=(
                    None
                    if self.settings.openrouter_api_key
                    else "Set MINA_OPENROUTER_API_KEY in .env."
                ),
            )
        )
        return statuses

    async def analyze_image(
        self,
        *,
        image_path: Path,
        mime_type: str,
        prompt: str | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> VisionResult:
        payload = image_path.read_bytes()
        if len(payload) > self.settings.vision_max_image_bytes:
            raise VisionError(
                f"Image exceeds configured max size of {self.settings.vision_max_image_bytes} bytes."
            )
        active_provider = _normalize_provider(provider or self.default_provider())
        active_model = model or self.default_model(active_provider)
        active_prompt = _guard_prompt(prompt or DEFAULT_VISION_PROMPT)
        base64_image = base64.b64encode(payload).decode("ascii")

        if active_provider == "ollama":
            return await self.ollama.analyze(base64_image, prompt=active_prompt, model=active_model)
        if active_provider == "openai":
            return await self.openai.analyze(
                base64_image,
                mime_type=mime_type,
                prompt=active_prompt,
                model=active_model,
            )
        if active_provider == "openrouter":
            return await self.openrouter.analyze(
                base64_image,
                mime_type=mime_type,
                prompt=active_prompt,
                model=active_model,
            )
        raise VisionError(f"Unsupported vision provider: {active_provider}")

    async def compare_images(
        self,
        *,
        images: list[dict[str, Any]],
        prompt: str | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> VisionResult:
        if len(images) < 2:
            raise VisionError("At least two images are required for comparison.")
        active_provider = _normalize_provider(provider or self.default_provider())
        active_model = model or self.default_model(active_provider)
        active_prompt = _guard_prompt(prompt or DEFAULT_COMPARISON_PROMPT)
        payloads: list[dict[str, str]] = []
        for image in images:
            path = image["path"]
            raw = path.read_bytes()
            if len(raw) > self.settings.vision_max_image_bytes:
                raise VisionError(
                    f"Image exceeds configured max size of {self.settings.vision_max_image_bytes} bytes."
                )
            payloads.append(
                {
                    "base64_image": base64.b64encode(raw).decode("ascii"),
                    "mime_type": str(image.get("mime_type") or "image/jpeg"),
                    "label": str(image.get("label") or "image"),
                }
            )

        if active_provider == "ollama":
            return await self.ollama.compare(payloads, prompt=active_prompt, model=active_model)
        if active_provider == "openai":
            return await self.openai.compare(payloads, prompt=active_prompt, model=active_model)
        if active_provider == "openrouter":
            return await self.openrouter.compare(payloads, prompt=active_prompt, model=active_model)
        raise VisionError(f"Unsupported vision provider: {active_provider}")


class OllamaVisionClient:
    provider = "ollama"

    def __init__(self, *, base_url: str, model: str, timeout_seconds: float):
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
            raise VisionError(f"Ollama is not available at {self.base_url}: {exc}") from exc

    async def analyze(self, base64_image: str, *, prompt: str, model: str | None = None) -> VisionResult:
        active_model = model or self.model
        payload: dict[str, Any] = {
            "model": active_model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [base64_image],
                }
            ],
            "stream": False,
            "options": {"temperature": 0.2},
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            raise VisionError(f"Ollama Vision returned an error: {_response_error(exc.response)}") from exc
        except httpx.HTTPError as exc:
            raise VisionError(f"Could not complete the Ollama Vision request: {exc}") from exc

        message = data.get("message") or {}
        content = str(message.get("content") or "").strip()
        if not content:
            raise VisionError("Ollama Vision returned an empty response.")
        return VisionResult(analysis=content, provider=self.provider, model=data.get("model") or active_model)

    async def compare(
        self,
        images: list[dict[str, str]],
        *,
        prompt: str,
        model: str | None = None,
    ) -> VisionResult:
        active_model = model or self.model
        labels = "\n".join(f"- Image {index + 1}: {image['label']}" for index, image in enumerate(images))
        payload: dict[str, Any] = {
            "model": active_model,
            "messages": [
                {
                    "role": "user",
                    "content": f"{prompt}\n\nImage labels:\n{labels}",
                    "images": [image["base64_image"] for image in images],
                }
            ],
            "stream": False,
            "options": {"temperature": 0.2},
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            raise VisionError(f"Ollama Vision returned an error: {_response_error(exc.response)}") from exc
        except httpx.HTTPError as exc:
            raise VisionError(f"Could not complete the Ollama Vision request: {exc}") from exc

        message = data.get("message") or {}
        content = str(message.get("content") or "").strip()
        if not content:
            raise VisionError("Ollama Vision returned an empty response.")
        return VisionResult(analysis=content, provider=self.provider, model=data.get("model") or active_model)


class OpenAIVisionClient:
    provider = "openai"

    def __init__(self, *, api_key: str | None, base_url: str, model: str, timeout_seconds: float):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def analyze(
        self,
        base64_image: str,
        *,
        mime_type: str,
        prompt: str,
        model: str | None = None,
    ) -> VisionResult:
        active_model = model or self.model
        payload: dict[str, Any] = {
            "model": active_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}",
                            },
                        },
                    ],
                }
            ],
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
            raise VisionError(f"{self._provider_label()} Vision returned an error: {_response_error(exc.response)}") from exc
        except httpx.HTTPError as exc:
            raise VisionError(f"Could not complete the {self._provider_label()} Vision request: {exc}") from exc

        choices = data.get("choices") or []
        message = choices[0].get("message") if choices else {}
        content = _openai_content_to_text((message or {}).get("content")).strip()
        if not content:
            raise VisionError(f"{self._provider_label()} Vision returned an empty response.")
        return VisionResult(analysis=content, provider=self.provider, model=data.get("model") or active_model)

    async def compare(
        self,
        images: list[dict[str, str]],
        *,
        prompt: str,
        model: str | None = None,
    ) -> VisionResult:
        active_model = model or self.model
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for index, image in enumerate(images):
            content.append({"type": "text", "text": f"Image {index + 1}: {image['label']}"})
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{image['mime_type']};base64,{image['base64_image']}",
                    },
                }
            )

        payload: dict[str, Any] = {
            "model": active_model,
            "messages": [{"role": "user", "content": content}],
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
            raise VisionError(f"{self._provider_label()} Vision returned an error: {_response_error(exc.response)}") from exc
        except httpx.HTTPError as exc:
            raise VisionError(f"Could not complete the {self._provider_label()} Vision request: {exc}") from exc

        choices = data.get("choices") or []
        message = choices[0].get("message") if choices else {}
        response_content = _openai_content_to_text((message or {}).get("content")).strip()
        if not response_content:
            raise VisionError(f"{self._provider_label()} Vision returned an empty response.")
        return VisionResult(analysis=response_content, provider=self.provider, model=data.get("model") or active_model)

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise VisionError("OpenAI API key is not configured. Set MINA_OPENAI_API_KEY in .env.")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _provider_label(self) -> str:
        return "OpenAI"


class OpenRouterVisionClient(OpenAIVisionClient):
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
            raise VisionError("OpenRouter API key is not configured. Set MINA_OPENROUTER_API_KEY in .env.")
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


def _normalize_provider(provider: str) -> str:
    return provider.strip().lower()


def _guard_prompt(prompt: str) -> str:
    cleaned = prompt.strip()
    if LANGUAGE_GUARD.lower() in cleaned.lower():
        return cleaned
    return f"{LANGUAGE_GUARD}\n\n{cleaned}"


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


def _response_error(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return f"{response.status_code} {response.text[:500]}"

    error = data.get("error") if isinstance(data, dict) else None
    if isinstance(error, dict):
        return f"{response.status_code} {error.get('message') or error}"
    return f"{response.status_code} {data}"
