from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import DATABASE_PATH, ensure_directories
from app.core.resources import resource_path


def alembic_config(database_path: Path = DATABASE_PATH) -> Config:
    config = Config(str(resource_path("alembic.ini")))
    config.set_main_option(
        "script_location",
        str(resource_path("alembic")),
    )
    config.set_main_option(
        "prepend_sys_path",
        str(resource_path()),
    )
    config.set_main_option(
        "sqlalchemy.url",
        f"sqlite:///{Path(database_path).expanduser().resolve().as_posix()}",
    )
    return config


def ensure_database(database_path: Path = DATABASE_PATH) -> None:
    ensure_directories()
    command.upgrade(alembic_config(database_path), "head")
