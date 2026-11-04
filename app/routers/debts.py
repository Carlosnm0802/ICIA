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
