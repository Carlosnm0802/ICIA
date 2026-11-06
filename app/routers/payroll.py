from datetime import date
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import APP_NAME
from app.core.database import get_db
from app.core.format import formato_fecha, formato_fecha_hora, formato_fecha_larga
from app.services import catalog, payroll

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.filters["fecha"] = formato_fecha
templates.env.filters["fecha_larga"] = formato_fecha_larga
templates.env.filters["fecha_hora"] = formato_fecha_hora
templates.env.globals["app_name"] = APP_NAME

router = APIRouter(prefix="/pagos-maestros", tags=["pagos-maestros"])


def _destino(params: dict[str, str | None]) -> RedirectResponse:
    limpios = {clave: valor for clave, valor in params.items() if valor}
    return RedirectResponse(
        url=f"/pagos-maestros?{urlencode(limpios)}",
        status_code=303,
    )


def _periodo(
    desde: str | None,
    hasta: str | None,
) -> tuple[date, date]:
    inicio_defecto, fin_defecto = payroll.rango_corte()
    try:
        inicio = date.fromisoformat(desde) if desde else inicio_defecto
        fin = date.fromisoformat(hasta) if hasta else fin_defecto
    except ValueError as exc:
        raise payroll.PayrollError(
            "Las fechas del corte no son válidas."
        ) from exc

    hoy = date.today()
    if fin > hoy:
        fin = hoy
    if inicio > fin:
        raise payroll.PayrollError(
            "El periodo no contiene días hasta hoy."
        )
    return inicio, fin


def _filtros(
    desde: str,
    hasta: str,
    sucursal_id: int | None,
    maestro_id: int | None,
    estado: str,
) -> dict[str, str | None]:
    return {
        "desde": desde,
        "hasta": hasta,
        "sucursal_id": str(sucursal_id) if sucursal_id is not None else None,
        "maestro_id": str(maestro_id) if maestro_id is not None else None,
        "estado": estado if estado in payroll.ESTADOS_PAGO else "todos",
    }


@router.get("", response_class=HTMLResponse)
def mostrar_pagos(
    request: Request,
    desde: Annotated[str | None, Query(max_length=10)] = None,
    hasta: Annotated[str | None, Query(max_length=10)] = None,
    sucursal_id: Annotated[int | None, Query(ge=1)] = None,
    maestro_id: Annotated[int | None, Query(ge=1)] = None,
    estado: Annotated[str, Query(max_length=20)] = "todos",
    actualizados: Annotated[int | None, Query(ge=0)] = None,
    error: Annotated[str | None, Query(max_length=300)] = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    try:
        inicio, fin = _periodo(desde, hasta)
    except payroll.PayrollError as exc:
        error = error or str(exc)
        inicio, fin = payroll.rango_corte()

    if estado not in payroll.ESTADOS_PAGO:
        estado = "todos"
        error = error or "El estado de pago no es válido."

    resumen = payroll.listar_honorarios(
        db,
        inicio,
        fin,
        sucursal_id=sucursal_id,
        maestro_id=maestro_id,
        estado=estado,
    )

    response = templates.TemplateResponse(
        request=request,
        name="payroll/index.html",
        context={
            "resumen": resumen,
            "sucursales": catalog.listar_sucursales_admin(db),
            "maestros": payroll.listar_maestros_filtro(db),
            "sucursal_id": sucursal_id,
            "maestro_id": maestro_id,
            "estado": estado,
            "actualizados": actualizados,
            "error": error,
            "hoy": date.today().isoformat(),
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/marcar", response_model=None)
def marcar_pagos(
    marca_ids: Annotated[list[int] | None, Form()] = None,
    pagado: Annotated[str, Form(max_length=1)] = "1",
    desde: Annotated[str | None, Form(max_length=10)] = None,
    hasta: Annotated[str | None, Form(max_length=10)] = None,
    sucursal_id: Annotated[int | None, Form(ge=1)] = None,
    maestro_id: Annotated[int | None, Form(ge=1)] = None,
    estado: Annotated[str, Form(max_length=20)] = "todos",
    db: Session = Depends(get_db),
) -> RedirectResponse:
    inicio_defecto, fin_defecto = payroll.rango_corte()
    desde_valor = desde or inicio_defecto.isoformat()
    hasta_valor = hasta or fin_defecto.isoformat()
    filtros = _filtros(
        desde_valor,
        hasta_valor,
        sucursal_id,
        maestro_id,
        estado,
    )

    if pagado not in {"0", "1"}:
        return _destino({**filtros, "error": "El estado de pago no es válido."})

    try:
        cambios = payroll.marcar_honorarios_lote(
            db,
            marca_ids or [],
            pagado=pagado == "1",
        )
    except payroll.PayrollError as exc:
        return _destino({**filtros, "error": str(exc)})

    return _destino({**filtros, "actualizados": str(cambios)})
