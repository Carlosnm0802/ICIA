import os
import sys
from pathlib import Path

APP_NAME = "ICIA"
HOST = os.getenv("ICIA_HOST", "127.0.0.1")
PORT = int(os.getenv("ICIA_PORT", "8000"))


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


BASE_DIR = _base_dir()
DATA_DIR = (
    Path(os.getenv("ICIA_DATA_DIR", str(BASE_DIR / "data")))
    .expanduser()
    .resolve()
)
DATABASE_PATH = (
    Path(os.getenv("ICIA_DB_PATH", str(DATA_DIR / "icia.db")))
    .expanduser()
    .resolve()
)
PHOTOS_DIR = (
    Path(os.getenv("ICIA_PHOTOS_DIR", str(DATA_DIR / "photos")))
    .expanduser()
    .resolve()
)


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
