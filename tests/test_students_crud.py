from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import build_engine, get_db
from app.core.security import requiere_sesion
from app.main import app
from app.models import Alumno, Asistencia, Grupo, GrupoAlumno, Pago, Sesion
from app.services import cashier as cashier_service
from app.services import photos
from app.services.seed import seed_database

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff" + b"\x00" * 16


def _config(database_path: Path) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("prepend_sys_path", str(PROJECT_ROOT))
    config.set_main_option(
        "sqlalchemy.url",
        f"sqlite:///{database_path.as_posix()}",
    )
    return config


@pytest.fixture
def students_app(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    monkeypatch.setattr(photos, "PHOTOS_DIR", tmp_path / "photos")
    database_path = tmp_path / "students.db"
    command.upgrade(_config(database_path), "head")
    engine = build_engine(database_path)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        seed_database(session)

    def override_get_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[requiere_sesion] = lambda: None
    try:
        with TestClient(app) as client:
            yield client, factory
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _datos_alumno(nombre: str = "Ana Pérez") -> dict[str, str]:
    return {
        "nombre": nombre,
        "fecha_nacimiento": "2015-05-10",
        "tutor": "Laura Pérez",
        "telefono_tutor": "333-123-4567",
        "escuela_procedencia": "Primaria Centro",
        "alergias_notas": "Sin alergias",
        "personas_autorizadas": "Laura Pérez, Abuela",
        "fecha_inscripcion": "2026-01-15",
    }


def _crear(
    client: TestClient,
    nombre: str = "Ana Pérez",
    *,
    foto: bool = True,
    **overrides: str,
):
    datos = _datos_alumno(nombre)
    datos.update(overrides)
    archivos = (
        {"foto": ("foto.png", PNG, "image/png")}
        if foto
        else {"foto": ("", b"", "application/octet-stream")}
    )
    return client.post(
        "/alumnos",
        data=datos,
        files=archivos,
        follow_redirects=False,
    )


def _alumno(factory: sessionmaker[Session], nombre: str = "Ana Pérez") -> Alumno:
    with factory() as session:
        alumno = session.scalar(select(Alumno).where(Alumno.nombre == nombre))
        assert alumno is not None
        return alumno


def test_listado_alta_foto_y_busqueda(
    students_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = students_app

    listado = client.get("/alumnos")
    assert listado.status_code == 200
    assert "ICIA" in listado.text
    assert "Alumno 01" in listado.text

    creada = _crear(client, "Ana Pérez")
    assert creada.status_code == 303
    assert creada.headers["location"].startswith("/alumnos/")

    alumno = _alumno(factory)
    assert alumno.nombre == "Ana Pérez"
    assert alumno.tutor == "Laura Pérez"
    assert alumno.fecha_inscripcion == "2026-01-15"
    assert alumno.estado == "activo"
    assert alumno.foto_ruta is not None
    assert alumno.foto_ruta.startswith("alumnos/")
    archivo = photos.resolver_foto(alumno.foto_ruta)
    assert archivo is not None
    assert archivo.read_bytes() == PNG

    ficha = client.get(f"/alumnos/{alumno.id}")
    assert ficha.status_code == 200
    assert "Ana Pérez" in ficha.text
    assert "Laura Pérez" in ficha.text
    assert "Grupos" in ficha.text
    assert "Pagos" in ficha.text

    foto = client.get(f"/alumnos/{alumno.id}/foto")
    assert foto.status_code == 200
    assert foto.content == PNG

    busqueda = client.get("/alumnos?q=laura")
    assert busqueda.status_code == 200
    assert "Ana Pérez" in busqueda.text


def test_actualiza_reemplaza_y_quita_foto(
    students_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = students_app
    _crear(client, "Ana Pérez")
    alumno = _alumno(factory)
    ruta_anterior = alumno.foto_ruta
    archivo_anterior = photos.resolver_foto(ruta_anterior)
    assert archivo_anterior is not None

    datos = _datos_alumno("Ana Pérez López")
    datos["tutor"] = "Laura López"
    respuesta = client.post(
        f"/alumnos/{alumno.id}",
        data=datos,
        files={"foto": ("nueva.jpg", JPEG, "image/jpeg")},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303

    actualizado = _alumno(factory, "Ana Pérez López")
    assert actualizado.tutor == "Laura López"
    assert actualizado.foto_ruta is not None
    assert actualizado.foto_ruta != ruta_anterior
    assert not archivo_anterior.exists()
    archivo_nuevo = photos.resolver_foto(actualizado.foto_ruta)
    assert archivo_nuevo is not None
    assert archivo_nuevo.read_bytes() == JPEG

    ruta_nueva = actualizado.foto_ruta
    sin_foto = client.post(
        f"/alumnos/{alumno.id}",
        data=datos | {"quitar_foto": "1"},
        files={"foto": ("", b"", "application/octet-stream")},
        follow_redirects=False,
    )
    assert sin_foto.status_code == 303
    final = _alumno(factory, "Ana Pérez López")
    assert final.foto_ruta is None
    assert photos.resolver_foto(ruta_nueva) is None


def test_rechaza_foto_invalida_y_fecha_invalida(
    students_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = students_app

    foto = client.post(
        "/alumnos",
        data=_datos_alumno("Foto Mala"),
        files={"foto": ("foto.png", b"texto", "image/png")},
        follow_redirects=False,
    )
    assert foto.status_code == 303
    assert "error=" in foto.headers["location"]
    with factory() as session:
        assert (
            session.scalar(select(Alumno).where(Alumno.nombre == "Foto Mala"))
            is None
        )

    fecha = _crear(client, "Fecha Mala", fecha_nacimiento="ayer")
    assert fecha.status_code == 303
    assert "error=" in fecha.headers["location"]
    with factory() as session:
        assert (
            session.scalar(select(Alumno).where(Alumno.nombre == "Fecha Mala"))
            is None
        )


def test_baja_reactivacion_y_grupos_conservan_historial(
    students_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = students_app
    with factory() as session:
        alumno = session.scalar(
            select(Alumno).where(Alumno.nombre == "Alumno 01")
        )
        grupo = session.scalar(
            select(Grupo).where(Grupo.nombre == "Jueves 3-5 PM")
        )
        assert alumno is not None and grupo is not None
        alumno_id = alumno.id
        grupo_id = grupo.id
        sesion = Sesion(
            grupo_id=grupo_id,
            fecha=date.today().isoformat(),
            estado="programada",
        )
        session.add(sesion)
        session.commit()
        sesion_id = sesion.id

    with factory() as session:
        cashier_service.cobrar_sesion(
            session,
            sesion_id=sesion_id,
            alumno_id=alumno_id,
            metodo="efectivo",
        )

    baja = client.post(
        f"/alumnos/{alumno_id}/estado",
        data={"estado": "baja"},
        follow_redirects=False,
    )
    assert baja.status_code == 303

    with factory() as session:
        alumno = session.get(Alumno, alumno_id)
        assert alumno is not None
        assert alumno.estado == "baja"
        inscripciones = list(
            session.scalars(
                select(GrupoAlumno).where(
                    GrupoAlumno.alumno_id == alumno_id,
                )
            )
        )
        assert len(inscripciones) == 1
        assert inscripciones[0].fecha_baja is not None
        assert session.scalar(
            select(func.count(Pago.id)).where(Pago.alumno_id == alumno_id)
        ) == 1
        assert session.scalar(
            select(func.count(Asistencia.id)).where(
                Asistencia.alumno_id == alumno_id
            )
        ) == 1

    reactivar = client.post(
        f"/alumnos/{alumno_id}/estado",
        data={"estado": "activo"},
        follow_redirects=False,
    )
    assert reactivar.status_code == 303

    inscribir = client.post(
        f"/alumnos/{alumno_id}/grupos",
        data={"grupo_id": grupo_id},
        follow_redirects=False,
    )
    assert inscribir.status_code == 303

    with factory() as session:
        activas = list(
            session.scalars(
                select(GrupoAlumno).where(
                    GrupoAlumno.alumno_id == alumno_id,
                    GrupoAlumno.fecha_baja.is_(None),
                )
            )
        )
        assert len(activas) == 1
        inscripcion_id = activas[0].id

    duplicada = client.post(
        f"/alumnos/{alumno_id}/grupos",
        data={"grupo_id": grupo_id},
        follow_redirects=False,
    )
    assert duplicada.status_code == 303
    assert "error=" in duplicada.headers["location"]

    retirar = client.post(
        f"/alumnos/{alumno_id}/grupos/{inscripcion_id}/baja",
        follow_redirects=False,
    )
    assert retirar.status_code == 303

    with factory() as session:
        assert session.scalar(
            select(func.count(GrupoAlumno.id)).where(
                GrupoAlumno.alumno_id == alumno_id,
                GrupoAlumno.fecha_baja.is_(None),
            )
        ) == 0
        assert session.scalar(
            select(func.count(GrupoAlumno.id)).where(
                GrupoAlumno.alumno_id == alumno_id,
            )
        ) == 2
