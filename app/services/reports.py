from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import Alumno, Pago


@dataclass(frozen=True)
class ResumenDashboard:
    fecha: date
    inicio_semana: date
    cobrado_hoy_centavos: int
    tickets_hoy: int
    cobrado_semana_centavos: int
    tickets_semana: int
    deudas_asistencias: int
    deudas_centavos: int
    alumnos_activos: int


def _pagos_periodo(
    db: Session,
    desde: date,
    hasta: date,
) -> tuple[int, int]:
    total, tickets = db.execute(
        select(
            func.coalesce(func.sum(Pago.monto_centavos), 0),
            func.count(Pago.id),
        ).where(
            Pago.estado == "vigente",
            func.date(Pago.fecha) >= desde.isoformat(),
            func.date(Pago.fecha) <= hasta.isoformat(),
        )
    ).one()
    return int(total), int(tickets)


def resumen_dashboard(
    db: Session,
    hoy: date | None = None,
) -> ResumenDashboard:
    fecha = hoy or date.today()
    inicio_semana = fecha - timedelta(days=fecha.weekday())

    cobrado_hoy, tickets_hoy = _pagos_periodo(db, fecha, fecha)
    cobrado_semana, tickets_semana = _pagos_periodo(
        db,
        inicio_semana,
        fecha,
    )

    deudas = db.execute(
        text(
            "SELECT COUNT(*) AS asistencias, "
            "COALESCE(SUM(monto_centavos), 0) AS monto "
            "FROM v_deudas"
        )
    ).mappings().one()

    alumnos_activos = db.scalar(
        select(func.count(Alumno.id)).where(Alumno.estado == "activo")
    )

    return ResumenDashboard(
        fecha=fecha,
        inicio_semana=inicio_semana,
        cobrado_hoy_centavos=cobrado_hoy,
        tickets_hoy=tickets_hoy,
        cobrado_semana_centavos=cobrado_semana,
        tickets_semana=tickets_semana,
        deudas_asistencias=int(deudas["asistencias"]),
        deudas_centavos=int(deudas["monto"]),
        alumnos_activos=int(alumnos_activos or 0),
    )
