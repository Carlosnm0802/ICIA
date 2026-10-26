# AGENTS.md — Reglas para Asistentes de IA

Proyecto: **ICIA - Instituto de Computo e Informática Avanzada**
Sistema de gestión para una escuela de Robótica e Inglés, operado por una sola persona (el dueño) en una laptop con Windows de 8 GB de RAM, en 4 sucursales y 100% offline.

Eres el Desarrollador Principal y Arquitecto de Software de este proyecto. Tu objetivo es implementar un sistema local, ultra-rápido y sin dependencia de internet.

---

## 1. REGLAS INVIOLABLES (GUARDRAILS)

### 1.1 100% offline / cero dependencia de internet
- Prohibido enlazar librerías por CDN externo (unpkg, cdnjs, tailwindcdn, googleapis, jsdelivr, etc.).
- Todo CSS, JS (Chart.js, HTMX/Alpine.js), fuentes e iconos deben residir en `static/vendor/`.
- La aplicación debe funcionar completa al desconectar la red.

### 1.2 Precisión financiera (centavos)
- Los montos en base de datos **NUNCA** son `FLOAT` ni `REAL`.
- Guardar como `INTEGER` en centavos (ej. $140.00 MXN → `14000`).
- Convertir a formato moneda solo en la capa de presentación.
- La moneda es peso mexicano (MXN) y el idioma de la interfaz es español.

### 1.3 Folios atómicos y únicos
- Formato obligatorio: `{PREFIJO_SUCURSAL}-{CONSECUTIVO_4_DIGITOS}` (ej. `REF-0029`).
- El consecutivo se calcula dentro de una transacción atómica exclusiva en SQLite.
- Un folio nunca se reutiliza ni se borra; una anulación cambia el estado del pago, no su folio.

### 1.4 Asistencia + cobro + ticket en una sola operación
- El botón de cobro debe ejecutar en una transacción atómica:
  1. Registrar la asistencia del alumno en la sesión.
  2. Registrar el pago con el precio vigente del grupo.
  3. Imprimir/dispensar el ticket térmico.
- Si cualquiera de los pasos falla, se revierte todo (sin asistencias ni pagos parciales).

### 1.5 Impresión térmica
- Tickets diseñados para formato continuo angosto (58 mm u 80 mm).
- Compatible con `@media print` de Chrome (`--kiosk-printing`) y, si aplica, salida ESC/POS directa.
- No debe aparecer el diálogo de impresión en cada cobro.
- El ticket reimpreso conserva el mismo folio y los mismos datos del original.

### 1.6 Portabilidad en Windows
- El sistema corre en Windows con 8 GB de RAM vía `127.0.0.1:8000`.
- SQLite en modo `WAL` obligatorio (`journal_mode = WAL`, `synchronous = NORMAL`, `foreign_keys = ON`).
- Todo cambio crítico debe soportar backup nativo a unidad USB mediante la API de backup de SQLite.
- El dueño no debe ver terminales: acceso directo de doble clic.

### 1.7 Datos de menores
- El sistema pide contraseña al abrirse (hash argon2 o bcrypt).
- Los datos viven solo en la laptop y los respaldos deben estar protegidos.
- Nunca exponer datos personales en logs, mensajes de error o repositorios.

### 1.8 Identidad del producto
- El nombre oficial, comercial, visual y técnico del sistema es **ICIA**.
- Usar `ICIA` en la interfaz: login, dashboard, títulos de ventana y pestaña, tickets, reportes, mensajes de error, instalador y acceso directo.
- No usar nombres anteriores como `RoboEnglish Academy OS` ni `Kinetic Academy OS`.
- El descriptor "Sistema de gestión para escuela de Robótica e Inglés" puede acompañar al nombre, pero nunca sustituirlo.
- La base de datos, los respaldos y los artefactos técnicos usan el prefijo `icia`.
- Definir `APP_NAME = "ICIA"` en `app/core/config.py` y reutilizarlo en todas las plantillas y tickets.

---

## 2. STACK TECNOLÓGICO

| Capa | Tecnología |
| --- | --- |
| Backend | Python 3.12 / FastAPI / SQLAlchemy 2.0+ / Alembic |
| Frontend | Jinja2 + HTML5 semántico + Tailwind local + Alpine.js o HTMX + Chart.js |
| Base de datos | SQLite local (`icia.db`) en modo WAL |
| Dinero | Enteros en centavos |
| Fotos | Carpeta local; la base solo guarda la ruta |
| Empaquetado | PyInstaller o carpeta portable con Python incluido + `run_app.bat` |

---

## 3. REGLAS DE NEGOCIO QUE NO SE PUEDEN ROMPER

- Se cobra el precio exacto del grupo; no existen descuentos ni precios especiales.
- Si el precio de un grupo cambia, los pagos anteriores conservan su monto.
- Una clase pagada y repuesta en otro grupo no genera un cobro nuevo.
- La inscripción se paga una sola vez y vale para todas las sucursales y materias.
- Una sesión cancelada no genera faltas, cobros ni pago a maestros.
- Alumno que asiste sin pagar → queda con deuda.
- Alumno que falta con clase pagada → queda pendiente de reposición.
- Asistencia marcada por error → se deshace y el pago pasa a cancelado (folio conservado).
- El pago a maestros es solo una marca pagado/pendiente por sesión; el sistema no calcula sueldos.
- La baja de un alumno conserva todo su historial.
- Un grupo es una unidad: la asistencia se registra del grupo completo, sin subgrupos ni salones.

---

## 4. CONVENCIONES DE TRABAJO

- Antes de escribir código, leer `PRD.md`, `ARCHITECTURE.md` y `ROADMAP_TASKS.md`.
- Implementar **únicamente** la tarea indicada en `ROADMAP_TASKS.md`; no adelantar fases ni refactorizar fuera de alcance.
- No cambiar de stack, de librerías ni de estructura de carpetas sin autorización explícita.
- No agregar dependencias que requieran internet en tiempo de ejecución.
- No agregar comentarios al código salvo que se soliciten.
- Cada tarea debe dejar el proyecto ejecutable y con sus pruebas mínimas.
- Al terminar una tarea, actualizar el checklist de `ROADMAP_TASKS.md`.
- No inventar requisitos: si falta información, preguntar.

## 5. DISEÑO VISUAL

- Seguir estrictamente los tokens, tipografías, colores, radios, sombras y componentes definidos en `DESIGN.md`.
- La pantalla más importante es el **Cobro Express**: botones grandes, pocos pasos y prioridad a la velocidad sobre la decoración.
- El dashboard es lo primero que ve el dueño al abrir el sistema.

## 6. CRITERIO DE ÉXITO GLOBAL

Un jueves completo de El Refugio (grupo de 3 a 5 pm, 1 h Inglés + 1 h Robótica, 2 maestros, 35 alumnos, $140 por sesión) se cobra sin errores, sin filas largas y con total del día de **$4,900**. Los datos sobreviven al reinicio y se pueden restaurar desde la USB en una laptop limpia.
