# ICIA

**Sistema de gestión para escuela de Robótica e Inglés**

Aplicación web local para operar una academia en 4 sucursales: cobro de clases,
asistencia, tickets térmicos, deudas, reposiciones, grupos, docentes y respaldos.
Diseñada para una sola persona, una laptop Windows de 8 GB y funcionamiento
**100 % sin internet**.

---

## Estado del proyecto

| Fase | Alcance | Estado |
| --- | --- | --- |
| 1 | Esqueleto, SQLite WAL, modelos, migraciones y respaldo | Completada |
| 2 | Cobro Express, folios atómicos y tickets térmicos | Completada |
| 3 | Dashboard, deudas y reposiciones | Completada |
| 4 | Grupos, sesiones, suplencias, pago a maestros y CRUD de personas | Completada |
| 5 | Empaquetado y puesta en marcha en Windows | Preparación local; validación física pendiente |

La Fase 5 ya tiene listos el launcher, el paquete PyInstaller, el creador del
acceso directo, la parada ordenada y el respaldo/restauración. Falta validar en
la laptop del dueño:

- Compilación real y revisión de antivirus.
- Modelo y ancho de la impresora térmica (58 u 80 mm).
- Impresión de 3 tickets consecutivos sin diálogo.
- Restauración desde USB en una carpeta limpia.
- Caso base físico de 35 alumnos con total de **$4,900.00 MXN**.

Estado de pruebas actual: **264 passed**.

---

## Funcionalidades

- **Cobro Express:** asistencia + pago + folio en una sola transacción atómica.
- **Folios únicos por sucursal:** formato `REF-0001`; nunca se reutilizan.
- **Tickets térmicos:** HTML para 58/80 mm, reimpresión por folio y descarga.
- **Deudas:** alumnos que asistieron sin pagar, con cobro posterior y ticket.
- **Reposiciones:** faltas con clase pagada y reposición en otro grupo sin cobro nuevo.
- **Dashboard:** cobrado hoy, cobrado en la semana, deudas y alumnos activos.
- **Grupos y sesiones:** horarios, bloques de materia, cancelación, sesión extra y suplencias.
- **Pago a maestros:** marca pagado/pendiente por sesión, individual o en lote.
- **Alumnos y maestros:** ficha, foto local, baja conservando historial.
- **Asistencia:** consulta por grupo y fechas, con exportación CSV.
- **Respaldos:** ZIP con base, fotos y manifiesto; restauración con respaldo de seguridad.

---

## Stack

| Capa | Tecnología |
| --- | --- |
| Lenguaje | Python 3.12 |
| Servidor | FastAPI + Uvicorn en `127.0.0.1:8000` |
| ORM y migraciones | SQLAlchemy 2 + Alembic |
| Base de datos | SQLite en modo WAL |
| Plantillas | Jinja2 |
| Frontend | HTML, CSS propio y JavaScript vanilla; Chart.js local |
| Contraseña | bcrypt |
| Impresión | HTML `@media print` + Chrome/Edge con `--kiosk-printing` |
| Empaquetado | PyInstaller |

No se usa Node, Docker, CDN ni servicios externos en tiempo de ejecución.
Los montos se guardan como enteros en centavos.

---

## Requisitos

**Desarrollo**

- Python 3.12
- Chrome o Edge para probar la impresión en modo kiosco

**Producción**

- Windows 10/11 en laptop de 8 GB
- Chrome o Edge instalado
- Impresora térmica de 58 u 80 mm (pendiente de confirmar)

---

## Instalación para desarrollo

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
```

Crear la base y cargar los datos semilla:

```bash
python -m alembic upgrade head
python -m app.services.seed
```

El seed crea 4 sucursales (TOT, OCO, PON, REF), 2 maestros, el grupo de El Refugio
con 35 alumnos y precio de $140 por sesión.

---

## Ejecución

### Modo normal (recomendado)

```bash
python -m app.launcher
```

El launcher aplica migraciones, inicia Uvicorn en `127.0.0.1:8000`, espera el
servidor y abre el navegador en modo aplicación. Para detenerlo:

```bash
python -m app.stop
```

### Solo servidor (desarrollo)

```bash
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Primer acceso

La primera vez, `/login` muestra el modo de configuración para crear la
contraseña del dueño. Después de crearla, el acceso queda protegido con bcrypt.

---

## Uso básico

1. Iniciar ICIA y entrar con la contraseña.
2. Elegir sucursal, grupo y sesión en **Cobro**.
3. Cobrar con teclado:
   - `Espacio`: cobrar con el método seleccionado.
   - `F1`: cobrar en efectivo.
   - `F2`: cobrar por transferencia.
   - `F3`: marcar “asistió sin pagar” (genera deuda).
   - Flechas: moverse entre alumnos.
   - `Esc`: limpiar selección.
4. Consultar deudas, reposiciones y pagos a maestros desde el menú lateral.
5. Configurar ancho de ticket, respaldo y restauración en **Configuración**.

---

## Configuración

Variables de entorno opcionales:

| Variable | Valor por defecto | Uso |
| --- | --- | --- |
| `ICIA_HOST` | `127.0.0.1` | Interfaz de red |
| `ICIA_PORT` | `8000` | Puerto local |
| `ICIA_DATA_DIR` | `data/` | Carpeta de datos |
| `ICIA_DB_PATH` | `data/icia.db` | Ruta de la base |
| `ICIA_PHOTOS_DIR` | `data/photos/` | Fotos locales |
| `ICIA_BACKUP_DIR` | `data/backups/` | Respaldos |
| `ICIA_SESSION_HOURS` | `12` | Duración de la sesión |
| `ICIA_SESSION_HORIZON_WEEKS` | `8` | Horizonte de generación de sesiones |
| `ICIA_TICKET_ANCHO_MM` | `80` | Ancho del ticket (58 u 80) |

El ancho del ticket también se puede cambiar desde la interfaz y queda guardado
en la base.

---

## Impresión térmica

- Configurar la impresora como predeterminada en Windows.
- Elegir 58 u 80 mm en **Configuración**.
- Usar **Configuración → Imprimir ticket de prueba**.
- La impresión silenciosa requiere abrir ICIA con el acceso directo, porque el
  navegador se inicia con `--kiosk-printing`.
- Sin impresora física se puede validar el diseño con “Guardar como PDF”, pero
  eso no confirma la ausencia del diálogo de impresión.

---

## Respaldos y restauración

- El respaldo completo genera un ZIP con `icia.db`, `manifest.json` y `photos/`.
- Se puede guardar en una carpeta de la USB.
- La restauración se prepara desde **Configuración** y se aplica al reiniciar
  ICIA, después de cerrarlo con `detener_icia.bat`.
- Antes de restaurar se crea un respaldo de seguridad automático.
- No copiar `icia.db` manualmente con el sistema en ejecución.

---

## Pruebas

```bash
python -m pytest -q
```

Cubren cobro atómico, folios, tickets, deudas, reposiciones, dashboard, grupos,
sesiones, suplencias, nómina por sesión, CRUD, respaldo/restauración y el caso
base de 35 alumnos con total de $4,900.

---

## Empaquetado para Windows

La compilación debe hacerse en Windows:

```bat
py -3.12 -m venv .venv
packaging\build_windows.bat
```

Después:

1. Copiar la carpeta `dist\` completa a `C:\ICIA` (no a `Program Files`).
2. Abrir `C:\ICIA\crear_acceso_directo.vbs` para crear el acceso **ICIA** en el
   Escritorio y el Menú Inicio.
3. Iniciar con el acceso directo; no se abre ninguna terminal.

El paquete incluye `ICIA.exe`, `iniciar_icia.vbs`, `detener_icia.bat`,
`run_app.bat` y el creador del acceso directo.

---

## Estructura del proyecto

```text
ICIA/
├── app/
│   ├── main.py              # App FastAPI y routers
│   ├── launcher.py          # Arranque, navegador y parada ordenada
│   ├── stop.py              # Detención del servidor
│   ├── core/                # Configuración, base de datos y seguridad
│   ├── models/              # Modelos SQLAlchemy
│   ├── routers/             # Endpoints por módulo
│   ├── services/            # Lógica de negocio
│   ├── templates/           # Vistas Jinja2
│   └── static/              # CSS, JS y vendor local (Chart.js, fuentes)
├── alembic/                 # Migraciones
├── schemas/                 # Contrato SQL de referencia
├── packaging/               # PyInstaller y scripts de Windows
├── tests/                   # Suite pytest
├── data/                    # Base, fotos, respaldos y logs (no se versiona)
├── docs/                    # Acta de prueba de Fase 5
├── requirements.txt
└── run_app.bat
```

---

## Documentación

- `docs/MANUAL_USUARIO.md` — manual de uso para el dueño.
- `PRD.md` — requisitos de producto y reglas de negocio.
- `ARCHITECTURE.md` — arquitectura, base de datos y flujos.
- `DESIGN.md` — tokens y componentes visuales.
- `ROADMAP_TASKS.md` — avance por fases y tareas pendientes.
- `docs/ACTA_PRUEBA_FASE5.md` — preparación y checklist de puesta en marcha.
- `CHANGELOG.md` — historial de versiones y cambios.
- `LICENSE` — aviso de uso privado y propietario.

---

## Limitaciones conocidas

- La validación física en Windows, la impresora real y la restauración desde USB
  siguen pendientes.
- El ancho y modelo de la impresora térmica no están confirmados.
- Un solo usuario, sin roles ni acceso remoto.
- Sin sincronización en la nube ni uso desde varias computadoras.
- No calcula sueldos; solo marca pagos por sesión.
- No hay importación masiva desde Excel.
- Datos de menores: mantener la laptop y los respaldos protegidos.

---

## Licencia

Software propietario de uso privado. Consulta `LICENSE`. No es software de
código abierto.
