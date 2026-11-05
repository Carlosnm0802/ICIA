from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import urlsplit

import bcrypt
from fastapi import Depends, Request
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.core import config
from app.core.database import get_db
from app.models import Configuracion

AUTH_HASH_KEY = "auth_password_hash"
SESSION_COOKIE = "icia_session"
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_BYTES = 72


class NoAutenticado(Exception):
    def __init__(self, next_url: str) -> None:
        super().__init__(next_url)
        self.next_url = next_url


def hash_password(password: str, rounds: int = 12) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(rounds=rounds),
    ).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("ascii"),
        )
    except (ValueError, UnicodeError):
        return False


def obtener_password_hash(db: Session) -> str | None:
    registro = db.get(Configuracion, AUTH_HASH_KEY)
    return registro.valor if registro is not None else None


def guardar_password_hash(db: Session, password_hash: str) -> None:
    registro = db.get(Configuracion, AUTH_HASH_KEY)
    if registro is None:
        db.add(Configuracion(clave=AUTH_HASH_KEY, valor=password_hash))
    else:
        registro.valor = password_hash
    db.flush()


def _firma(password_hash: str, payload: str) -> str:
    return hmac.new(
        password_hash.encode("utf-8"),
        payload.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()


def crear_token_sesion(password_hash: str, ahora: int | None = None) -> str:
    base = int(time.time()) if ahora is None else ahora
    expira = base + config.SESSION_HOURS * 3600
    payload = str(expira)
    return f"{payload}.{_firma(password_hash, payload)}"


def sesion_valida(
    cookie: str | None,
    password_hash: str | None,
    ahora: int | None = None,
) -> bool:
    if not cookie or not password_hash:
        return False
    try:
        payload, firma = cookie.split(".", 1)
        expira = int(payload)
    except (ValueError, AttributeError):
        return False

    actual = int(time.time()) if ahora is None else ahora
    if expira <= actual:
        return False
    return hmac.compare_digest(firma, _firma(password_hash, payload))


def aplicar_cookie_sesion(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=config.SESSION_HOURS * 3600,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )


def borrar_cookie_sesion(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE,
        path="/",
        httponly=True,
        samesite="lax",
    )


def destino_seguro(next_url: str | None) -> str:
    if not next_url:
        return "/dashboard"
    if (
        not next_url.startswith("/")
        or next_url.startswith("//")
        or "\\" in next_url
    ):
        return "/dashboard"
    parsed = urlsplit(next_url)
    if parsed.scheme or parsed.netloc:
        return "/dashboard"
    return next_url


def requiere_sesion(request: Request, db: Session = Depends(get_db)) -> None:
    password_hash = obtener_password_hash(db)
    db.rollback()
    if sesion_valida(request.cookies.get(SESSION_COOKIE), password_hash):
        return

    next_url = request.url.path
    if request.url.query:
        next_url = f"{next_url}?{request.url.query}"
    raise NoAutenticado(next_url)
