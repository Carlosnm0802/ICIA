from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core import config, security
from app.core.database import build_engine, get_db
from app.core.security import requiere_sesion
from app.main import app
from app.models import Configuracion

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "clave-segura"


def _config(database_path: Path) -> Config:
    configuracion = Config(str(PROJECT_ROOT / "alembic.ini"))
    configuracion.set_main_option("prepend_sys_path", str(PROJECT_ROOT))
    configuracion.set_main_option(
        "sqlalchemy.url",
        f"sqlite:///{database_path.as_posix()}",
    )
    return configuracion


@pytest.fixture
def auth_app(
    tmp_path: Path,
) -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    database_path = tmp_path / "auth.db"
    command.upgrade(_config(database_path), "head")
    engine = build_engine(database_path)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides.pop(requiere_sesion, None)
    try:
        with TestClient(app) as client:
            yield client, factory
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _configurar(
    client: TestClient,
    password: str = PASSWORD,
) -> None:
    response = client.post(
        "/setup",
        data={"password": password, "password_confirm": password},
        follow_redirects=False,
    )
    assert response.status_code == 303


def _hash_guardado(factory: sessionmaker[Session]) -> str:
    with factory() as session:
        registro = session.get(Configuracion, security.AUTH_HASH_KEY)
        assert registro is not None
        return registro.valor


def test_login_primer_uso_muestra_crear_password(
    auth_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = auth_app

    response = client.get("/login")

    assert response.status_code == 200
    assert "ICIA" in response.text
    assert "Crea la contraseña de acceso" in response.text
    assert "Guardar contraseña" in response.text
    assert response.headers["cache-control"] == "no-store"


def test_setup_guarda_hash_y_autentica(
    auth_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = auth_app

    response = client.post(
        "/setup",
        data={"password": PASSWORD, "password_confirm": PASSWORD},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "path=/" in cookie
    assert f"max-age={config.SESSION_HOURS * 3600}" in cookie

    hashed = _hash_guardado(factory)
    assert hashed != PASSWORD
    assert hashed.startswith("$2")
    assert security.verify_password(PASSWORD, hashed)
    assert client.get("/pos").status_code == 200


def test_setup_rechaza_password_corta_y_confirmacion_distinta(
    auth_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = auth_app

    corta = client.post(
        "/setup",
        data={"password": "corta", "password_confirm": "corta"},
        follow_redirects=False,
    )
    distinta = client.post(
        "/setup",
        data={"password": PASSWORD, "password_confirm": "otra-clave"},
        follow_redirects=False,
    )
    larga = "a" * 73
    demasiado_larga = client.post(
        "/setup",
        data={"password": larga, "password_confirm": larga},
        follow_redirects=False,
    )

    assert corta.status_code == 400
    assert "al menos 8 caracteres" in corta.text
    assert distinta.status_code == 400
    assert "no coinciden" in distinta.text
    assert demasiado_larga.status_code == 400
    assert "demasiado larga" in demasiado_larga.text
    with factory() as session:
        assert session.get(Configuracion, security.AUTH_HASH_KEY) is None


def test_setup_no_sobrescribe_password_existente(
    auth_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = auth_app
    _configurar(client)
    hashed = _hash_guardado(factory)

    response = client.post(
        "/setup",
        data={"password": "otra-clave", "password_confirm": "otra-clave"},
        follow_redirects=False,
    )

    assert response.status_code == 409
    assert _hash_guardado(factory) == hashed


def test_login_correcto_crea_sesion(
    auth_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = auth_app
    _configurar(client)
    client.cookies.clear()

    response = client.post(
        "/login",
        data={"password": PASSWORD, "next": "/pos"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/pos"
    assert client.cookies.get(security.SESSION_COOKIE) is not None
    assert client.get("/pos").status_code == 200


def test_login_incorrecto_no_autentica(
    auth_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = auth_app
    _configurar(client)
    client.cookies.clear()

    response = client.post(
        "/login",
        data={"password": "incorrecta"},
        follow_redirects=False,
    )

    assert response.status_code == 401
    assert "Contraseña incorrecta." in response.text
    assert client.cookies.get(security.SESSION_COOKIE) is None
    assert client.get("/pos", follow_redirects=False).status_code == 303


def test_login_sin_password_configurada_redirige_al_login(
    auth_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = auth_app

    response = client.post(
        "/login",
        data={"password": PASSWORD},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_login_con_sesion_valida_redirige(
    auth_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = auth_app
    _configurar(client)

    response = client.get("/login", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"


def test_login_respeta_next_local_y_rechaza_externo(
    auth_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = auth_app
    _configurar(client)

    local = client.post(
        "/login",
        data={"password": PASSWORD, "next": "/pos?sucursal_id=7"},
        follow_redirects=False,
    )
    assert local.status_code == 303
    assert local.headers["location"] == "/pos?sucursal_id=7"

    client.cookies.clear()
    externo = client.post(
        "/login",
        data={"password": PASSWORD, "next": "https://ejemplo.com"},
        follow_redirects=False,
    )
    assert externo.status_code == 303
    assert externo.headers["location"] == "/dashboard"

    client.cookies.clear()
    doble_slash = client.post(
        "/login",
        data={"password": PASSWORD, "next": "//ejemplo.com"},
        follow_redirects=False,
    )
    assert doble_slash.status_code == 303
    assert doble_slash.headers["location"] == "/dashboard"


def test_rutas_protegidas_redirigen_al_login(
    auth_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = auth_app

    for ruta in (
        "/",
        "/dashboard",
        "/dashboard/recaudacion",
        "/pos",
        "/pos/tickets/1",
    ):
        response = client.get(ruta, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"].startswith("/login?next=")


def test_cookie_manipulada_y_expirada_redirigen(
    auth_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = auth_app
    _configurar(client)
    hashed = _hash_guardado(factory)
    client.cookies.clear()

    client.cookies.set(security.SESSION_COOKIE, "9999999999.firma", path="/")
    assert client.get("/pos", follow_redirects=False).status_code == 303

    client.cookies.clear()
    expirada = security.crear_token_sesion(hashed, ahora=0)
    client.cookies.set(security.SESSION_COOKIE, expirada, path="/")
    assert client.get("/pos", follow_redirects=False).status_code == 303


def test_logout_elimina_la_sesion(
    auth_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = auth_app
    _configurar(client)

    response = client.post("/logout", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert client.cookies.get(security.SESSION_COOKIE) is None
    assert client.get("/pos", follow_redirects=False).status_code == 303


def test_health_y_static_siguen_publicos(
    auth_app: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = auth_app

    assert client.get("/health").status_code == 200
    assert client.get("/static/css/app.css").status_code == 200
    assert client.get("/login").status_code == 200
