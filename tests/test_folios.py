import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import build_engine
from app.models import FolioContador, Sucursal
from app.services.folios import FolioError, siguiente_folio
from app.services.seed import seed_database

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _config(database_path: Path) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("prepend_sys_path", str(PROJECT_ROOT))
    config.set_main_option(
        "sqlalchemy.url",
        f"sqlite:///{database_path.as_posix()}",
    )
    return config


@pytest.fixture
def folio_factory(
    tmp_path: Path,
) -> Iterator[sessionmaker[Session]]:
    database_path = tmp_path / "folios.db"
    command.upgrade(_config(database_path), "head")
    engine = build_engine(database_path)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        seed_database(session)
    try:
        yield factory
    finally:
        engine.dispose()


def _sucursal_id(
    factory: sessionmaker[Session],
    prefijo: str,
) -> int:
    with factory() as session:
        sucursal_id = session.scalar(
            select(Sucursal.id).where(Sucursal.prefijo_folio == prefijo)
        )
        assert sucursal_id is not None
        return sucursal_id


def test_primer_folio(folio_factory: sessionmaker[Session]) -> None:
    ref_id = _sucursal_id(folio_factory, "REF")

    with folio_factory.begin() as session:
        assert siguiente_folio(session, ref_id) == "REF-0001"


def test_folios_consecutivos(folio_factory: sessionmaker[Session]) -> None:
    ref_id = _sucursal_id(folio_factory, "REF")

    with folio_factory.begin() as session:
        folios = [siguiente_folio(session, ref_id) for _ in range(3)]

    assert folios == ["REF-0001", "REF-0002", "REF-0003"]


def test_consecutivos_independientes_por_sucursal(
    folio_factory: sessionmaker[Session],
) -> None:
    ref_id = _sucursal_id(folio_factory, "REF")
    tot_id = _sucursal_id(folio_factory, "TOT")

    with folio_factory.begin() as session:
        assert siguiente_folio(session, ref_id) == "REF-0001"
        assert siguiente_folio(session, tot_id) == "TOT-0001"
        assert siguiente_folio(session, ref_id) == "REF-0002"
        assert siguiente_folio(session, tot_id) == "TOT-0002"


def test_folio_comprometido_no_se_reutiliza(
    folio_factory: sessionmaker[Session],
) -> None:
    ref_id = _sucursal_id(folio_factory, "REF")

    with folio_factory.begin() as session:
        primero = siguiente_folio(session, ref_id)
    with folio_factory.begin() as session:
        segundo = siguiente_folio(session, ref_id)

    assert primero == "REF-0001"
    assert segundo == "REF-0002"


def test_rollback_no_consume_folio(
    folio_factory: sessionmaker[Session],
) -> None:
    ref_id = _sucursal_id(folio_factory, "REF")
    session = folio_factory()
    try:
        assert siguiente_folio(session, ref_id) == "REF-0001"
        session.rollback()
    finally:
        session.close()

    with folio_factory.begin() as session:
        assert siguiente_folio(session, ref_id) == "REF-0001"


def test_folios_unicos_bajo_concurrencia(
    folio_factory: sessionmaker[Session],
) -> None:
    ref_id = _sucursal_id(folio_factory, "REF")
    barrera = threading.Barrier(2)

    def emitir(_: int) -> str:
        with folio_factory.begin() as session:
            barrera.wait(timeout=5)
            return siguiente_folio(session, ref_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        folios = list(executor.map(emitir, range(2)))

    assert set(folios) == {"REF-0001", "REF-0002"}


def test_sucursal_inexistente(
    folio_factory: sessionmaker[Session],
) -> None:
    with folio_factory.begin() as session:
        with pytest.raises(FolioError, match="No existe la sucursal"):
            siguiente_folio(session, 999999)


def test_sucursal_sin_contador(
    folio_factory: sessionmaker[Session],
) -> None:
    ref_id = _sucursal_id(folio_factory, "REF")
    with folio_factory.begin() as session:
        session.execute(
            text(
                "DELETE FROM folio_contadores "
                "WHERE sucursal_id = :sucursal_id"
            ),
            {"sucursal_id": ref_id},
        )

    with folio_factory.begin() as session:
        with pytest.raises(FolioError, match="no tiene contador"):
            siguiente_folio(session, ref_id)


def test_consecutivo_agotado_no_avanza(
    folio_factory: sessionmaker[Session],
) -> None:
    ref_id = _sucursal_id(folio_factory, "REF")
    with folio_factory.begin() as session:
        session.execute(
            text(
                "UPDATE folio_contadores "
                "SET ultimo_consecutivo = 9999 "
                "WHERE sucursal_id = :sucursal_id"
            ),
            {"sucursal_id": ref_id},
        )

    with pytest.raises(FolioError, match="agotó su consecutivo"):
        with folio_factory.begin() as session:
            siguiente_folio(session, ref_id)

    with folio_factory() as session:
        assert (
            session.scalar(
                select(FolioContador.ultimo_consecutivo).where(
                    FolioContador.sucursal_id == ref_id
                )
            )
            == 9999
        )
