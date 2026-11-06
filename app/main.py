from pathlib import Path
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import APP_NAME
from app.core.security import NoAutenticado, requiere_sesion
from app.routers import auth, dashboard, debts, groups, payroll, pos

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title=APP_NAME)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(auth.router)
app.include_router(dashboard.router, dependencies=[Depends(requiere_sesion)])
app.include_router(debts.router, dependencies=[Depends(requiere_sesion)])
app.include_router(
    debts.reposiciones_router,
    dependencies=[Depends(requiere_sesion)],
)
app.include_router(groups.router, dependencies=[Depends(requiere_sesion)])
app.include_router(
    groups.sucursales_router,
    dependencies=[Depends(requiere_sesion)],
)
app.include_router(payroll.router, dependencies=[Depends(requiere_sesion)])
app.include_router(pos.router, dependencies=[Depends(requiere_sesion)])


@app.exception_handler(NoAutenticado)
async def _redirigir_login(
    _request: Request,
    exc: NoAutenticado,
) -> RedirectResponse:
    destino = f"/login?{urlencode({'next': exc.next_url})}"
    return RedirectResponse(url=destino, status_code=303)


@app.get("/", dependencies=[Depends(requiere_sesion)])
def home() -> RedirectResponse:
    return RedirectResponse(url="/dashboard", status_code=303)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": APP_NAME}
