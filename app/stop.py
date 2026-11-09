from __future__ import annotations

import os
import signal
import sys
import time

from app.core.config import DATA_DIR

PID_PATH = DATA_DIR / "icia.pid"
STOP_PATH = DATA_DIR / "icia.stop"
ESPERA_SEGUNDOS = 8.0
INTERVALO_SEGUNDOS = 0.2


def _proceso_vivo(pid: int) -> bool:
    if sys.platform == "win32":
        import ctypes

        synchronize = 0x00100000
        wait_timeout = 0x00000102
        kernel32 = ctypes.windll.kernel32
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.OpenProcess.argtypes = [
            ctypes.c_ulong,
            ctypes.c_int,
            ctypes.c_ulong,
        ]
        kernel32.WaitForSingleObject.restype = ctypes.c_ulong
        kernel32.WaitForSingleObject.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
        ]
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel32.OpenProcess(synchronize, 0, pid)
        if not handle:
            return False
        try:
            return (
                kernel32.WaitForSingleObject(handle, 0) == wait_timeout
            )
        finally:
            kernel32.CloseHandle(handle)

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def detener(espera: float = ESPERA_SEGUNDOS) -> int:
    try:
        pid = int(PID_PATH.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return 1

    STOP_PATH.write_text(str(pid), encoding="utf-8")
    fin = time.monotonic() + espera
    while time.monotonic() < fin:
        if not PID_PATH.exists() or not _proceso_vivo(pid):
            STOP_PATH.unlink(missing_ok=True)
            PID_PATH.unlink(missing_ok=True)
            return 0
        time.sleep(INTERVALO_SEGUNDOS)

    STOP_PATH.unlink(missing_ok=True)
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
