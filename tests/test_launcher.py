import json
import sqlite3
from pathlib import Path

from app import launcher
from app.bootstrap import ensure_database


class _Respuesta:
    def __init__(self, payload: dict[str, str]) -> None:
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_Respuesta":
        return self

    def __exit__(self, *_args) -> None:
        return None


def test_bootstrap_creates_schema_and_is_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "icia.db"

    ensure_database(database_path)
    ensure_database(database_path)

    connection = sqlite3.connect(database_path)
    try:
        tablas = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        vistas = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'view'"
            )
        }
    finally:
        connection.close()

    assert "alumnos" in tablas
    assert "pagos" in tablas
    assert "alembic_version" in tablas
    assert "v_deudas" in vistas


def test_argumentos_navegador_incluyen_impresion_silenciosa() -> None:
    argumentos = launcher._argumentos_navegador("C:/Chrome/chrome.exe")

    assert argumentos[0] == "C:/Chrome/chrome.exe"
    assert any(item.startswith("--app=") for item in argumentos)
    assert "--kiosk-printing" in argumentos
    assert any(
        item.startswith("--user-data-dir=") for item in argumentos
    )


def test_servidor_activo_valida_identidad(monkeypatch) -> None:
    monkeypatch.setattr(
        launcher.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _Respuesta(
            {"status": "ok", "app": "ICIA"}
        ),
    )
    assert launcher.servidor_activo()

    monkeypatch.setattr(
        launcher.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _Respuesta(
            {"status": "ok", "app": "Otra"}
        ),
    )
    assert not launcher.servidor_activo()


def test_abrir_navegador_usa_perfil_local(
    tmp_path: Path,
    monkeypatch,
) -> None:
    executable = tmp_path / "chrome.exe"
    executable.write_text("", encoding="utf-8")
    llamadas = []

    def _popen(argumentos, **_kwargs):
        llamadas.append(argumentos)
        return object()

    monkeypatch.setattr(launcher, "_rutas_navegador", lambda: [executable])
    monkeypatch.setattr(launcher.subprocess, "Popen", _popen)

    assert launcher.abrir_navegador()
    assert llamadas
    assert f"--app={launcher.APP_URL}" in llamadas[0]
    assert "--kiosk-printing" in llamadas[0]
