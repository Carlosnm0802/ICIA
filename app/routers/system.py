from __future__ import annotations

import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import APP_NAME
from app.core.database import get_db
from app.core.format import formato_fecha, formato_fecha_hora, formato_mxn
from app.models import Configuracion
from app.services import backup_service, restore_service, thermal_printer

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.filters["fecha"] = formato_fecha
templates.env.filters["fecha_hora"] = formato_fecha_hora
templates.env.filters["mxn"] = formato_mxn
templates.env.globals["app_name"] = APP_NAME

router = APIRouter(prefix="/configuracion", tags=["configuracion"])
MAX_BACKUP_BYTES = 512 * 1024 * 1024
CONFIG_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def _destino(ruta: str, **params: str) -> RedirectResponse:
    return RedirectResponse(url=f"{ruta}?{urlencode(params)}", status_code=303)


def _guardar(db: Session, clave: str, valor: str) -> None:
    instante = datetime.now().strftime(CONFIG_TIMESTAMP_FORMAT)
    registro = db.get(Configuracion, clave)
    if registro is None:
        db.add(
            Configuracion(
                clave=clave,
                valor=valor,
                actualizado_en=instante,
            )
        )
    else:
        registro.valor = valor
        registro.actualizado_en = instante
    db.commit()


@router.get("", response_class=HTMLResponse)
def mostrar_configuracion(
    request: Request,
    guardado: Annotated[bool, Query()] = False,
    respaldo: Annotated[str | None, Query(max_length=300)] = None,
    restauracion: Annotated[bool, Query()] = False,
    error: Annotated[str | None, Query(max_length=500)] = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    response = templates.TemplateResponse(
        request=request,
        name="system/settings.html",
        context={
            "ancho_mm": thermal_printer.obtener_ancho_ticket(db),
            "ruta_respaldo": str(backup_service.ruta_respaldo(db)),
            "ultimo_respaldo": backup_service.ultimo_respaldo(db),
            "recordatorio": backup_service.recordatorio_respaldo(db),
            "pendiente": restore_service.pending_restore(),
            "guardado": guardado,
            "respaldo": respaldo,
            "restauracion": restauracion,
            "error": error,
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/impresion", response_model=None)
def guardar_impresion(
    ancho_mm: Annotated[int, Form()],
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if ancho_mm not in (58, 80):
        return _destino(
            "/configuracion",
            error="El ancho del ticket debe ser 58 u 80 mm.",
        )
    _guardar(db, "ticket_ancho_mm", str(ancho_mm))
    return _destino("/configuracion", guardado="1")


@router.post("/respaldo/ruta", response_model=None)
def guardar_ruta_respaldo(
    ruta_respaldo: Annotated[str | None, Form(max_length=300)] = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        backup_service.guardar_ruta_respaldo(db, ruta_respaldo)
        db.commit()
    except backup_service.BackupError as exc:
        db.rollback()
        return _destino("/configuracion", error=str(exc))
    return _destino("/configuracion", guardado="1")


@router.post("/respaldo", response_model=None)
def crear_respaldo(db: Session = Depends(get_db)) -> RedirectResponse:
    try:
        resultado = backup_service.backup_completo_database(
            db,
            backup_service.ruta_respaldo(db),
        )
        db.commit()
    except backup_service.BackupError as exc:
        db.rollback()
        return _destino("/configuracion", error=str(exc))
    return _destino(
        "/configuracion",
        respaldo=resultado.destination_path.name,
    )


@router.post("/restaurar", response_model=None)
def preparar_restauracion(
    archivo: Annotated[UploadFile, File()],
) -> RedirectResponse:
    nombre = (archivo.filename or "").lower()
    if not nombre.endswith(".zip"):
        return _destino(
            "/configuracion",
            error="Selecciona un respaldo completo en formato ZIP.",
        )

    temporal = tempfile.NamedTemporaryFile(
        suffix=".zip",
        delete=False,
    )
    try:
        copiado = 0
        while chunk := archivo.file.read(1024 * 1024):
            copiado += len(chunk)
            if copiado > MAX_BACKUP_BYTES:
                return _destino(
                    "/configuracion",
                    error="El respaldo es demasiado grande.",
                )
            temporal.write(chunk)
        temporal.close()
        restore_service.stage_restore(Path(temporal.name))
    except restore_service.RestoreError as exc:
        return _destino("/configuracion", error=str(exc))
    except OSError as exc:
        return _destino(
            "/configuracion",
            error=f"No se pudo leer el respaldo: {exc}",
        )
    finally:
        temporal.close()
        Path(temporal.name).unlink(missing_ok=True)

    return _destino("/configuracion", restauracion="1")


@router.get("/ticket-prueba", response_class=HTMLResponse)
def ticket_prueba(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    ticket = thermal_printer.TicketData(
        pago_id=0,
        folio="PRUEBA",
        estado="vigente",
        estado_etiqueta="Vigente",
        fecha=datetime.now().strftime(CONFIG_TIMESTAMP_FORMAT),
        alumno="Alumno de prueba",
        sucursal="El Refugio",
        sucursal_direccion="Ticket de prueba de impresión",
        sucursal_telefono=None,
        grupo="Jueves 3-5 PM",
        materias=("Inglés", "Robótica"),
        sesion_fecha=date.today().isoformat(),
        monto_centavos=14000,
        metodo="efectivo",
        metodo_etiqueta="Efectivo",
        ancho_mm=thermal_printer.obtener_ancho_ticket(db),
    )
    response = templates.TemplateResponse(
        request=request,
        name="ticket.html",
        context={
            "ticket": ticket,
            "auto": True,
            "prueba": True,
            "descargar": False,
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response
