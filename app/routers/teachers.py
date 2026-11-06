from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlencode

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path as PathParam,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import APP_NAME
from app.core.database import get_db
from app.core.format import (
    formato_fecha,
    formato_fecha_hora,
    formato_fecha_larga,
)
from app.services import photos
from app.services import teachers as teachers_service

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.filters["fecha"] = formato_fecha
templates.env.filters["fecha_hora"] = formato_fecha_hora
templates.env.filters["fecha_larga"] = formato_fecha_larga
templates.env.globals["app_name"] = APP_NAME

router = APIRouter(prefix="/maestros", tags=["maestros"])


def _destino(ruta: str, **params: str) -> RedirectResponse:
    return RedirectResponse(url=f"{ruta}?{urlencode(params)}", status_code=303)


@router.get("", response_class=HTMLResponse)
def mostrar_maestros(
    request: Request,
    q: Annotated[str | None, Query(max_length=120)] = None,
    estado: Annotated[
        Literal["activo", "inactivo", "todos"],
        Query(),
    ] = "activo",
    actualizado: Annotated[bool, Query()] = False,
    error: Annotated[str | None, Query(max_length=300)] = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    response = templates.TemplateResponse(
        request=request,
        name="teachers/index.html",
        context={
            "maestros": teachers_service.listar_maestros(
                db,
                q=q,
                estado=estado,
            ),
            "q": q or "",
            "estado": estado,
            "actualizado": actualizado,
            "error": error,
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/nuevo", response_class=HTMLResponse)
def formulario_nuevo_maestro(
    request: Request,
    error: Annotated[str | None, Query(max_length=300)] = None,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="teachers/form.html",
        context={"maestro": None, "error": error},
    )


@router.post("", response_model=None)
def crear_maestro(
    nombre: Annotated[str, Form(max_length=120)],
    fecha_nacimiento: Annotated[str | None, Form(max_length=10)] = None,
    telefono: Annotated[str | None, Form(max_length=40)] = None,
    correo: Annotated[str | None, Form(max_length=160)] = None,
    direccion: Annotated[str | None, Form(max_length=240)] = None,
    especialidad: Annotated[str | None, Form(max_length=120)] = None,
    fecha_ingreso: Annotated[str | None, Form(max_length=10)] = None,
    contacto_emergencia: Annotated[str | None, Form(max_length=200)] = None,
    foto: Annotated[UploadFile | None, File()] = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        maestro = teachers_service.crear_maestro(
            db,
            nombre=nombre,
            fecha_nacimiento=fecha_nacimiento,
            telefono=telefono,
            correo=correo,
            direccion=direccion,
            especialidad=especialidad,
            fecha_ingreso=fecha_ingreso,
            contacto_emergencia=contacto_emergencia,
            foto=foto,
        )
    except (teachers_service.TeacherError, photos.PhotoError) as exc:
        return _destino("/maestros/nuevo", error=str(exc))
    return _destino(f"/maestros/{maestro.id}", creado="1")


@router.get("/{maestro_id}", response_class=HTMLResponse)
def mostrar_maestro(
    maestro_id: Annotated[int, PathParam(ge=1)],
    request: Request,
    creado: Annotated[bool, Query()] = False,
    actualizado: Annotated[bool, Query()] = False,
    error: Annotated[str | None, Query(max_length=300)] = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    ficha = teachers_service.obtener_ficha(db, maestro_id)
    if ficha is None:
        return RedirectResponse(url="/maestros", status_code=303)
    response = templates.TemplateResponse(
        request=request,
        name="teachers/detail.html",
        context={
            "ficha": ficha,
            "creado": creado,
            "actualizado": actualizado,
            "error": error,
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/{maestro_id}/editar", response_class=HTMLResponse)
def formulario_editar_maestro(
    maestro_id: Annotated[int, PathParam(ge=1)],
    request: Request,
    error: Annotated[str | None, Query(max_length=300)] = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    maestro = teachers_service.obtener_maestro(db, maestro_id)
    if maestro is None:
        return RedirectResponse(url="/maestros", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="teachers/form.html",
        context={"maestro": maestro, "error": error},
    )


@router.post("/{maestro_id}", response_model=None)
def actualizar_maestro(
    maestro_id: Annotated[int, PathParam(ge=1)],
    nombre: Annotated[str, Form(max_length=120)],
    fecha_nacimiento: Annotated[str | None, Form(max_length=10)] = None,
    telefono: Annotated[str | None, Form(max_length=40)] = None,
    correo: Annotated[str | None, Form(max_length=160)] = None,
    direccion: Annotated[str | None, Form(max_length=240)] = None,
    especialidad: Annotated[str | None, Form(max_length=120)] = None,
    fecha_ingreso: Annotated[str | None, Form(max_length=10)] = None,
    contacto_emergencia: Annotated[str | None, Form(max_length=200)] = None,
    quitar_foto: Annotated[str | None, Form()] = None,
    foto: Annotated[UploadFile | None, File()] = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        teachers_service.actualizar_maestro(
            db,
            maestro_id,
            nombre=nombre,
            fecha_nacimiento=fecha_nacimiento,
            telefono=telefono,
            correo=correo,
            direccion=direccion,
            especialidad=especialidad,
            fecha_ingreso=fecha_ingreso,
            contacto_emergencia=contacto_emergencia,
            foto=foto,
            quitar_foto=quitar_foto == "1",
        )
    except (teachers_service.TeacherError, photos.PhotoError) as exc:
        return _destino(
            f"/maestros/{maestro_id}/editar",
            error=str(exc),
        )
    return _destino(f"/maestros/{maestro_id}", actualizado="1")


@router.post("/{maestro_id}/estado", response_model=None)
def cambiar_estado_maestro(
    maestro_id: Annotated[int, PathParam(ge=1)],
    activo: Annotated[str, Form()],
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        teachers_service.cambiar_estado_maestro(
            db,
            maestro_id,
            activo == "1",
        )
    except teachers_service.TeacherError as exc:
        return _destino(f"/maestros/{maestro_id}", error=str(exc))
    return _destino(f"/maestros/{maestro_id}", actualizado="1")


@router.get("/{maestro_id}/foto")
def mostrar_foto_maestro(
    maestro_id: Annotated[int, PathParam(ge=1)],
    db: Session = Depends(get_db),
) -> FileResponse:
    maestro = teachers_service.obtener_maestro(db, maestro_id)
    if maestro is None:
        raise HTTPException(status_code=404, detail="Maestro no encontrado.")
    ruta = photos.resolver_foto(maestro.foto_ruta)
    if ruta is None:
        raise HTTPException(status_code=404, detail="Foto no encontrada.")
    return FileResponse(
        ruta,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
