import signal
from pathlib import Path

from app import launcher
from app import stop as stop_module


def _escribir_pid(path: Path, pid: int = 4242) -> None:
    path.write_text(str(pid), encoding="utf-8")


class _Servidor:
    def __init__(self) -> None:
        self.should_exit = False


def test_detener_sin_pid_devuelve_uno(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(stop_module, "PID_PATH", tmp_path / "icia.pid")
    monkeypatch.setattr(stop_module, "STOP_PATH", tmp_path / "icia.stop")

    assert stop_module.detener(espera=0.05) == 1
    assert not (tmp_path / "icia.stop").exists()


def test_detener_limpia_cuando_el_proceso_no_vive(
    tmp_path: Path,
    monkeypatch,
) -> None:
    pid_path = tmp_path / "icia.pid"
    stop_path = tmp_path / "icia.stop"
    _escribir_pid(pid_path)
    monkeypatch.setattr(stop_module, "PID_PATH", pid_path)
    monkeypatch.setattr(stop_module, "STOP_PATH", stop_path)
    monkeypatch.setattr(stop_module, "_proceso_vivo", lambda _pid: False)

    assert stop_module.detener(espera=0.5) == 0
    assert not pid_path.exists()
    assert not stop_path.exists()


def test_detener_espera_la_remocion_del_pid(
    tmp_path: Path,
    monkeypatch,
) -> None:
    pid_path = tmp_path / "icia.pid"
    stop_path = tmp_path / "icia.stop"
    _escribir_pid(pid_path)
    monkeypatch.setattr(stop_module, "PID_PATH", pid_path)
    monkeypatch.setattr(stop_module, "STOP_PATH", stop_path)
    monkeypatch.setattr(stop_module, "_proceso_vivo", lambda _pid: True)

    def _sleep(_segundos: float) -> None:
        pid_path.unlink(missing_ok=True)

    monkeypatch.setattr(stop_module.time, "sleep", _sleep)

    assert stop_module.detener(espera=1.0) == 0
    assert not pid_path.exists()
    assert not stop_path.exists()


def test_detener_usa_sigterm_como_respaldo(
    tmp_path: Path,
    monkeypatch,
) -> None:
    pid_path = tmp_path / "icia.pid"
    stop_path = tmp_path / "icia.stop"
    _escribir_pid(pid_path, pid=12345)
    monkeypatch.setattr(stop_module, "PID_PATH", pid_path)
    monkeypatch.setattr(stop_module, "STOP_PATH", stop_path)
    monkeypatch.setattr(stop_module, "_proceso_vivo", lambda _pid: True)
    monkeypatch.setattr(stop_module.time, "sleep", lambda _s: None)
    llamadas: list[tuple[int, int]] = []
    monkeypatch.setattr(
        stop_module.os,
        "kill",
        lambda pid, sig: llamadas.append((pid, sig)),
    )

    assert stop_module.detener(espera=0.0) == 0
    assert llamadas == [(12345, signal.SIGTERM)]
    assert not stop_path.exists()


def test_vigilar_parada_detecta_el_marcador(
    tmp_path: Path,
    monkeypatch,
) -> None:
    stop_path = tmp_path / "icia.stop"
    stop_path.write_text("4242", encoding="utf-8")
    monkeypatch.setattr(launcher, "STOP_PATH", stop_path)
    servidor = _Servidor()

    launcher._vigilar_parada(servidor, intervalo=0)

    assert servidor.should_exit is True
    assert not stop_path.exists()
