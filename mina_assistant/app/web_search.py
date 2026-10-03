from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from mina_assistant.app.config import Settings


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str | None
    source: str


@dataclass(frozen=True)
class WebSearchResponse:
    query: str
    provider: str
    results: list[WebSearchResult]


@dataclass(frozen=True)
class WebImageResult:
    title: str
    url: str
    image_url: str
    thumbnail_url: str | None
    source: str


@dataclass(frozen=True)
class WebImageSearchResponse:
    query: str
    provider: str
    images: list[WebImageResult]


class WebSearchError(RuntimeError):
    pass


class WebSearchService:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def search(
        self,
        query: str,
        *,
        provider: str | None = None,
        limit: int | None = None,
    ) -> WebSearchResponse:
        cleaned_query = query.strip()
        if not cleaned_query:
            raise WebSearchError("Search query cannot be empty.")
        max_results = max(1, min(limit or self.settings.web_search_max_results, 10))
        active_provider = (provider or self.settings.web_search_provider or "duckduckgo").strip().lower()

        if active_provider == "brave":
            if not self.settings.brave_search_api_key:
                raise WebSearchError("Brave Search API key is not configured. Set MINA_BRAVE_SEARCH_API_KEY in .env.")
            return await self._brave_search(cleaned_query, max_results)
        if active_provider == "duckduckgo":
            return await self._duckduckgo_search(cleaned_query, max_results)
        raise WebSearchError(f"Unsupported web search provider: {active_provider}")

    async def image_search(
        self,
        query: str,
        *,
        provider: str | None = None,
        limit: int | None = None,
    ) -> WebImageSearchResponse:
        cleaned_query = query.strip()
        if not cleaned_query:
            raise WebSearchError("Image search query cannot be empty.")
        max_results = max(1, min(limit or 4, 8))
        active_provider = (provider or self.settings.web_search_provider or "duckduckgo").strip().lower()

        if active_provider == "brave":
            if not self.settings.brave_search_api_key:
                raise WebSearchError("Brave Search API key is not configured. Set MINA_BRAVE_SEARCH_API_KEY in .env.")
            return await self._brave_image_search(cleaned_query, max_results)
        if active_provider == "duckduckgo":
            return await self._duckduckgo_image_search(cleaned_query, max_results)
        raise WebSearchError(f"Unsupported image search provider: {active_provider}")

    async def _brave_search(self, query: str, limit: int) -> WebSearchResponse:
        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
                response = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": query, "count": limit},
                    headers={"X-Subscription-Token": self.settings.brave_search_api_key or ""},
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            raise WebSearchError(f"Brave Search returned an error: {_response_error(exc.response)}") from exc
        except httpx.HTTPError as exc:
            raise WebSearchError(f"Could not complete Brave Search request: {exc}") from exc

        raw_results = ((data.get("web") or {}).get("results") or [])[:limit]
        results = [
            WebSearchResult(
                title=_clean_text(item.get("title")),
                url=str(item.get("url") or ""),
                snippet=_clean_text(item.get("description")) or None,
                source="brave",
            )
            for item in raw_results
            if item.get("title") and item.get("url")
        ]
        return WebSearchResponse(query=query, provider="brave", results=results)

    async def _brave_image_search(self, query: str, limit: int) -> WebImageSearchResponse:
        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
                response = await client.get(
                    "https://api.search.brave.com/res/v1/images/search",
                    params={"q": query, "count": limit},
                    headers={"X-Subscription-Token": self.settings.brave_search_api_key or ""},
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            raise WebSearchError(f"Brave Image Search returned an error: {_response_error(exc.response)}") from exc
        except httpx.HTTPError as exc:
            raise WebSearchError(f"Could not complete Brave Image Search request: {exc}") from exc

        images: list[WebImageResult] = []
        for item in (data.get("results") or [])[:limit]:
            thumbnail = item.get("thumbnail") or {}
            properties = item.get("properties") or {}
            image_url = str(properties.get("url") or thumbnail.get("src") or "")
            page_url = str(item.get("url") or image_url)
            title = _clean_text(item.get("title")) or page_url
            if not image_url or not page_url:
                continue
            images.append(
                WebImageResult(
                    title=title,
                    url=page_url,
                    image_url=image_url,
                    thumbnail_url=str(thumbnail.get("src") or image_url),
                    source="brave",
                )
            )
        return WebImageSearchResponse(query=query, provider="brave", images=images)

    async def _duckduckgo_search(self, query: str, limit: int) -> WebSearchResponse:
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.request_timeout_seconds,
                headers={"User-Agent": "Mina Desktop/0.1"},
                follow_redirects=True,
            ) as client:
                response = await client.get("https://html.duckduckgo.com/html/", params={"q": query})
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise WebSearchError(f"DuckDuckGo returned an error: {_response_error(exc.response)}") from exc
        except httpx.HTTPError as exc:
            raise WebSearchError(f"Could not complete DuckDuckGo request: {exc}") from exc

        parser = DuckDuckGoHTMLParser(limit=limit)
        parser.feed(response.text)
        return WebSearchResponse(query=query, provider="duckduckgo", results=parser.results)

    async def _duckduckgo_image_search(self, query: str, limit: int) -> WebImageSearchResponse:
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.request_timeout_seconds,
                headers={"User-Agent": "Mina Desktop/0.1"},
                follow_redirects=True,
            ) as client:
                page = await client.get("https://duckduckgo.com/", params={"q": query})
                page.raise_for_status()
                vqd = _duckduckgo_vqd(page.text)
                if not vqd:
                    raise WebSearchError("DuckDuckGo image token was not found.")
                response = await client.get(
                    "https://duckduckgo.com/i.js",
                    params={"q": query, "vqd": vqd, "o": "json", "p": "1", "l": "wt-wt"},
                )
                response.raise_for_status()
                data = response.json()
        except WebSearchError:
            raise
        except httpx.HTTPStatusError as exc:
            raise WebSearchError(f"DuckDuckGo Image Search returned an error: {_response_error(exc.response)}") from exc
        except httpx.HTTPError as exc:
            raise WebSearchError(f"Could not complete DuckDuckGo Image Search request: {exc}") from exc
        except ValueError as exc:
            raise WebSearchError(f"DuckDuckGo Image Search returned invalid JSON: {exc}") from exc

        images: list[WebImageResult] = []
        for item in (data.get("results") or [])[:limit]:
            image_url = str(item.get("image") or "")
            page_url = str(item.get("url") or image_url)
            title = _clean_text(item.get("title")) or page_url
            if not image_url or not page_url:
                continue
            images.append(
                WebImageResult(
                    title=title,
                    url=page_url,
                    image_url=image_url,
                    thumbnail_url=str(item.get("thumbnail") or image_url),
                    source="duckduckgo",
                )
            )
        return WebImageSearchResponse(query=query, provider="duckduckgo", images=images)


class DuckDuckGoHTMLParser(HTMLParser):
    def __init__(self, *, limit: int):
        super().__init__()
        self.limit = limit
        self.results: list[WebSearchResult] = []
        self._current: dict[str, str] | None = None
        self._capture: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}
        classes = set(attrs_dict.get("class", "").split())
        if tag == "a" and "result__a" in classes:
            self._current = {
                "title": "",
                "url": _clean_duckduckgo_url(attrs_dict.get("href", "")),
                "snippet": "",
            }
            self._capture = "title"
            return
        if self._current is not None and tag in {"a", "div"} and "result__snippet" in classes:
            self._capture = "snippet"

    def handle_data(self, data: str) -> None:
        if self._current is None or self._capture is None:
            return
        self._current[self._capture] += data

    def handle_endtag(self, tag: str) -> None:
        if self._current is None:
            return
        if tag == "a" and self._capture == "title":
            self._capture = None
            return
        if tag in {"a", "div"} and self._capture == "snippet":
            self._capture = None
            self._flush_current()

    def _flush_current(self) -> None:
        if self._current is None or len(self.results) >= self.limit:
            self._current = None
            return
        title = _clean_text(self._current.get("title"))
        url = self._current.get("url", "").strip()
        snippet = _clean_text(self._current.get("snippet")) or None
        if title and url:
            self.results.append(WebSearchResult(title=title, url=url, snippet=snippet, source="duckduckgo"))
        self._current = None
        self._capture = None


def _clean_duckduckgo_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.path == "/l/":
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        if target:
            return unquote(target)
    return value


def _duckduckgo_vqd(html: str) -> str | None:
    patterns = [
        r'vqd="([^"]+)"',
        r"vqd='([^']+)'",
        r"vqd=([\d-]+)&",
        r"vqd\\x3d([\d-]+)\\x26",
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return match.group(1)
    return None


def _clean_text(value: Any) -> str:
    return " ".join(unescape(str(value or "")).split())


def _response_error(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return f"{response.status_code} {response.text[:500]}"
    return f"{response.status_code} {data}"
