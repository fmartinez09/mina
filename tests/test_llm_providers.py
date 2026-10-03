from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi import WebSocketDisconnect

from mina_assistant.app.llm import AnthropicClient, LLMError, OpenAIClient, OpenRouterClient
from mina_assistant.app.vision import OpenAIVisionClient


GOOGLE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"


class ResponseStream(httpx.AsyncByteStream):
    def __init__(self, body: bytes):
        self.body = body

    async def __aiter__(self):
        yield self.body


def mock_client(handler):
    client_class = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    return lambda **kwargs: client_class(transport=transport, **kwargs)


def text_client(base_url: str):
    options = dict(api_key="test-key", base_url=base_url, model="test-model", timeout_seconds=5)
    if "openrouter.ai" in base_url:
        return OpenRouterClient(**options, app_title="Mina tests", referer=None)
    return OpenAIClient(**options)


class ProviderCompatibilityTest(unittest.IsolatedAsyncioTestCase):
    async def test_websocket_reports_provider_error_and_accepts_retry(self):
        from mina_assistant.app import main

        request_count = 0

        def handler(request):
            nonlocal request_count
            request_count += 1
            if request_count == 1:
                body = json.dumps([{"error": {"message": "Unsupported parameter"}}]).encode()
                return httpx.Response(400, stream=ResponseStream(body))
            event = {"choices": [{"delta": {"content": "Hello"}}]}
            body = ("data: " + json.dumps(event) + "\n\ndata: [DONE]\n\n").encode()
            return httpx.Response(200, stream=ResponseStream(body))

        client = text_client(GOOGLE_URL)

        class TestOrchestrator:
            async def stream_chat(self, content, **kwargs):
                async for chunk in client.chat_stream([{"role": "user", "content": content}]):
                    if chunk.content:
                        yield SimpleNamespace(
                            type="assistant_chunk", session_id="test-session", delta=chunk.content,
                            provider=chunk.provider, model=chunk.model,
                        )

        class TestSocket:
            def __init__(self):
                self.messages = []
                self.requests = iter([{"content": "Hi"}, {"content": "Try again"}])
                self.accepted = False

            async def accept(self):
                self.accepted = True

            async def receive_json(self):
                payload = next(self.requests, None)
                if payload is None:
                    raise WebSocketDisconnect()
                return payload

            async def send_json(self, message):
                self.messages.append(message)

        socket = TestSocket()
        with patch("httpx.AsyncClient", new=mock_client(handler)), patch.object(
            main, "orchestrator", TestOrchestrator(),
        ):
            await main.websocket_chat(socket)

        self.assertTrue(socket.accepted)
        self.assertEqual([message["type"] for message in socket.messages], [
            "status", "error", "status", "assistant_chunk",
        ])
        self.assertIn("400 Unsupported parameter", socket.messages[1]["detail"])
        self.assertEqual(socket.messages[-1]["delta"], "Hello")

    async def test_chat_and_stream_work_with_google_and_existing_providers(self):
        for base_url in (GOOGLE_URL, "https://api.openai.com/v1", "https://openrouter.ai/api/v1"):
            with self.subTest(base_url=base_url):
                requests = []

                def handler(request):
                    payload = json.loads(request.content)
                    requests.append(payload)
                    self.assertEqual(str(request.url), base_url + "/chat/completions")
                    self.assertEqual(request.headers["Authorization"], "Bearer test-key")
                    if payload["stream"]:
                        event = {
                            "choices": [{"delta": {"content": "Hello"}}],
                            "usage": {"prompt_tokens": 7, "completion_tokens": 1},
                        }
                        body = ("data: " + json.dumps(event) + "\n\ndata: [DONE]\n\n").encode()
                        return httpx.Response(200, stream=ResponseStream(body))
                    return httpx.Response(200, json={
                        "choices": [{"message": {"content": "Hello"}}],
                        "usage": {"prompt_tokens": 7, "completion_tokens": 1},
                    })

                client = text_client(base_url)
                with patch("httpx.AsyncClient", new=mock_client(handler)):
                    result = await client.chat([{"role": "user", "content": "Hi"}])
                    chunks = [chunk async for chunk in client.chat_stream([
                        {"role": "user", "content": "Hi"},
                    ])]

                self.assertEqual(result.content, "Hello")
                self.assertEqual("".join(chunk.content for chunk in chunks), "Hello")
                self.assertTrue(chunks[-1].done)
                self.assertEqual(chunks[-1].prompt_eval_count, 7)
                self.assertEqual(chunks[-1].eval_count, 1)
                for payload in requests:
                    if base_url == GOOGLE_URL:
                        self.assertNotIn("store", payload)
                    else:
                        self.assertIs(payload["store"], False)

    async def test_stream_errors_preserve_provider_message(self):
        cases = (
            (400, [{"error": {"message": "Unsupported parameter"}}], "Unsupported parameter"),
            (401, {"error": {"message": "Invalid credentials"}}, "Invalid credentials"),
            (404, {"error": {"message": "Model unavailable"}}, "Model unavailable"),
        )
        for status, error, expected in cases:
            with self.subTest(status=status):
                def handler(request):
                    return httpx.Response(status, stream=ResponseStream(json.dumps(error).encode()))

                with patch("httpx.AsyncClient", new=mock_client(handler)):
                    with self.assertRaisesRegex(LLMError, f"{status} {expected}"):
                        _ = [chunk async for chunk in text_client(GOOGLE_URL).chat_stream([
                            {"role": "user", "content": "Hi"},
                        ])]

    async def test_non_json_stream_errors_are_reported(self):
        def handler(request):
            return httpx.Response(503, stream=ResponseStream(b"Service temporarily unavailable"))

        with patch("httpx.AsyncClient", new=mock_client(handler)):
            with self.assertRaisesRegex(LLMError, "503 Service temporarily unavailable"):
                _ = [chunk async for chunk in text_client(GOOGLE_URL).chat_stream([
                    {"role": "user", "content": "Hi"},
                ])]

    async def test_anthropic_stream_errors_are_reported(self):
        def handler(request):
            body = json.dumps({"error": {"message": "Rate limit exceeded"}}).encode()
            return httpx.Response(429, stream=ResponseStream(body))

        client = AnthropicClient(
            api_key="test-key", base_url="https://api.anthropic.com", model="test-model",
            max_tokens=100, timeout_seconds=5,
        )
        with patch("httpx.AsyncClient", new=mock_client(handler)):
            with self.assertRaisesRegex(LLMError, "429 Rate limit exceeded"):
                _ = [chunk async for chunk in client.chat_stream([{"role": "user", "content": "Hi"}])]

    async def test_google_vision_analysis_and_comparison_omit_storage_option(self):
        for base_url in (GOOGLE_URL, "https://api.openai.com/v1", "https://openrouter.ai/api/v1"):
            with self.subTest(base_url=base_url):
                requests = []

                def handler(request):
                    requests.append(json.loads(request.content))
                    return httpx.Response(200, json={"choices": [{"message": {"content": "A jacket"}}]})

                client = OpenAIVisionClient(
                    api_key="test-key", base_url=base_url, model="test-model", timeout_seconds=5,
                )
                with patch("httpx.AsyncClient", new=mock_client(handler)):
                    analysis = await client.analyze("test-image", mime_type="image/png", prompt="Describe")
                    comparison = await client.compare([
                        {"label": "One", "mime_type": "image/png", "base64_image": "test-image"},
                        {"label": "Two", "mime_type": "image/png", "base64_image": "test-image"},
                    ], prompt="Compare")

                self.assertEqual(analysis.analysis, "A jacket")
                self.assertEqual(comparison.analysis, "A jacket")
                for payload in requests:
                    if base_url == GOOGLE_URL:
                        self.assertNotIn("store", payload)
                    else:
                        self.assertIs(payload["store"], False)


if __name__ == "__main__":
    unittest.main()
