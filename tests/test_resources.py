import sys
from pathlib import Path

from app.core import config, resources

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_resource_path_normal_apunta_a_la_raiz() -> None:
    assert resources.resource_path("app") == PROJECT_ROOT / "app"
    assert (
        resources.resource_path("alembic.ini")
        == PROJECT_ROOT / "alembic.ini"
    )


def test_resource_path_usa_meipass_cuando_esta_empaquetado(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert (
        resources.resource_path("app", "templates")
        == tmp_path / "app" / "templates"
    )


def test_base_dir_usa_carpeta_del_ejecutable_si_esta_congelado(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ejecutable = tmp_path / "ICIA.exe"
    ejecutable.write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(ejecutable))

    assert config._base_dir() == tmp_path
