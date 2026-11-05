from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Path as PathParam, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import APP_NAME
from app.core.database import get_db
from app.core.format import formato_fecha, formato_mxn, formato_pesos
from app.services import catalog

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.filters["mxn"] = formato_mxn
templates.env.filters["fecha"] = formato_fecha
templates.env.filters["pesos"] = formato_pesos
templates.env.globals["app_name"] = APP_NAME

router = APIRouter(prefix="/grupos", tags=["grupos"])
sucursales_router = APIRouter(prefix="/sucursales", tags=["sucursales"])


def _destino(ruta: str, **params: str) -> RedirectResponse:
    return RedirectResponse(url=f"{ruta}?{urlencode(params)}", status_code=303)


def _bloques_desde_formulario(
    materias: list[str],
    duraciones: list[int],
    maestros: list[int],
) -> list[catalog.BloqueForm]:
    bloques = []
    for indice, (materia, duracion, maestro) in enumerate(
        zip(materias, duraciones, maestros, strict=True),
        start=1,
    ):
        bloques.append(
            catalog.BloqueForm(
                materia=materia,
                orden=indice,
                duracion_minutos=duracion,
                maestro_id=maestro,
            )
        )
    return bloques


def _contexto_formulario_grupo(
    request: Request,
    db: Session,
    grupo: catalog.GrupoEdicion | None = None,
    error: str | None = None,
) -> dict:
    return {
        "sucursales": catalog.listar_sucursales_admin(db),
        "maestros": catalog.listar_maestros_activos(db),
        "dias_semana": catalog.DIAS_SEMANA,
        "materias": catalog.MATERIAS,
        "detalle": grupo,
        "error": error,
    }


@sucursales_router.get("", response_class=HTMLResponse)
def mostrar_sucursales(
    request: Request,
    creada: Annotated[bool, Query()] = False,
    actualizada: Annotated[bool, Query()] = False,
    error: Annotated[str | None, Query(max_length=300)] = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    response = templates.TemplateResponse(
        request=request,
        name="branches/index.html",
        context={
            "sucursales": catalog.listar_sucursales_admin(db),
            "creada": creada,
            "actualizada": actualizada,
            "error": error,
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@sucursales_router.get("/nueva", response_class=HTMLResponse)
def formulario_nueva_sucursal(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="branches/form.html",
        context={"sucursal": None, "error": None, "puede_prefijo": True},
    )


@sucursales_router.get("/{sucursal_id}/editar", response_class=HTMLResponse)
def formulario_editar_sucursal(
    sucursal_id: Annotated[int, PathParam(ge=1)],
    request: Request,
    error: Annotated[str | None, Query(max_length=300)] = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    sucursal = catalog.obtener_sucursal(db, sucursal_id)
    if sucursal is None:
        return RedirectResponse(url="/sucursales", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="branches/form.html",
        context={
            "sucursal": sucursal,
            "error": error,
            "puede_prefijo": not catalog.sucursal_tiene_pagos(db, sucursal.id),
        },
    )


@sucursales_router.post("", response_model=None)
def crear_sucursal(
    nombre: Annotated[str, Form(max_length=120)],
    prefijo_folio: Annotated[str, Form(max_length=8)],
    direccion: Annotated[str | None, Form(max_length=200)] = None,
    telefono: Annotated[str | None, Form(max_length=40)] = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        catalog.crear_sucursal(
            db,
            nombre=nombre,
            prefijo=prefijo_folio,
            direccion=direccion,
            telefono=telefono,
        )
    except catalog.CatalogError as exc:
        return _destino("/sucursales", error=str(exc))
    return _destino("/sucursales", creada="1")


@sucursales_router.post("/{sucursal_id}", response_model=None)
def actualizar_sucursal(
    sucursal_id: Annotated[int, PathParam(ge=1)],
    nombre: Annotated[str, Form(max_length=120)],
    prefijo_folio: Annotated[str, Form(max_length=8)],
    direccion: Annotated[str | None, Form(max_length=200)] = None,
    telefono: Annotated[str | None, Form(max_length=40)] = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        catalog.actualizar_sucursal(
            db,
            sucursal_id,
            nombre=nombre,
            prefijo=prefijo_folio,
            direccion=direccion,
            telefono=telefono,
        )
    except catalog.CatalogError as exc:
        return _destino(
            f"/sucursales/{sucursal_id}/editar",
            error=str(exc),
        )
    return _destino("/sucursales", actualizada="1")


@sucursales_router.post("/{sucursal_id}/estado", response_model=None)
def cambiar_estado_sucursal(
    sucursal_id: Annotated[int, PathParam(ge=1)],
    activa: Annotated[str, Form()],
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        catalog.cambiar_estado_sucursal(
            db,
            sucursal_id,
            activa=activa == "1",
        )
    except catalog.CatalogError as exc:
        return _destino("/sucursales", error=str(exc))
    return _destino("/sucursales", actualizada="1")


@router.get("", response_class=HTMLResponse)
def mostrar_grupos(
    request: Request,
    sucursal_id: Annotated[int | None, Query(ge=1)] = None,
    inactivos: Annotated[bool, Query()] = False,
    creado: Annotated[bool, Query()] = False,
    actualizado: Annotated[bool, Query()] = False,
    error: Annotated[str | None, Query(max_length=300)] = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    response = templates.TemplateResponse(
        request=request,
        name="groups/index.html",
        context={
            "grupos": catalog.listar_grupos_admin(
                db,
                sucursal_id=sucursal_id,
                incluir_inactivos=inactivos,
            ),
            "sucursales": catalog.listar_sucursales_admin(db),
            "sucursal_id": sucursal_id,
            "inactivos": inactivos,
            "creado": creado,
            "actualizado": actualizado,
            "error": error,
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/nuevo", response_class=HTMLResponse)
def formulario_nuevo_grupo(
    request: Request,
    error: Annotated[str | None, Query(max_length=300)] = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="groups/form.html",
        context=_contexto_formulario_grupo(request, db, error=error),
    )


@router.get("/{grupo_id}/editar", response_class=HTMLResponse)
def formulario_editar_grupo(
    grupo_id: Annotated[int, PathParam(ge=1)],
    request: Request,
    error: Annotated[str | None, Query(max_length=300)] = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    detalle = catalog.obtener_grupo_detalle(db, grupo_id)
    if detalle is None:
        return RedirectResponse(url="/grupos", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="groups/form.html",
        context=_contexto_formulario_grupo(request, db, detalle, error),
    )


@router.post("", response_model=None)
def crear_grupo(
    request: Request,
    sucursal_id: Annotated[int, Form(ge=1)],
    nombre: Annotated[str, Form(max_length=120)],
    dias_semana: Annotated[list[str], Form()],
    hora_inicio: Annotated[str, Form(max_length=5)],
    hora_fin: Annotated[str, Form(max_length=5)],
    precio: Annotated[str, Form(max_length=20)],
    bloque_materia: Annotated[list[str], Form()],
    bloque_duracion: Annotated[list[int], Form()],
    bloque_maestro: Annotated[list[int], Form()],
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        bloques = _bloques_desde_formulario(
            bloque_materia,
            bloque_duracion,
            bloque_maestro,
        )
        catalog.crear_grupo(
            db,
            sucursal_id=sucursal_id,
            nombre=nombre,
            dias_semana=dias_semana,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
            precio=precio,
            bloques=bloques,
        )
    except (catalog.CatalogError, ValueError) as exc:
        return _destino("/grupos/nuevo", error=str(exc))
    return _destino("/grupos", creado="1")


@router.post("/{grupo_id}", response_model=None)
def actualizar_grupo(
    grupo_id: Annotated[int, PathParam(ge=1)],
    sucursal_id: Annotated[int, Form(ge=1)],
    nombre: Annotated[str, Form(max_length=120)],
    dias_semana: Annotated[list[str], Form()],
    hora_inicio: Annotated[str, Form(max_length=5)],
    hora_fin: Annotated[str, Form(max_length=5)],
    precio: Annotated[str, Form(max_length=20)],
    bloque_materia: Annotated[list[str], Form()],
    bloque_duracion: Annotated[list[int], Form()],
    bloque_maestro: Annotated[list[int], Form()],
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        bloques = _bloques_desde_formulario(
            bloque_materia,
            bloque_duracion,
            bloque_maestro,
        )
        catalog.actualizar_grupo(
            db,
            grupo_id,
            sucursal_id=sucursal_id,
            nombre=nombre,
            dias_semana=dias_semana,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
            precio=precio,
            bloques=bloques,
        )
    except (catalog.CatalogError, ValueError) as exc:
        return _destino(f"/grupos/{grupo_id}/editar", error=str(exc))
    return _destino("/grupos", actualizado="1")


@router.post("/{grupo_id}/estado", response_model=None)
def cambiar_estado_grupo(
    grupo_id: Annotated[int, PathParam(ge=1)],
    activo: Annotated[str, Form()],
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        catalog.cambiar_estado_grupo(db, grupo_id, activo=activo == "1")
    except catalog.CatalogError as exc:
        return _destino("/grupos", error=str(exc))
    return _destino("/grupos", actualizado="1")
