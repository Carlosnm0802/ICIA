from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import FolioContador, Sucursal

MAX_CONSECUTIVO = 9999


class FolioError(RuntimeError):
    pass


def siguiente_folio(db: Session, sucursal_id: int) -> str:
    prefijo = db.scalar(
        select(Sucursal.prefijo_folio).where(Sucursal.id == sucursal_id)
    )
    if prefijo is None:
        raise FolioError(f"No existe la sucursal {sucursal_id}")

    consecutivo = db.execute(
        text(
            "UPDATE folio_contadores "
            "SET ultimo_consecutivo = ultimo_consecutivo + 1 "
            "WHERE sucursal_id = :sucursal_id "
            "AND ultimo_consecutivo < :maximo "
            "RETURNING ultimo_consecutivo"
        ),
        {
            "sucursal_id": sucursal_id,
            "maximo": MAX_CONSECUTIVO,
        },
    ).scalar_one_or_none()

    if consecutivo is None:
        actual = db.scalar(
            select(FolioContador.ultimo_consecutivo).where(
                FolioContador.sucursal_id == sucursal_id
            )
        )
        if actual is None:
            raise FolioError(
                f"La sucursal {sucursal_id} no tiene contador de folios"
            )
        raise FolioError(
            f"La sucursal {sucursal_id} agotó su consecutivo de folios"
        )

    return f"{prefijo}-{consecutivo:04d}"
