# ARCHITECTURE.md — Arquitectura del Sistema

Proyecto: **ICIA** — Sistema de gestión para escuela de Robótica e Inglés
Patrón: aplicación web local monolítica, offline-first, con SQLite como única fuente de verdad.

---

## 1. Principios de arquitectura

1. **Local por defecto:** el servidor escucha únicamente en `127.0.0.1:8000`. No hay servicios externos.
2. **Offline-first:** todo recurso vive en el disco; ninguna petición a CDN en tiempo de ejecución.
3. **Una fuente de verdad:** SQLite en un solo archivo (`data/icia.db`).
4. **Dinero entero:** todos los montos son `INTEGER` en centavos.
5. **Atomicidad:** asistencia, pago, folio, ticket y anulación se ejecutan en transacciones SQLite.
6. **Monolito simple:** FastAPI + Jinja2 + HTMX/Alpine.js, sin build de frontend ni Node en producción.
7. **Trazabilidad:** nada se borra; se cancela o se da de baja conservando historial.
8. **Identidad única:** toda la aplicación se presenta como `ICIA`; la constante `APP_NAME = "ICIA"` en `config.py` alimenta títulos, login, dashboard, reportes y tickets.

---

## 2. Stack técnico

| Capa | Tecnología |
| --- | --- |
| Lenguaje | Python 3.12 |
| Servidor | FastAPI + Uvicorn en `127.0.0.1:8000` |
| ORM | SQLAlchemy 2.0+ |
| Migraciones | Alembic |
| Base de datos | SQLite en modo WAL |
| Plantillas | Jinja2 + HTML5 semántico |
| Interactividad | HTMX o Alpine.js (local) |
| Gráficas | Chart.js (local) |
| Estilos | Tailwind compilado offline |
| Contraseña | argon2 o bcrypt |
| Impresión | HTML `@media print` + `--kiosk-printing`; ESC/POS opcional |
| Respaldo | SQLite Backup API hacia USB |
| Empaquetado | PyInstaller o carpeta portable + `run_app.bat` |

---

## 3. Estructura de carpetas

```text
ICIA/
├── AGENTS.md
├── PRD.md
├── ARCHITECTURE.md
├── ROADMAP_TASKS.md
├── DESIGN.md
├── schemas/
│   └── database_schema.sql
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
├── app/
│   ├── main.py                  # Creación de la app FastAPI y registro de routers
│   ├── core/
│   │   ├── config.py            # APP_NAME="ICIA", rutas, puerto, USB, moneda
│   │   ├── database.py          # Engine SQLite WAL y sesión por request
│   │   └── security.py          # Hash de contraseña, sesión/cookie local
│   ├── models/                  # Tablas SQLAlchemy
│   │   ├── academic.py          # sucursales, grupos, bloques, sesiones, alumnos
│   │   ├── billing.py           # pagos, folios, asistencias
│   │   ├── staff.py             # maestros, sesion_maestros
│   │   └── system.py            # configuración
│   ├── routers/                 # Endpoints FastAPI agrupados
│   │   ├── auth.py
│   │   ├── dashboard.py
│   │   ├── pos.py               # Cobro Express y tickets
│   │   ├── students.py
│   │   ├── teachers.py
│   │   ├── groups.py
│   │   ├── debts.py             # Deudas y reposiciones
│   │   ├── payroll.py           # Pago a maestros
│   │   └── system.py            # Respaldo USB y configuración
│   ├── services/                # Lógica de negocio pura
│   │   ├── cashier.py           # Transacción atómica de cobro y anulación
│   │   ├── folios.py            # Numeración consecutiva por sucursal
│   │   ├── thermal_printer.py   # Ticket HTML y ESC/POS
│   │   ├── backup_service.py    # SQLite Backup API hacia USB
│   │   ├── reports.py           # Consultas de dashboard, deudas y reposiciones
│   │   └── seed.py              # Datos semilla reproducibles
│   ├── templates/
│   │   ├── layouts/base.html
│   │   ├── auth/login.html
│   │   ├── dashboard.html
│   │   ├── pos.html
│   │   ├── students/
│   │   ├── teachers/
│   │   ├── groups/
│   │   ├── debts/
│   │   ├── payroll/
│   │   └── components/          # Modales, tarjeta alumno, visor ticket
│   └── static/
│       ├── css/
│       ├── js/
│       ├── img/
│       └── vendor/              # Chart.js, HTMX/Alpine, fuentes, iconos
├── data/
│   ├── icia.db
│   ├── icia.db-wal
│   ├── icia.db-shm
│   └── photos/                  # Fotos de alumnos y maestros
├── tests/
├── requirements.txt
└── run_app.bat
```

> La estructura exacta puede ajustarse durante la Fase 1, pero no se cambia de stack ni se agregan capas sin autorización.

---

## 4. Base de datos SQLite

### 4.1 PRAGMAs obligatorios

```python
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
```

Se aplican en cada conexión nueva. El esquema de referencia es `schemas/database_schema.sql`.

### 4.2 Convenciones
- Llaves primarias `INTEGER PRIMARY KEY`.
- Fechas en formato ISO-8601 (`TEXT`): `YYYY-MM-DD` o `YYYY-MM-DD HH:MM:SS`.
- Booleanos como `INTEGER` con `CHECK (columna IN (0,1))`.
- Montos como `INTEGER` en centavos; nunca `REAL`/`FLOAT`.
- Estados como `TEXT` con `CHECK` de valores permitidos.
- `ON DELETE RESTRICT` por defecto; no se borra historial.

### 4.3 Tablas
Ver `schemas/database_schema.sql` para columnas, checks, índices y vistas.

Tablas de soporte además de las diez de negocio:
- `folio_contadores`: último consecutivo por sucursal, protegido por `BEGIN IMMEDIATE`.
- `configuracion`: valores locales como hash de contraseña, ruta de USB, ancho de ticket y último respaldo.

Columnas de apoyo para trazabilidad:
- `asistencias.precio_aplicado_centavos`: congela el precio al momento de la asistencia para que la deuda no cambie si el grupo cambia de precio.
- `pagos.motivo_cancelacion` y `pagos.cancelado_en`: auditoría de anulaciones.

Restricciones de integridad relevantes:
- El folio de un pago es inmutable y los pagos no se eliminan (triggers).
- Una asistencia y su pago deben pertenecer al mismo alumno (FK compuesta).
- Una reposición y la falta que repone deben pertenecer al mismo alumno (FK compuesta).
- Solo puede haber una asistencia normal por alumno y sesión; las reposiciones se identifican con `es_reposicion = 1`.

### 4.4 Rutas configurables
- `ICIA_DATA_DIR`: carpeta de datos; por defecto `data/` junto al proyecto o al ejecutable.
- `ICIA_DB_PATH`: ruta de la base; por defecto `data/icia.db`. Para desarrollo se puede usar `data/icia_dev.db`.
- `ICIA_PHOTOS_DIR`: carpeta de fotos; por defecto `data/photos/`.
- `ICIA_HOST` e `ICIA_PORT`: servidor local; por defecto `127.0.0.1:8000`.
- Cuando la app corre empaquetada con PyInstaller, `BASE_DIR` apunta a la carpeta del ejecutable para que los datos no queden dentro del bundle temporal.

---

## 5. Folios atómicos

- Formato: `{PREFIJO}-{CONSECUTIVO:04d}` (ej. `REF-0029`).
- El consecutivo se incrementa en una transacción `BEGIN IMMEDIATE` sobre la tabla `folio_contadores`.
- El folio se asigna al pago dentro de la misma transacción que crea el pago.
- Nunca se reutiliza ni se renumera. La anulación solo cambia `pagos.estado` a `cancelado`.
- Si el proceso falla, la transacción revierte el incremento.

---

## 6. Flujo transaccional de Cobro Express

```text
POST /pos/cobrar
  BEGIN IMMEDIATE
    1. Validar sesión, alumno, grupo y método de pago.
    2. Obtener el precio vigente del grupo (centavos).
    3. Insertar pago con folio generado (estado = vigente).
    4. Insertar asistencia (estado = asistio, pago_id).
    5. COMMIT
  Fuera de la transacción:
    6. Renderizar ticket térmico con el folio confirmado.
    7. Enviar a impresión silenciosa.
```

- Si el ticket no se puede imprimir, el pago y la asistencia ya están confirmados y el ticket puede reimprimirse con el mismo folio. No se duplica el cobro.
- La operación "asistió sin pagar" inserta asistencia con `pago_id = NULL` y sin folio.
- Deshacer asistencia: `UPDATE pagos SET estado='cancelado'`, `DELETE`/marcar la asistencia según el contrato y registrar el motivo; el folio permanece.

---

## 7. Reglas de negocio en servicios

| Servicio | Responsabilidad |
| --- | --- |
| `cashier.py` | Cobro atómico, deuda, anulación y reposición |
| `folios.py` | Consecutivos por sucursal dentro de transacción |
| `thermal_printer.py` | Ticket HTML/ESC-POS y reimpresión |
| `backup_service.py` | Copia consistente a USB y verificación |
| `reports.py` | Dashboard, deudas y reposiciones pendientes |

La lógica de negocio no vive en routers ni en plantillas.

---

## 8. Frontend

- **Layout base:** rail lateral persistente, workspace central y panel térmico lateral (ver `DESIGN.md`).
- **Cobro Express:** tarjetas grandes de alumno, atajos `Espacio`/`F1`/`F2`, feedback inmediato y contador de cola.
- **HTMX/Alpine.js:** interacciones sin recarga completa; sin framework compilado.
- **Chart.js:** gráficas del dashboard con datos servidos por endpoint JSON local.
- **Tailwind:** CSS compilado y versionado en `app/static/css/`; no CDN.
- **Accesibilidad:** foco visible, contraste WCAG ≥ 4.5:1 y objetivos táctiles ≥ 48 px.

---

## 9. Impresión térmica

- Plantilla de ticket independiente con ancho de 58 mm u 80 mm configurable.
- CSS `@media print` con `@page { margin: 0; }` y ancho fijo.
- Chrome en modo kiosco para impresión silenciosa:
  `chrome --kiosk-printing http://127.0.0.1:8000/...`
- Salida ESC/POS opcional si el modelo de impresora lo requiere.
- Reimpresión por folio: consulta el pago y regenera el mismo ticket.

---

## 10. Respaldo y restauración

- Usar la API de backup de SQLite (`sqlite3.Connection.backup`) hacia la ruta USB configurada.
- La copia es consistente aunque el sistema esté en uso; no copiar el archivo con el explorador.
- Nombre sugerido: `icia_YYYYMMDD_HHMMSS.db`.
- Ruta configurable con `ICIA_BACKUP_DIR`; por defecto `data/backups` en desarrollo.
- `backup_service.py` copia a un archivo temporal, verifica `PRAGMA integrity_check` y renombra al nombre final.
- Registrar `ultimo_respaldo` y `ultimo_respaldo_ruta` en `configuracion` solo tras una copia verificada.
- Restauración probada en una carpeta limpia con otra laptop.
- Los respaldos contienen datos de menores: protegerlos y no enviarlos a la nube.

---

## 11. Seguridad y arranque

- Contraseña única del dueño con hash argon2/bcrypt; nunca en texto plano.
- Sesión local mediante cookie firmada; expiración configurable.
- No registrar datos personales en logs ni en mensajes de error.
- `run_app.bat` levanta Uvicorn, espera el puerto y abre Chrome en modo app.
- El acceso directo visible en Windows se llama **ICIA**.
- El dueño no ve terminales ni consola.

---

## 12. Pruebas

- `tests/` con pytest para servicios y flujos transaccionales.
- Casos mínimos:
  - Cobro de 35 alumnos con total $4,900.
  - Folio único y consecutivo por sucursal.
  - Anulación sin reutilizar folio.
  - Deuda, reposición y no duplicación de cobro.
  - Rollback ante fallo en cualquier paso del cobro.
  - Backup y restauración desde archivo.
- Meta: `pytest` verde antes de cerrar cada fase del `ROADMAP_TASKS.md`.
