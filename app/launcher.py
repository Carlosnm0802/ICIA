from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from urllib.parse import urljoin

from app.bootstrap import ensure_database
from app.core.config import (
    APP_NAME,
    DATA_DIR,
    HOST,
    PORT,
    ensure_directories,
)

LOG_DIR = DATA_DIR / "logs"
LOG_PATH = LOG_DIR / "icia.log"
PID_PATH = DATA_DIR / "icia.pid"
BROWSER_PROFILE_DIR = DATA_DIR / "browser-profile"
APP_URL = f"http://{HOST}:{PORT}/"
HEALTH_URL = urljoin(APP_URL, "health")


def _configurar_log() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(LOG_PATH),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )


def _argumentos_navegador(executable: str) -> list[str]:
    return [
        executable,
        f"--app={APP_URL}",
        "--kiosk-printing",
        f"--user-data-dir={BROWSER_PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-sync",
    ]


def _rutas_navegador() -> list[Path]:
    candidatos: list[Path] = []
    if sys.platform == "win32":
        for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            base = os.getenv(variable)
            if not base:
                continue
            candidatos.extend(
                [
                    Path(base)
                    / "Google"
                    / "Chrome"
                    / "Application"
                    / "chrome.exe",
                    Path(base)
                    / "Microsoft"
                    / "Edge"
                    / "Application"
                    / "msedge.exe",
                ]
            )
    elif sys.platform == "darwin":
        candidatos.extend(
            [
                Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                Path(
                    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
                ),
            ]
        )
    else:
        candidatos.extend(
            [
                Path("/usr/bin/google-chrome"),
                Path("/usr/bin/chromium"),
            ]
        )
    return [ruta for ruta in candidatos if ruta.is_file()]


def abrir_navegador() -> bool:
    for executable in _rutas_navegador():
        try:
            subprocess.Popen(
                _argumentos_navegador(str(executable)),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return True
        except OSError:
            continue
    return webbrowser.open(APP_URL, new=1)


def servidor_activo(timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError):
        return False
    return data.get("app") == APP_NAME and data.get("status") == "ok"


def _abrir_cuando_este_listo(limite_segundos: float = 20.0) -> None:
    fin = time.monotonic() + limite_segundos
    while time.monotonic() < fin:
        if servidor_activo(timeout=1.0):
            abrir_navegador()
            return
        time.sleep(0.3)
    logging.error("El servidor no respondió antes de abrir el navegador.")


def _escribir_pid() -> None:
    PID_PATH.write_text(str(os.getpid()), encoding="utf-8")


def _limpiar_pid() -> None:
    try:
        if PID_PATH.read_text(encoding="utf-8").strip() == str(os.getpid()):
            PID_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def _mostrar_error(mensaje: str) -> None:
    logging.error(mensaje)
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                0,
                mensaje,
                f"{APP_NAME} no pudo iniciar",
                0x10,
            )
            return
        except (AttributeError, OSError):
            pass
    print(mensaje, file=sys.stderr)


def ejecutar() -> int:
    ensure_directories()
    _configurar_log()

    if servidor_activo():
        abrir_navegador()
        return 0

    try:
        from app.services.restore_service import apply_pending_restore

        apply_pending_restore()
    except Exception:
        logging.exception("No se pudo aplicar la restauración pendiente.")

    try:
        ensure_database()
    except Exception as exc:
        _mostrar_error(
            f"No se pudo preparar la base de datos. Revisa {LOG_PATH}. {exc}"
        )
        return 1

    _escribir_pid()
    hilo_navegador = threading.Thread(
        target=_abrir_cuando_este_listo,
        daemon=True,
    )
    hilo_navegador.start()

    try:
        import uvicorn

        from app.main import app

        config = uvicorn.Config(
            app,
            host=HOST,
            port=PORT,
            log_level="info",
            access_log=False,
        )
        server = uvicorn.Server(config)
        server.run()
    except Exception as exc:
        _mostrar_error(f"{APP_NAME} no pudo iniciar. Revisa {LOG_PATH}. {exc}")
        return 1
    finally:
        _limpiar_pid()

    return 0


def main() -> None:
    if "--detener" in sys.argv:
        from app.stop import detener

        raise SystemExit(detener())
    raise SystemExit(ejecutar())


if __name__ == "__main__":
    main()
