from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import PHOTOS_DIR

MAX_PHOTO_BYTES = 5 * 1024 * 1024
CATEGORIAS = {"alumnos", "maestros"}


class PhotoError(Exception):
    pass


def _detectar_tipo(data: bytes) -> tuple[str, str] | None:
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg", "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png", "image/png"
    if (
        len(data) >= 12
        and data[:4] == b"RIFF"
        and data[8:12] == b"WEBP"
    ):
        return ".webp", "image/webp"
    return None


def _base(base_dir: Path | None) -> Path:
    return (base_dir or PHOTOS_DIR).resolve()


def guardar_foto(
    upload: UploadFile | None,
    categoria: str,
    base_dir: Path | None = None,
) -> str | None:
    if categoria not in CATEGORIAS:
        raise PhotoError("Categoría de foto no válida.")
    if upload is None or not upload.filename:
        return None

    data = upload.file.read(MAX_PHOTO_BYTES + 1)
    if not data:
        raise PhotoError("La foto está vacía.")
    if len(data) > MAX_PHOTO_BYTES:
        raise PhotoError("La foto no puede superar los 5 MB.")

    tipo = _detectar_tipo(data)
    if tipo is None:
        raise PhotoError("La foto debe ser JPG, PNG o WebP.")

    extension, _ = tipo
    destino_dir = _base(base_dir) / categoria
    destino_dir.mkdir(parents=True, exist_ok=True)
    nombre = f"{uuid4().hex}{extension}"
    destino = destino_dir / nombre
    destino.write_bytes(data)
    return f"{categoria}/{nombre}"


def resolver_foto(
    ruta: str | None,
    base_dir: Path | None = None,
) -> Path | None:
    if not ruta:
        return None
    base = _base(base_dir)
    destino = (base / ruta).resolve()
    if not destino.is_relative_to(base):
        return None
    if not destino.is_file():
        return None
    return destino


def borrar_foto(ruta: str | None, base_dir: Path | None = None) -> None:
    destino = resolver_foto(ruta, base_dir)
    if destino is None:
        return
    try:
        destino.unlink()
    except OSError:
        return
