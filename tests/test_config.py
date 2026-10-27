from app.core.config import (
    APP_NAME,
    BACKUP_DIR,
    BASE_DIR,
    DATA_DIR,
    DATABASE_PATH,
    PHOTOS_DIR,
)


def test_app_name_is_icia() -> None:
    assert APP_NAME == "ICIA"


def test_paths_are_absolute() -> None:
    assert BASE_DIR.is_absolute()
    assert DATA_DIR.is_absolute()
    assert DATABASE_PATH.is_absolute()
    assert PHOTOS_DIR.is_absolute()
    assert BACKUP_DIR.is_absolute()


def test_database_path_uses_sqlite_file() -> None:
    assert DATABASE_PATH.suffix == ".db"
