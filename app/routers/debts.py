from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Path as PathParam, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import APP_NAME
from app.core.database import get_db
from app.core.format import formato_fecha, formato_mxn
from app.services import cashier, reports, thermal_printer

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.filters["mxn"] = formato_mxn
templates.env.filters["fecha"] = formato_fecha
templates.env.globals["app_name"] = APP_NAME

router = APIRouter(prefix="/deudas", tags=["deudas"])
reposiciones_router = APIRouter(
    prefix="/reposiciones",
    tags=["reposiciones"],
)


@router.get("", response_class=HTMLResponse)
def mostrar_deudas(
    request: Request,
    cobrado: Annotated[int | None, Query(ge=1)] = None,
    error: Annotated[str | None, Query(max_length=200)] = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    deudas = reports.listar_deudas(db)
    ticket = (
        thermal_printer.obtener_ticket(db, cobrado)
        if cobrado is not None
        else None
    )
    response = templates.TemplateResponse(
        request=request,
        name="debts/index.html",
        context={
            "deudas": deudas,
            "total_centavos": sum(
                deuda.monto_centavos for deuda in deudas
            ),
            "ticket": ticket,
            "error": error,
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/{asistencia_id}/cobrar", response_model=None)
def cobrar_deuda(
    asistencia_id: Annotated[int, PathParam(ge=1)],
    metodo: Annotated[
        Literal["efectivo", "transferencia"],
        Form(),
    ],
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        resultado = cashier.cobrar_deuda(
            db,
            asistencia_id=asistencia_id,
            metodo=metodo,
        )
    except cashier.CashierError as exc:
        destino = f"/deudas?{urlencode({'error': str(exc)})}"
        return RedirectResponse(url=destino, status_code=303)

    destino = f"/deudas?{urlencode({'cobrado': resultado.pago_id})}"
    return RedirectResponse(url=destino, status_code=303)


@reposiciones_router.get("", response_class=HTMLResponse)
def mostrar_reposiciones(
    request: Request,
    registrada: Annotated[bool, Query()] = False,
    error: Annotated[str | None, Query(max_length=200)] = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    pendientes = reports.listar_reposiciones_pendientes(db)
    sesiones = reports.listar_sesiones_destino(db)
    opciones = {
        item.asistencia_id: [
            sesion
            for sesion in sesiones
            if sesion.grupo_id != item.grupo_id
            and sesion.fecha >= item.fecha_falta
        ]
        for item in pendientes
    }
    response = templates.TemplateResponse(
        request=request,
        name="debts/repositions.html",
        context={
            "pendientes": pendientes,
            "opciones": opciones,
            "total_centavos": sum(
                item.monto_centavos for item in pendientes
            ),
            "registrada": registrada,
            "error": error,
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@reposiciones_router.post("/{falta_id}/registrar", response_model=None)
def registrar_reposicion(
    falta_id: Annotated[int, PathParam(ge=1)],
    sesion_id: Annotated[int, Form(ge=1)],
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        cashier.registrar_reposicion(
            db,
            falta_id=falta_id,
            sesion_destino_id=sesion_id,
        )
    except cashier.CashierError as exc:
        destino = f"/reposiciones?{urlencode({'error': str(exc)})}"
        return RedirectResponse(url=destino, status_code=303)

    destino = f"/reposiciones?{urlencode({'registrada': '1'})}"
    return RedirectResponse(url=destino, status_code=303)
