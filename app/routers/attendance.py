from __future__ import annotations

import csv
import io
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import APP_NAME
from app.core.database import get_db
from app.core.format import formato_fecha, formato_fecha_larga, formato_mxn
from app.services import attendance, catalog

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.filters["fecha"] = formato_fecha
templates.env.filters["fecha_larga"] = formato_fecha_larga
templates.env.filters["mxn"] = formato_mxn
templates.env.globals["app_name"] = APP_NAME

router = APIRouter(prefix="/asistencias", tags=["asistencias"])

CSV_HEADERS = (
    "Sucursal",
    "Grupo",
    "Fecha de sesión",
    "Estado de sesión",
    "Alumno",
    "Tutor",
    "Estado de asistencia",
    "Reposición",
    "Folio",
    "Monto MXN",
    "Origen de reposición",
)


def _fecha(valor: str | None) -> date | None:
    if valor is None or not valor.strip():
        return None
    try:
        return date.fromisoformat(valor.strip())
    except ValueError:
        return None


def _resolver_fechas(
    desde: str | None,
    hasta: str | None,
) -> tuple[date, date]:
    fecha_desde = _fecha(desde)
    fecha_hasta = _fecha(hasta)
    if (desde and fecha_desde is None) or (hasta and fecha_hasta is None):
        raise attendance.AttendanceError(
            "Las fechas deben tener formato AAAA-MM-DD."
        )
    if fecha_desde is None or fecha_hasta is None:
        predeterminada_desde, predeterminada_hasta = (
            attendance.rango_mes_actual()
        )
        fecha_desde = fecha_desde or predeterminada_desde
        fecha_hasta = fecha_hasta or predeterminada_hasta
    attendance.validar_rango(fecha_desde, fecha_hasta)
    return fecha_desde, fecha_hasta


def _monto_csv(centavos: int | None) -> str:
    if centavos is None:
        return ""
    return f"{centavos // 100}.{centavos % 100:02d}"


def _nombre_archivo(grupo_id: int, desde: date, hasta: date) -> str:
    return f"asistencias_{grupo_id}_{desde.isoformat()}_{hasta.isoformat()}.csv"


@router.get("", response_class=HTMLResponse)
def mostrar_asistencias(
    request: Request,
    grupo_id: Annotated[int | None, Query(ge=1)] = None,
    desde: Annotated[str | None, Query(max_length=10)] = None,
    hasta: Annotated[str | None, Query(max_length=10)] = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    grupos = catalog.listar_grupos_admin(db, incluir_inactivos=True)
    resumen = None
    error = None
    fecha_desde, fecha_hasta = attendance.rango_mes_actual()
    try:
        fecha_desde, fecha_hasta = _resolver_fechas(desde, hasta)
        if grupo_id is not None:
            resumen = attendance.resumen_asistencia(
                db,
                grupo_id,
                fecha_desde,
                fecha_hasta,
            )
    except attendance.AttendanceError as exc:
        error = str(exc)

    response = templates.TemplateResponse(
        request=request,
        name="attendance/index.html",
        context={
            "grupos": grupos,
            "resumen": resumen,
            "grupo_id": grupo_id,
            "desde": fecha_desde.isoformat(),
            "hasta": fecha_hasta.isoformat(),
            "error": error,
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/exportar", response_model=None)
def exportar_asistencias(
    grupo_id: Annotated[int, Query(ge=1)],
    desde: Annotated[str | None, Query(max_length=10)] = None,
    hasta: Annotated[str | None, Query(max_length=10)] = None,
    db: Session = Depends(get_db),
) -> StreamingResponse | PlainTextResponse:
    try:
        fecha_desde, fecha_hasta = _resolver_fechas(desde, hasta)
        resumen = attendance.resumen_asistencia(
            db,
            grupo_id,
            fecha_desde,
            fecha_hasta,
        )
    except attendance.AttendanceError as exc:
        return PlainTextResponse(str(exc), status_code=400)

    salida = io.StringIO()
    escritor = csv.writer(salida, delimiter=";", lineterminator="\r\n")
    escritor.writerow(CSV_HEADERS)
    for registro in resumen.registros:
        escritor.writerow(
            (
                registro.sucursal,
                registro.grupo,
                registro.fecha_sesion,
                registro.estado_sesion,
                registro.alumno,
                registro.tutor or "",
                registro.estado_asistencia,
                "Sí" if registro.reposicion else "No",
                registro.folio or "",
                _monto_csv(registro.monto_centavos),
                registro.origen or "",
            )
        )

    contenido = "\ufeff" + salida.getvalue()
    nombre = _nombre_archivo(grupo_id, fecha_desde, fecha_hasta)
    return StreamingResponse(
        iter((contenido,)),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{nombre}"',
            "Cache-Control": "no-store",
        },
    )
