from app.core import config, security


def test_hash_password_no_guarda_texto_plano() -> None:
    hashed = security.hash_password("clave-segura", rounds=4)

    assert hashed != "clave-segura"
    assert hashed.startswith("$2")
    assert security.verify_password("clave-segura", hashed)
    assert not security.verify_password("otra-clave", hashed)
    assert not security.verify_password("clave-segura", "hash-invalido")


def test_token_sesion_valido_expirado_y_manipulado() -> None:
    hashed = security.hash_password("clave-segura", rounds=4)
    ahora = 1_700_000_000
    token = security.crear_token_sesion(hashed, ahora=ahora)

    assert security.sesion_valida(token, hashed, ahora=ahora)
    assert not security.sesion_valida(
        token,
        hashed,
        ahora=ahora + config.SESSION_HOURS * 3600,
    )
    assert not security.sesion_valida(f"{token}x", hashed, ahora=ahora)
    assert not security.sesion_valida(token, None, ahora=ahora)
    assert not security.sesion_valida(None, hashed, ahora=ahora)


def test_destino_seguro_solo_acepta_rutas_locales() -> None:
    assert security.destino_seguro(None) == "/dashboard"
    assert security.destino_seguro("") == "/dashboard"
    assert security.destino_seguro("/pos?sucursal_id=1") == "/pos?sucursal_id=1"
    assert security.destino_seguro("https://ejemplo.com") == "/dashboard"
    assert security.destino_seguro("//ejemplo.com") == "/dashboard"
    assert security.destino_seguro("/\\ejemplo.com") == "/dashboard"
