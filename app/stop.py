from __future__ import annotations

import os
import signal

from app.core.config import DATA_DIR

PID_PATH = DATA_DIR / "icia.pid"


def detener() -> int:
    try:
        pid = int(PID_PATH.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return 1
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        PID_PATH.unlink(missing_ok=True)
        return 1
    PID_PATH.unlink(missing_ok=True)
    return 0


def main() -> None:
    raise SystemExit(detener())


if __name__ == "__main__":
    main()
