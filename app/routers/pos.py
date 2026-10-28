from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import APP_NAME
from app.core.database import get_db
from app.core.format import (
    formato_fecha,
    formato_fecha_corta,
    formato_fecha_larga,
    formato_mxn,
)
from app.services import pos as pos_service

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.filters["mxn"] = formato_mxn
templates.env.filters["fecha"] = formato_fecha
templates.env.filters["fecha_corta"] = formato_fecha_corta
templates.env.filters["fecha_larga"] = formato_fecha_larga
templates.env.globals["app_name"] = APP_NAME

router = APIRouter(prefix="/pos", tags=["pos"])


@router.get("", response_class=HTMLResponse)
def mostrar_pos(
    request: Request,
    sucursal_id: Annotated[int | None, Query(ge=1)] = None,
    grupo_id: Annotated[int | None, Query(ge=1)] = None,
    sesion_id: Annotated[int | None, Query(ge=1)] = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    sucursales = pos_service.listar_sucursales(db)
    sucursal = (
        pos_service.obtener_sucursal(db, sucursal_id)
        if sucursal_id is not None
        else None
    )
    grupos: list = []
    grupo = None
    sesiones: list = []
    sesion = None
    alumnos: list = []
    resumen = None

    if sucursal is not None:
        grupos = pos_service.listar_grupos(db, sucursal.id)
        if grupo_id is not None:
            grupo = pos_service.obtener_grupo(db, grupo_id, sucursal.id)
        if grupo is not None:
            sesiones = pos_service.listar_sesiones(db, grupo.id)
            if sesion_id is not None:
                sesion = pos_service.obtener_sesion(db, sesion_id, grupo.id)
            if sesion is None:
                sesion = pos_service.sesion_de_hoy(db, grupo.id)
            if sesion is not None:
                alumnos, resumen = pos_service.listar_roster(
                    db,
                    grupo.id,
                    sesion.id,
                )

    return templates.TemplateResponse(
        request=request,
        name="pos.html",
        context={
            "sucursales": sucursales,
            "sucursal": sucursal,
            "grupos": grupos,
            "grupo": grupo,
            "sesiones": sesiones,
            "sesion": sesion,
            "alumnos": alumnos,
            "resumen": resumen,
        },
    )


@router.post("/sesiones")
def abrir_sesion_hoy(
    grupo_id: Annotated[int, Query(ge=1)],
    db: Session = Depends(get_db),
) -> RedirectResponse:
    grupo = pos_service.obtener_grupo_activo(db, grupo_id)
    if grupo is None:
        return RedirectResponse(url="/pos", status_code=303)

    sesion = pos_service.abrir_sesion_hoy(db, grupo)
    return RedirectResponse(
        url=(
            f"/pos?sucursal_id={grupo.sucursal_id}"
            f"&grupo_id={grupo.id}"
            f"&sesion_id={sesion.id}"
        ),
        status_code=303,
    )
