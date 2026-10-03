from __future__ import annotations

import base64
import binascii
import re
import uuid
from pathlib import Path
from typing import Any

from mina_assistant.app.config import Settings
from mina_assistant.app.db import SQLiteStore


ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


class MediaError(RuntimeError):
    pass


class MediaService:
    def __init__(self, *, settings: Settings, db: SQLiteStore):
        self.settings = settings
        self.db = db
        self.media_dir = settings.media_dir

    def initialize(self) -> None:
        self.media_dir.mkdir(parents=True, exist_ok=True)

    def upload_image(
        self,
        *,
        data_url: str,
        original_name: str | None = None,
        item_id: int | None = None,
    ) -> dict[str, Any]:
        if item_id is not None and self.db.get_wardrobe_item(item_id) is None:
            raise MediaError("Prenda no encontrada para asociar la imagen.")

        mime_type, payload = _parse_data_url(data_url)
        extension = ALLOWED_IMAGE_TYPES.get(mime_type)
        if not extension:
            raise MediaError(f"Tipo de imagen no soportado: {mime_type}")
        if len(payload) > self.settings.vision_max_image_bytes:
            raise MediaError(
                f"La imagen excede el maximo configurado de {self.settings.vision_max_image_bytes} bytes."
            )

        self.initialize()
        filename = f"img_{uuid.uuid4().hex}{extension}"
        target = self.media_dir / filename
        target.write_bytes(payload)
        width, height = _image_dimensions(payload, mime_type)

        image = self.db.create_wardrobe_image(
            item_id=item_id,
            file_path=filename,
            thumbnail_path=None,
            original_name=original_name,
            mime_type=mime_type,
            width=width,
            height=height,
        )
        return self.image_response(image)

    def list_images(self, *, item_id: int | None = None, limit: int = 200) -> list[dict[str, Any]]:
        return [self.image_response(image) for image in self.db.list_wardrobe_images(item_id=item_id, limit=limit)]

    def get_image(self, image_id: int) -> dict[str, Any] | None:
        image = self.db.get_wardrobe_image(image_id)
        return self.image_response(image) if image else None

    def delete_image(self, image_id: int) -> bool:
        image = self.db.get_wardrobe_image(image_id)
        if not image:
            return False
        deleted = self.db.delete_wardrobe_image(image_id)
        if not deleted:
            return False
        _unlink_if_safe(self.media_dir, image.get("file_path"))
        _unlink_if_safe(self.media_dir, image.get("thumbnail_path"))
        return True

    def image_path(self, image: dict[str, Any]) -> Path:
        file_path = str(image.get("file_path") or "")
        path = (self.media_dir / file_path).resolve()
        root = self.media_dir.resolve()
        if not str(path).startswith(str(root)):
            raise MediaError("Ruta de imagen invalida.")
        if not path.exists():
            raise MediaError("Archivo de imagen no encontrado.")
        return path

    def image_response(self, image: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": image["id"],
            "item_id": image.get("item_id"),
            "image_url": _media_url(image.get("file_path")),
            "thumbnail_url": _media_url(image.get("thumbnail_path")),
            "original_name": image.get("original_name"),
            "mime_type": image.get("mime_type"),
            "width": image.get("width"),
            "height": image.get("height"),
            "analysis": image.get("analysis"),
            "created_at": image["created_at"],
            "deleted_at": image.get("deleted_at"),
        }


def _parse_data_url(value: str) -> tuple[str, bytes]:
    match = re.match(r"^data:(image/[a-zA-Z0-9.+-]+);base64,(.+)$", value, flags=re.DOTALL)
    if not match:
        raise MediaError("La imagen debe enviarse como data URL base64.")
    mime_type = match.group(1).lower()
    try:
        payload = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise MediaError("Base64 de imagen invalido.") from exc
    if not payload:
        raise MediaError("La imagen esta vacia.")
    return mime_type, payload


def _media_url(file_path: Any) -> str | None:
    if not file_path:
        return None
    safe_path = str(file_path).replace("\\", "/")
    return f"/media/{safe_path}"


def _unlink_if_safe(root: Path, file_path: Any) -> None:
    if not file_path:
        return
    path = (root / str(file_path)).resolve()
    if not str(path).startswith(str(root.resolve())):
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        return


def _image_dimensions(payload: bytes, mime_type: str) -> tuple[int | None, int | None]:
    if mime_type == "image/png" and len(payload) >= 24 and payload[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(payload[16:20], "big"), int.from_bytes(payload[20:24], "big")
    if mime_type == "image/jpeg":
        return _jpeg_dimensions(payload)
    return None, None


def _jpeg_dimensions(payload: bytes) -> tuple[int | None, int | None]:
    if len(payload) < 4 or payload[:2] != b"\xff\xd8":
        return None, None
    index = 2
    while index + 9 < len(payload):
        if payload[index] != 0xFF:
            index += 1
            continue
        marker = payload[index + 1]
        index += 2
        if marker in {0xD8, 0xD9}:
            continue
        if index + 2 > len(payload):
            return None, None
        length = int.from_bytes(payload[index : index + 2], "big")
        if length < 2 or index + length > len(payload):
            return None, None
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            height = int.from_bytes(payload[index + 3 : index + 5], "big")
            width = int.from_bytes(payload[index + 5 : index + 7], "big")
            return width, height
        index += length
    return None, None
