from pathlib import Path

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import APP_NAME
from app.core.database import get_db
from app.core.format import formato_fecha, formato_fecha_larga, formato_mxn
from app.services import reports

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.filters["mxn"] = formato_mxn
templates.env.filters["fecha"] = formato_fecha
templates.env.filters["fecha_larga"] = formato_fecha_larga
templates.env.globals["app_name"] = APP_NAME

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_class=HTMLResponse)
def mostrar_dashboard(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    resumen = reports.resumen_dashboard(db)
    response = templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"resumen": resumen},
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/dashboard/recaudacion")
def recaudacion_por_sucursal(
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    desde, hasta = reports.rango_semana()
    filas = reports.recaudacion_por_sucursal(db, desde, hasta)
    response.headers["Cache-Control"] = "no-store"
    return {
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "total_centavos": sum(fila.total_centavos for fila in filas),
        "sucursales": [
            {
                "id": fila.sucursal_id,
                "nombre": fila.nombre,
                "prefijo_folio": fila.prefijo_folio,
                "total_centavos": fila.total_centavos,
                "tickets": fila.tickets,
            }
            for fila in filas
        ],
    }
