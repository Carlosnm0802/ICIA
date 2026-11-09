from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).resolve().parent.parent

datas = [
    (str(ROOT / "app" / "templates"), "app/templates"),
    (str(ROOT / "app" / "static"), "app/static"),
    (str(ROOT / "alembic"), "alembic"),
    (str(ROOT / "alembic.ini"), "."),
]
datas += collect_data_files("alembic")

hiddenimports = [
    "python_multipart",
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.dialects.sqlite.pysqlite",
    "bcrypt",
    "mako",
    "mako.template",
    "mako.runtime",
    "jinja2.ext",
    "email.mime.multipart",
    "email.mime.text",
]
hiddenimports += collect_submodules("app")
hiddenimports += collect_submodules("uvicorn")

a = Analysis(
    [str(ROOT / "run_icia.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tkinter", "IPython", "matplotlib"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ICIA",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
