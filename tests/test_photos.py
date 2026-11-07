from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile

from app.services import photos

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff" + b"\x00" * 16
WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 16


def _upload(data: bytes, nombre: str = "foto.png") -> UploadFile:
    return UploadFile(filename=nombre, file=BytesIO(data))


def test_guardar_y_resolver_foto(tmp_path: Path) -> None:
    ruta = photos.guardar_foto(_upload(PNG), "alumnos", tmp_path)
    assert ruta is not None
    assert ruta.startswith("alumnos/")
    assert ruta.endswith(".png")
    archivo = photos.resolver_foto(ruta, tmp_path)
    assert archivo is not None
    assert archivo.read_bytes() == PNG


def test_acepta_jpeg_y_webp(tmp_path: Path) -> None:
    jpg = photos.guardar_foto(_upload(JPEG, "foto.jpg"), "maestros", tmp_path)
    webp = photos.guardar_foto(_upload(WEBP, "foto.webp"), "maestros", tmp_path)
    assert jpg is not None and jpg.endswith(".jpg")
    assert webp is not None and webp.endswith(".webp")


def test_rechaza_tipo_invalido(tmp_path: Path) -> None:
    with pytest.raises(photos.PhotoError, match="JPG"):
        photos.guardar_foto(_upload(b"texto plano"), "alumnos", tmp_path)


def test_rechaza_archivo_vacio(tmp_path: Path) -> None:
    with pytest.raises(photos.PhotoError, match="vacía"):
        photos.guardar_foto(_upload(b""), "alumnos", tmp_path)


def test_rechaza_archivo_demasiado_grande(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(photos, "MAX_PHOTO_BYTES", 8)
    with pytest.raises(photos.PhotoError, match="5 MB"):
        photos.guardar_foto(_upload(PNG), "alumnos", tmp_path)


def test_rechaza_categoria_desconocida(tmp_path: Path) -> None:
    with pytest.raises(photos.PhotoError, match="Categoría"):
        photos.guardar_foto(_upload(PNG), "otros", tmp_path)


def test_resolver_no_permite_salir_de_la_carpeta(tmp_path: Path) -> None:
    assert photos.resolver_foto("../secreto.png", tmp_path) is None
    assert photos.resolver_foto("alumnos/../secreto.png", tmp_path) is None


def test_borrar_foto(tmp_path: Path) -> None:
    ruta = photos.guardar_foto(_upload(PNG), "alumnos", tmp_path)
    assert ruta is not None
    archivo = photos.resolver_foto(ruta, tmp_path)
    assert archivo is not None
    photos.borrar_foto(ruta, tmp_path)
    assert not archivo.exists()
    photos.borrar_foto(ruta, tmp_path)
