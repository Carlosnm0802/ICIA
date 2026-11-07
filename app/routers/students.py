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
    formato_mxn,
)
from app.services import catalog
from app.services import photos
from app.services import students as students_service

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.filters["fecha"] = formato_fecha
templates.env.filters["fecha_hora"] = formato_fecha_hora
templates.env.filters["fecha_larga"] = formato_fecha_larga
templates.env.filters["mxn"] = formato_mxn
templates.env.globals["app_name"] = APP_NAME

router = APIRouter(prefix="/alumnos", tags=["alumnos"])


def _destino(ruta: str, **params: str) -> RedirectResponse:
    return RedirectResponse(url=f"{ruta}?{urlencode(params)}", status_code=303)


@router.get("", response_class=HTMLResponse)
def mostrar_alumnos(
    request: Request,
    q: Annotated[str | None, Query(max_length=120)] = None,
    estado: Annotated[Literal["activo", "baja", "todos"], Query()] = "activo",
    grupo_id: Annotated[int | None, Query(ge=1)] = None,
    actualizado: Annotated[bool, Query()] = False,
    error: Annotated[str | None, Query(max_length=300)] = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    response = templates.TemplateResponse(
        request=request,
        name="students/index.html",
        context={
            "alumnos": students_service.listar_alumnos(
                db,
                q=q,
                estado=estado,
                grupo_id=grupo_id,
            ),
            "grupos": catalog.listar_grupos_admin(
                db,
                incluir_inactivos=True,
            ),
            "q": q or "",
            "estado": estado,
            "grupo_id": grupo_id,
            "actualizado": actualizado,
            "error": error,
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/nuevo", response_class=HTMLResponse)
def formulario_nuevo_alumno(
    request: Request,
    error: Annotated[str | None, Query(max_length=300)] = None,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="students/form.html",
        context={"alumno": None, "error": error},
    )


@router.post("", response_model=None)
def crear_alumno(
    nombre: Annotated[str, Form(max_length=120)],
    fecha_nacimiento: Annotated[str | None, Form(max_length=10)] = None,
    tutor: Annotated[str | None, Form(max_length=120)] = None,
    telefono_tutor: Annotated[str | None, Form(max_length=40)] = None,
    escuela_procedencia: Annotated[str | None, Form(max_length=200)] = None,
    alergias_notas: Annotated[str | None, Form(max_length=2000)] = None,
    personas_autorizadas: Annotated[str | None, Form(max_length=2000)] = None,
    fecha_inscripcion: Annotated[str | None, Form(max_length=10)] = None,
    foto: Annotated[UploadFile | None, File()] = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        alumno = students_service.crear_alumno(
            db,
            nombre=nombre,
            fecha_nacimiento=fecha_nacimiento,
            tutor=tutor,
            telefono_tutor=telefono_tutor,
            escuela_procedencia=escuela_procedencia,
            alergias_notas=alergias_notas,
            personas_autorizadas=personas_autorizadas,
            fecha_inscripcion=fecha_inscripcion,
            foto=foto,
        )
    except (students_service.StudentError, photos.PhotoError) as exc:
        return _destino("/alumnos/nuevo", error=str(exc))
    return _destino(f"/alumnos/{alumno.id}", creado="1")


@router.get("/{alumno_id}", response_class=HTMLResponse)
def mostrar_alumno(
    alumno_id: Annotated[int, PathParam(ge=1)],
    request: Request,
    creado: Annotated[bool, Query()] = False,
    actualizado: Annotated[bool, Query()] = False,
    grupo_agregado: Annotated[bool, Query()] = False,
    grupo_retirado: Annotated[bool, Query()] = False,
    error: Annotated[str | None, Query(max_length=300)] = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    ficha = students_service.obtener_ficha(db, alumno_id)
    if ficha is None:
        return RedirectResponse(url="/alumnos", status_code=303)

    inscritos = {
        grupo.grupo_id for grupo in ficha.grupos if grupo.activa
    }
    grupos_disponibles = [
        grupo
        for grupo in catalog.listar_grupos_admin(db)
        if grupo.id not in inscritos
    ]
    response = templates.TemplateResponse(
        request=request,
        name="students/detail.html",
        context={
            "ficha": ficha,
            "grupos_disponibles": grupos_disponibles,
            "creado": creado,
            "actualizado": actualizado,
            "grupo_agregado": grupo_agregado,
            "grupo_retirado": grupo_retirado,
            "error": error,
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/{alumno_id}/editar", response_class=HTMLResponse)
def formulario_editar_alumno(
    alumno_id: Annotated[int, PathParam(ge=1)],
    request: Request,
    error: Annotated[str | None, Query(max_length=300)] = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    alumno = students_service.obtener_alumno(db, alumno_id)
    if alumno is None:
        return RedirectResponse(url="/alumnos", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="students/form.html",
        context={"alumno": alumno, "error": error},
    )


@router.post("/{alumno_id}", response_model=None)
def actualizar_alumno(
    alumno_id: Annotated[int, PathParam(ge=1)],
    nombre: Annotated[str, Form(max_length=120)],
    fecha_nacimiento: Annotated[str | None, Form(max_length=10)] = None,
    tutor: Annotated[str | None, Form(max_length=120)] = None,
    telefono_tutor: Annotated[str | None, Form(max_length=40)] = None,
    escuela_procedencia: Annotated[str | None, Form(max_length=200)] = None,
    alergias_notas: Annotated[str | None, Form(max_length=2000)] = None,
    personas_autorizadas: Annotated[str | None, Form(max_length=2000)] = None,
    fecha_inscripcion: Annotated[str | None, Form(max_length=10)] = None,
    quitar_foto: Annotated[str | None, Form()] = None,
    foto: Annotated[UploadFile | None, File()] = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        students_service.actualizar_alumno(
            db,
            alumno_id,
            nombre=nombre,
            fecha_nacimiento=fecha_nacimiento,
            tutor=tutor,
            telefono_tutor=telefono_tutor,
            escuela_procedencia=escuela_procedencia,
            alergias_notas=alergias_notas,
            personas_autorizadas=personas_autorizadas,
            fecha_inscripcion=fecha_inscripcion,
            foto=foto,
            quitar_foto=quitar_foto == "1",
        )
    except (students_service.StudentError, photos.PhotoError) as exc:
        return _destino(
            f"/alumnos/{alumno_id}/editar",
            error=str(exc),
        )
    return _destino(f"/alumnos/{alumno_id}", actualizado="1")


@router.post("/{alumno_id}/estado", response_model=None)
def cambiar_estado_alumno(
    alumno_id: Annotated[int, PathParam(ge=1)],
    estado: Annotated[str, Form()],
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        students_service.cambiar_estado_alumno(db, alumno_id, estado)
    except students_service.StudentError as exc:
        return _destino(f"/alumnos/{alumno_id}", error=str(exc))
    return _destino(f"/alumnos/{alumno_id}", actualizado="1")


@router.post("/{alumno_id}/grupos", response_model=None)
def agregar_grupo(
    alumno_id: Annotated[int, PathParam(ge=1)],
    grupo_id: Annotated[int, Form(ge=1)],
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        students_service.agregar_grupo(db, alumno_id, grupo_id)
    except students_service.StudentError as exc:
        return _destino(f"/alumnos/{alumno_id}", error=str(exc))
    return _destino(f"/alumnos/{alumno_id}", grupo_agregado="1")


@router.post(
    "/{alumno_id}/grupos/{inscripcion_id}/baja",
    response_model=None,
)
def dar_baja_grupo(
    alumno_id: Annotated[int, PathParam(ge=1)],
    inscripcion_id: Annotated[int, PathParam(ge=1)],
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        students_service.dar_baja_grupo(db, alumno_id, inscripcion_id)
    except students_service.StudentError as exc:
        return _destino(f"/alumnos/{alumno_id}", error=str(exc))
    return _destino(f"/alumnos/{alumno_id}", grupo_retirado="1")


@router.get("/{alumno_id}/foto")
def mostrar_foto_alumno(
    alumno_id: Annotated[int, PathParam(ge=1)],
    db: Session = Depends(get_db),
) -> FileResponse:
    alumno = students_service.obtener_alumno(db, alumno_id)
    if alumno is None:
        raise HTTPException(status_code=404, detail="Alumno no encontrado.")
    ruta = photos.resolver_foto(alumno.foto_ruta)
    if ruta is None:
        raise HTTPException(status_code=404, detail="Foto no encontrada.")
    return FileResponse(
        ruta,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
