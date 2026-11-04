from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import APP_NAME
from app.core.database import get_db

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["app_name"] = APP_NAME

router = APIRouter(tags=["auth"])


def _render_login(
    request: Request,
    *,
    modo_setup: bool,
    error: str | None = None,
    next_url: str = "",
    status_code: int = 200,
) -> HTMLResponse:
    response = templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={
            "modo_setup": modo_setup,
            "error": error,
            "next": next_url,
        },
        status_code=status_code,
    )
    response.headers["Cache-Control"] = "no-store"
    return response


def _validar_password(password: str, confirmacion: str) -> str | None:
    if not password.strip():
        return "La contraseña no puede estar vacía."
    if len(password) < security.MIN_PASSWORD_LENGTH:
        return "La contraseña debe tener al menos 8 caracteres."
    if len(password.encode("utf-8")) > security.MAX_PASSWORD_BYTES:
        return "La contraseña es demasiado larga."
    if password != confirmacion:
        return "Las contraseñas no coinciden."
    return None


@router.get("/login", response_class=HTMLResponse, response_model=None)
def mostrar_login(
    request: Request,
    next: Annotated[str | None, Query()] = None,
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    password_hash = security.obtener_password_hash(db)
    if password_hash is not None and security.sesion_valida(
        request.cookies.get(security.SESSION_COOKIE),
        password_hash,
    ):
        return RedirectResponse(
            url=security.destino_seguro(next),
            status_code=303,
        )

    return _render_login(
        request,
        modo_setup=password_hash is None,
        next_url=next or "",
    )


@router.post("/setup", response_model=None)
def configurar_password(
    request: Request,
    password: Annotated[str, Form()],
    password_confirm: Annotated[str, Form()],
    next: Annotated[str, Form()] = "",
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    if security.obtener_password_hash(db) is not None:
        raise HTTPException(
            status_code=409,
            detail="La contraseña ya está configurada.",
        )

    error = _validar_password(password, password_confirm)
    if error is not None:
        return _render_login(
            request,
            modo_setup=True,
            error=error,
            next_url=next,
            status_code=400,
        )

    password_hash = security.hash_password(password)
    security.guardar_password_hash(db, password_hash)
    db.commit()

    response = RedirectResponse(
        url=security.destino_seguro(next),
        status_code=303,
    )
    security.aplicar_cookie_sesion(
        response,
        security.crear_token_sesion(password_hash),
    )
    return response


@router.post("/login", response_model=None)
def iniciar_sesion(
    request: Request,
    password: Annotated[str, Form()],
    next: Annotated[str, Form()] = "",
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    password_hash = security.obtener_password_hash(db)
    if password_hash is None:
        return RedirectResponse(url="/login", status_code=303)

    if not security.verify_password(password, password_hash):
        return _render_login(
            request,
            modo_setup=False,
            error="Contraseña incorrecta.",
            next_url=next,
            status_code=401,
        )

    response = RedirectResponse(
        url=security.destino_seguro(next),
        status_code=303,
    )
    security.aplicar_cookie_sesion(
        response,
        security.crear_token_sesion(password_hash),
    )
    return response


@router.post("/logout")
def cerrar_sesion() -> RedirectResponse:
    response = RedirectResponse(url="/login", status_code=303)
    security.borrar_cookie_sesion(response)
    return response
