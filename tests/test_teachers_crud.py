from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import build_engine, get_db
from app.core.security import requiere_sesion
from app.main import app
from app.models import BloqueGrupo, Grupo, Maestro
from app.services import catalog
from app.services import photos
from app.services import teachers as teachers_service
from app.services.seed import seed_database

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def _config(database_path: Path) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("prepend_sys_path", str(PROJECT_ROOT))
    config.set_main_option(
        "sqlalchemy.url",
        f"sqlite:///{database_path.as_posix()}",
    )
    return config


@pytest.fixture
def teachers_app(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    monkeypatch.setattr(photos, "PHOTOS_DIR", tmp_path / "photos")
    database_path = tmp_path / "teachers.db"
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


def _datos_maestro(nombre: str = "Maestro Nuevo") -> dict[str, str]:
    return {
        "nombre": nombre,
        "fecha_nacimiento": "1990-04-12",
        "telefono": "333-000-1111",
        "correo": "maestro@example.com",
        "direccion": "Calle 1",
        "especialidad": "Robótica",
        "fecha_ingreso": "2025-08-01",
        "contacto_emergencia": "Familiar 333-000-2222",
    }


def _crear(
    client: TestClient,
    nombre: str = "Maestro Nuevo",
    *,
    foto: bool = True,
):
    archivos = (
        {"foto": ("foto.png", PNG, "image/png")}
        if foto
        else {"foto": ("", b"", "application/octet-stream")}
    )
    return client.post(
        "/maestros",
        data=_datos_maestro(nombre),
        files=archivos,
        follow_redirects=False,
    )


def _maestro(
    factory: sessionmaker[Session],
    nombre: str = "Maestro Nuevo",
) -> Maestro:
    with factory() as session:
        maestro = session.scalar(
            select(Maestro).where(Maestro.nombre == nombre)
        )
        assert maestro is not None
        return maestro


def test_listado_alta_foto_y_ficha(
    teachers_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = teachers_app

    listado = client.get("/maestros")
    assert listado.status_code == 200
    assert "ICIA" in listado.text
    assert "Maestro de Inglés" in listado.text

    creado = _crear(client)
    assert creado.status_code == 303
    assert creado.headers["location"].startswith("/maestros/")

    maestro = _maestro(factory)
    assert maestro.nombre == "Maestro Nuevo"
    assert maestro.especialidad == "Robótica"
    assert maestro.activo == 1
    assert maestro.foto_ruta is not None
    assert maestro.foto_ruta.startswith("maestros/")
    archivo = photos.resolver_foto(maestro.foto_ruta)
    assert archivo is not None
    assert archivo.read_bytes() == PNG

    ficha = client.get(f"/maestros/{maestro.id}")
    assert ficha.status_code == 200
    assert "Maestro Nuevo" in ficha.text
    assert "Datos personales" in ficha.text
    assert "Marcas de pago" in ficha.text

    foto = client.get(f"/maestros/{maestro.id}/foto")
    assert foto.status_code == 200
    assert foto.content == PNG

    busqueda = client.get("/maestros?q=robotica")
    assert busqueda.status_code == 200
    assert "Maestro Nuevo" in busqueda.text


def test_actualiza_maestro(
    teachers_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = teachers_app
    _crear(client)
    maestro = _maestro(factory)

    datos = _datos_maestro("Maestro Actualizado")
    datos["especialidad"] = "Inglés"
    respuesta = client.post(
        f"/maestros/{maestro.id}",
        data=datos,
        files={"foto": ("", b"", "application/octet-stream")},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303

    actualizado = _maestro(factory, "Maestro Actualizado")
    assert actualizado.especialidad == "Inglés"
    assert actualizado.foto_ruta == maestro.foto_ruta


def test_baja_bloqueada_con_grupo_activo(
    teachers_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = teachers_app
    with factory() as session:
        maestro = session.scalar(
            select(Maestro).where(Maestro.nombre == "Maestro de Inglés")
        )
        otro = session.scalar(
            select(Maestro).where(Maestro.nombre == "Maestro de Robótica")
        )
        assert maestro is not None and otro is not None
        maestro_id = maestro.id
        otro_id = otro.id

    bloqueada = client.post(
        f"/maestros/{maestro_id}/estado",
        data={"activo": "0"},
        follow_redirects=False,
    )
    assert bloqueada.status_code == 303
    assert "error=" in bloqueada.headers["location"]

    with factory() as session:
        assert session.get(Maestro, maestro_id).activo == 1
        session.execute(
            update(BloqueGrupo)
            .where(BloqueGrupo.maestro_id == maestro_id)
            .values(maestro_id=otro_id)
        )
        session.commit()

    permitida = client.post(
        f"/maestros/{maestro_id}/estado",
        data={"activo": "0"},
        follow_redirects=False,
    )
    assert permitida.status_code == 303

    with factory() as session:
        assert session.get(Maestro, maestro_id).activo == 0
        assert session.scalar(
            select(BloqueGrupo).where(
                BloqueGrupo.maestro_id == maestro_id
            )
        ) is None

    reactivar = client.post(
        f"/maestros/{maestro_id}/estado",
        data={"activo": "1"},
        follow_redirects=False,
    )
    assert reactivar.status_code == 303
    with factory() as session:
        assert session.get(Maestro, maestro_id).activo == 1


def test_grupo_inactivo_conserva_maestro_inactivo(
    teachers_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = teachers_app
    with factory() as session:
        maestro = session.scalar(
            select(Maestro).where(Maestro.nombre == "Maestro de Inglés")
        )
        grupo = session.scalar(
            select(Grupo).where(Grupo.nombre == "Jueves 3-5 PM")
        )
        assert maestro is not None and grupo is not None
        maestro_id = maestro.id
        grupo_id = grupo.id
        sucursal_id = grupo.sucursal_id
        catalog.cambiar_estado_grupo(session, grupo_id, activo=False)
        teachers_service.cambiar_estado_maestro(
            session,
            maestro_id,
            activo=False,
        )

    editar = client.get(f"/grupos/{grupo_id}/editar")
    assert editar.status_code == 200
    assert "Maestro de Inglés" in editar.text
    assert "(inactivo)" in editar.text

    with factory() as session:
        grupo = session.get(Grupo, grupo_id)
        assert grupo is not None
        bloques = list(
            session.scalars(
                select(BloqueGrupo)
                .where(BloqueGrupo.grupo_id == grupo_id)
                .order_by(BloqueGrupo.orden)
            )
        )
        maestros = [bloque.maestro_id for bloque in bloques]
        materias = [bloque.materia for bloque in bloques]
        duraciones = [bloque.duracion_minutos for bloque in bloques]

    actualizar = client.post(
        f"/grupos/{grupo_id}",
        data={
            "sucursal_id": sucursal_id,
            "nombre": grupo.nombre,
            "dias_semana": grupo.dias_semana.split(","),
            "hora_inicio": grupo.hora_inicio,
            "hora_fin": grupo.hora_fin,
            "precio": "140.00",
            "bloque_materia": materias,
            "bloque_duracion": duraciones,
            "bloque_maestro": maestros,
        },
        follow_redirects=False,
    )
    assert actualizar.status_code == 303
    assert "error=" not in actualizar.headers["location"]

    with factory() as session:
        assert session.scalar(
            select(BloqueGrupo).where(
                BloqueGrupo.grupo_id == grupo_id,
                BloqueGrupo.maestro_id == maestro_id,
            )
        ) is not None
