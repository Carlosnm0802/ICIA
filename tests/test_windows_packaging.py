import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = [
    PROJECT_ROOT / "run_app.bat",
    PROJECT_ROOT / "iniciar_icia.vbs",
    PROJECT_ROOT / "detener_icia.bat",
    PROJECT_ROOT / "packaging" / "build_windows.bat",
    PROJECT_ROOT / "packaging" / "crear_acceso_directo.vbs",
]
PATRONES_EXTERNOS = (
    "http://",
    "https://",
    "//cdn.",
    "cdnjs",
    "unpkg",
    "jsdelivr",
    "googleapis",
    "tailwindcdn",
)


def _texto(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _assert_sin_lf_sueltos(data: bytes) -> None:
    assert b"\r\n" in data
    assert b"\n" not in data.replace(b"\r\n", b"")
    assert b"\r" not in data.replace(b"\r\n", b"")


def test_scripts_windows_usan_crlf() -> None:
    for path in SCRIPTS:
        _assert_sin_lf_sueltos(path.read_bytes())


def test_gitattributes_fuerza_crlf_en_bat_y_vbs() -> None:
    texto = _texto(PROJECT_ROOT / ".gitattributes")

    assert "*.bat text eol=crlf" in texto
    assert "*.vbs text eol=crlf" in texto


def test_run_app_delega_en_el_launcher_sin_consola() -> None:
    texto = _texto(PROJECT_ROOT / "run_app.bat")

    assert "wscript" in texto
    assert "iniciar_icia.vbs" in texto


def test_iniciar_vbs_arranca_pythonw_o_el_ejecutable() -> None:
    texto = _texto(PROJECT_ROOT / "iniciar_icia.vbs")

    assert "pythonw.exe" in texto
    assert "app.launcher" in texto
    assert "ICIA.exe" in texto


def test_detener_usa_el_modulo_stop_o_el_argumento() -> None:
    texto = _texto(PROJECT_ROOT / "detener_icia.bat")

    assert "app.stop" in texto
    assert "--detener" in texto


def test_build_windows_instala_dependencias_y_copia_scripts() -> None:
    texto = _texto(PROJECT_ROOT / "packaging" / "build_windows.bat")

    assert "requirements.txt" in texto
    assert "requirements-build.txt" in texto
    assert "PyInstaller" in texto
    assert "dist\\" in texto
    for script in (
        "run_app.bat",
        "iniciar_icia.vbs",
        "detener_icia.bat",
        "crear_acceso_directo.vbs",
    ):
        assert script in texto


def test_acceso_directo_apunta_al_iniciador_sin_consola() -> None:
    texto = _texto(PROJECT_ROOT / "packaging" / "crear_acceso_directo.vbs")

    assert "CreateShortcut" in texto
    assert 'SpecialFolders("Desktop")' in texto
    assert 'SpecialFolders("Programs")' in texto
    assert "ICIA.lnk" in texto
    assert "iniciar_icia.vbs" in texto
    assert "wscript.exe" in texto


def test_pyinstaller_spec_incluye_recursos_e_imports_criticos() -> None:
    texto = _texto(PROJECT_ROOT / "packaging" / "icia.spec")

    for fragmento in (
        "app/templates",
        "app/static",
        "alembic.ini",
        "bcrypt",
        "mako",
        "jinja2.ext",
        'name="ICIA"',
        "console=False",
    ):
        assert fragmento in texto


def test_templates_y_assets_propios_no_dependen_de_internet() -> None:
    carpetas = [
        PROJECT_ROOT / "app" / "templates",
        PROJECT_ROOT / "app" / "static" / "css",
        PROJECT_ROOT / "app" / "static" / "js",
    ]
    revisados = 0
    for carpeta in carpetas:
        for path in carpeta.rglob("*"):
            if path.suffix not in {".html", ".css", ".js"}:
                continue
            revisados += 1
            contenido = _texto(path).lower()
            for patron in PATRONES_EXTERNOS:
                assert patron not in contenido, f"{path} usa {patron}"

    assert revisados > 0


def test_referencias_estaticas_existen() -> None:
    static = PROJECT_ROOT / "app" / "static"
    referencias: set[str] = set()
    patron_url_for = re.compile(
        r"url_for\(\s*['\"]static['\"]\s*,\s*path=['\"]([^'\"]+)['\"]\s*\)"
    )
    patron_css = re.compile(r'url\("\.\./([^"]+)"\)')

    for template in (PROJECT_ROOT / "app" / "templates").rglob("*.html"):
        texto = _texto(template)
        referencias.update(patron_url_for.findall(texto))
    for hoja in (static / "css").rglob("*.css"):
        referencias.update(patron_css.findall(_texto(hoja)))

    assert referencias
    faltantes = sorted(
        referencia
        for referencia in referencias
        if not (static / referencia).is_file()
    )
    assert faltantes == []
