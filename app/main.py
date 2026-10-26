from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.core.config import APP_NAME

app = FastAPI(title=APP_NAME)


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
        "</body>"
        "</html>"
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": APP_NAME}
