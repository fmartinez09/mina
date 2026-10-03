from __future__ import annotations

import base64
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from mina_assistant.app.config import get_settings
from mina_assistant.app.db import SQLiteStore
from mina_assistant.app.media import MediaError, MediaService
from mina_assistant.app.vision import VisionResult, VisionService


TINY_PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def _test_settings(root: Path):
    settings = get_settings()
    return replace(
        settings,
        data_dir=root,
        database_path=root / "assistant.sqlite",
        audio_dir=root / "audio",
        media_dir=root / "media",
        vision_max_image_bytes=1024 * 1024,
    )


class MediaServiceTest(unittest.TestCase):
    def test_upload_list_and_delete_wardrobe_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            settings = _test_settings(root)
            db = SQLiteStore(settings.database_path)
            db.initialize()
            media = MediaService(settings=settings, db=db)
            item = db.create_wardrobe_item(name="Black ankle boots", category="shoes")

            image = media.upload_image(
                data_url=TINY_PNG_DATA_URL,
                original_name="boots.png",
                item_id=item["id"],
            )

            self.assertEqual(image["item_id"], item["id"])
            self.assertEqual(image["mime_type"], "image/png")
            self.assertEqual(image["width"], 1)
            self.assertEqual(image["height"], 1)
            self.assertTrue((settings.media_dir / Path(image["image_url"]).name).exists())
            self.assertEqual(db.get_wardrobe_item(item["id"])["image_count"], 1)
            self.assertEqual(len(media.list_images(item_id=item["id"])), 1)

            self.assertTrue(media.delete_image(image["id"]))
            self.assertFalse((settings.media_dir / Path(image["image_url"]).name).exists())
            self.assertEqual(media.list_images(), [])
            self.assertEqual(db.get_wardrobe_item(item["id"])["image_count"], 0)

    def test_upload_rejects_missing_linked_item(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            settings = _test_settings(root)
            db = SQLiteStore(settings.database_path)
            db.initialize()
            media = MediaService(settings=settings, db=db)

            with self.assertRaises(MediaError):
                media.upload_image(data_url=TINY_PNG_DATA_URL, original_name="missing.png", item_id=404)


class FakeVisionClient:
    def __init__(self, provider: str = "ollama") -> None:
        self.calls: list[tuple[str, str | None]] = []
        self.provider = provider

    async def analyze(
        self,
        base64_image: str,
        *,
        prompt: str,
        model: str | None = None,
        mime_type: str | None = None,
    ) -> VisionResult:
        self.calls.append((prompt, model))
        self.payload = base64_image
        return VisionResult(analysis="**Garment:** black ankle boots.", provider=self.provider, model=model or "fake-vl")

    async def compare(
        self,
        images: list[dict[str, str]],
        *,
        prompt: str,
        model: str | None = None,
    ) -> VisionResult:
        self.calls.append((prompt, model))
        self.payloads = images
        return VisionResult(analysis="These two images work well together.", provider=self.provider, model=model or "fake-vl")


class VisionServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_analyze_image_dispatches_to_configured_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            settings = _test_settings(root)
            payload = TINY_PNG_DATA_URL.split(",", 1)[1]
            image_path = root / "sample.png"
            image_path.write_bytes(base64.b64decode(payload))

            service = VisionService(settings)
            fake = FakeVisionClient()
            service.ollama = fake

            result = await service.analyze_image(
                image_path=image_path,
                mime_type="image/png",
                prompt="Describe this item.",
                provider="ollama",
                model="fake-vl",
            )

            self.assertEqual(result.analysis, "**Garment:** black ankle boots.")
            self.assertEqual(result.provider, "ollama")
            self.assertIn("Never answer in Chinese", fake.calls[0][0])
            self.assertIn("Describe this item.", fake.calls[0][0])
            self.assertEqual(fake.calls[0][1], "fake-vl")
            self.assertTrue(fake.payload)

    async def test_analyze_image_dispatches_to_openrouter_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            settings = replace(_test_settings(root), vision_provider="openrouter")
            payload = TINY_PNG_DATA_URL.split(",", 1)[1]
            image_path = root / "sample.png"
            image_path.write_bytes(base64.b64decode(payload))

            service = VisionService(settings)
            fake = FakeVisionClient(provider="openrouter")
            service.openrouter = fake

            result = await service.analyze_image(
                image_path=image_path,
                mime_type="image/png",
                prompt="Describe this item.",
                provider="openrouter",
                model="xiaomi/mimo-v2.5",
            )

            self.assertEqual(result.provider, "openrouter")
            self.assertEqual(result.model, "xiaomi/mimo-v2.5")
            self.assertIn("Never answer in Chinese", fake.calls[0][0])
            self.assertEqual(fake.calls[0][1], "xiaomi/mimo-v2.5")

    async def test_compare_images_dispatches_with_language_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            settings = _test_settings(root)
            payload = TINY_PNG_DATA_URL.split(",", 1)[1]
            image_path_1 = root / "sample-1.png"
            image_path_2 = root / "sample-2.png"
            image_path_1.write_bytes(base64.b64decode(payload))
            image_path_2.write_bytes(base64.b64decode(payload))

            service = VisionService(settings)
            fake = FakeVisionClient()
            service.ollama = fake

            result = await service.compare_images(
                images=[
                    {"path": image_path_1, "mime_type": "image/png", "label": "boots"},
                    {"path": image_path_2, "mime_type": "image/png", "label": "jeans"},
                ],
                prompt="Compare these.",
                provider="ollama",
                model="fake-vl",
            )

            self.assertEqual(result.analysis, "These two images work well together.")
            self.assertIn("Never answer in Chinese", fake.calls[0][0])
            self.assertIn("Compare these.", fake.calls[0][0])
            self.assertEqual(len(fake.payloads), 2)


if __name__ == "__main__":
    unittest.main()
