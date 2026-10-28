from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import APP_NAME
from app.routers import pos

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title=APP_NAME)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(pos.router)


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return (
        "<!doctype html>"
        '<html lang="es">'
        "<head>"
        '<meta charset="utf-8">'
        f"<title>{APP_NAME}</title>"
        "</head>"
        "<body>"
        f"<h1>{APP_NAME}</h1>"
        '<p><a href="/pos">Abrir Cobro Express</a></p>'
        "</body>"
        "</html>"
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": APP_NAME}
