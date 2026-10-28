# ROADMAP_TASKS.md — Tareas de Implementación

Regla de trabajo: **una tarea a la vez**. No se adelanta la siguiente fase ni se refactoriza fuera de alcance. Al cerrar una tarea se marca `[x]` y se deja el proyecto ejecutable con sus pruebas mínimas.

Nombre oficial del producto: **ICIA**. Toda pantalla, ticket, reporte, título de ventana, instalador y acceso directo debe mostrar `ICIA`; no usar `RoboEnglish Academy OS` ni `Kinetic Academy OS`.

Leyenda: `[ ]` pendiente · `[x]` completada · `[~]` en curso

---

## FASE 1 — Esqueleto, base de datos y respaldo USB

- [x] **Tarea 1.1** — Crear estructura de directorios, `requirements.txt`, entorno virtual y archivo mínimo `app/main.py` con FastAPI en `127.0.0.1:8000`.
  - Entregable: servidor que responde una página básica; sin dependencias de internet en runtime.
- [x] **Tarea 1.2** — Implementar `app/core/config.py` con `APP_NAME = "ICIA"` y `app/core/database.py` con SQLite WAL (`journal_mode=WAL`, `synchronous=NORMAL`, `foreign_keys=ON`, `busy_timeout`).
  - Entregable: conexión reutilizable, PRAGMAs verificados y nombre de aplicación centralizado.
- [x] **Tarea 1.3** — Implementar modelos en `app/models/` conforme a `schemas/database_schema.sql` y migración inicial con Alembic.
  - Entregable: base creada con las tablas, checks, llaves foráneas e índices del contrato.
- [x] **Tarea 1.4** — Crear script de datos semilla: 4 sucursales (TOT, OCO, PON, REF), maestros y 1 grupo de El Refugio con 35 alumnos y precio $140.
  - Entregable: datos reproducibles para pruebas.
- [x] **Tarea 1.5** — Implementar `app/services/backup_service.py` con la SQLite Backup API hacia USB.
  - Entregable: copia consistente, nombre con timestamp y registro del último respaldo.
- [x] **Tarea 1.6** — Crear pruebas mínimas de base de datos, modelo y backup.
  - Entregable: `pytest` verde.

**Criterio de aceptación Fase 1:** base creada con datos semilla y backup que copia el `.db` sin bloquear lecturas, verificado por prueba automatizada.

---

## FASE 2 — Cobro Express y tickets térmicos (núcleo del sistema)

- [x] **Tarea 2.1** — Crear `app/routers/pos.py` y `pos.html` con listado nominal del grupo del turno.
  - Entregable: selección de sucursal/grupo/sesión y lista alfabética de alumnos.
- [ ] **Tarea 2.2** — Implementar atajos de teclado (`Espacio` cobro, `F1` efectivo, `F2` transferencia) con feedback visual inmediato.
  - Entregable: operación sin mouse y sin recarga completa.
- [ ] **Tarea 2.3** — Implementar `app/services/folios.py` con consecutivo atómico por sucursal (`REF-0001`).
  - Entregable: folio único bajo concurrencia y prueba de no reutilización.
- [ ] **Tarea 2.4** — Implementar `app/services/cashier.py`: transacción atómica asistencia + pago + folio, con rollback total ante error.
  - Entregable: cobro consistente y prueba de rollback.
- [ ] **Tarea 2.5** — Crear componente de Ticket Térmico (58/80 mm) con encabezado `ICIA` e integración con impresión silenciosa (`@media print` + `--kiosk-printing`).
  - Entregable: ticket foliado con datos completos, nombre ICIA y sin diálogo de impresión.
- [ ] **Tarea 2.6** — Botón y ruta "Asistió sin pagar" que registre deuda en un clic.
  - Entregable: asistencia con `pago_id = NULL` visible en deudas.
- [ ] **Tarea 2.7** — Botón "Deshacer asistencia" que anule el pago sin borrar el folio.
  - Entregable: pago en estado `cancelado`, asistencia deshecha y auditoría conservada.
- [ ] **Tarea 2.8** — Reimpresión de ticket por folio con los mismos datos.
  - Entregable: mismo folio y contenido que el original.
- [ ] **Tarea 2.9** — Implementar `auth.py` con contraseña hasheada y sesión local, mostrando `ICIA` en el login.
  - Entregable: acceso protegido al sistema con identidad ICIA visible.

**Criterio de aceptación Fase 2:** simulación de cobro a 10 alumnos consecutivos en menos de 30 segundos, con tickets generados, deuda y anulación funcionando, folios únicos y nombre ICIA visible en login y tickets.

---

## FASE 3 — Dashboard, deudas y reposiciones

- [ ] **Tarea 3.1** — Endpoint y plantilla `dashboard.html` con KPI: cobrado hoy, cobrado en la semana, deudas y alumnos activos.
  - Entregable: dashboard como primera pantalla tras el login.
- [ ] **Tarea 3.2** — Gráfica de recaudación por sucursal con Chart.js local (sin CDN).
  - Entregable: gráfica funcional offline.
- [ ] **Tarea 3.3** — Módulo de deudas: listado de morosos con monto y botón de cobro rápido.
  - Entregable: cobrar deuda genera ticket y actualiza totales.
- [ ] **Tarea 3.4** — Módulo de reposiciones pendientes y registro de reposición en otro grupo sin cobro nuevo.
  - Entregable: falta con pago se marca como repuesta y no altera el total cobrado.
- [ ] **Tarea 3.5** — Pruebas de dashboard, deuda y reposición.
  - Entregable: `pytest` verde y totales consistentes.

**Criterio de aceptación Fase 3:** al cobrar una deuda, el dashboard actualiza automáticamente los totales recaudados; reponer una clase no genera cobro nuevo.

---

## FASE 4 — Grupos, sesiones y pago a maestros

- [ ] **Tarea 4.1** — CRUD de sucursales y grupos con bloques múltiples (materia, orden, duración, maestro, precio).
  - Entregable: grupo de 1 h Robótica + 1 h Inglés creado desde la interfaz.
- [ ] **Tarea 4.2** — Generación automática de sesiones desde el horario del grupo.
  - Entregable: sesiones programadas visibles y editables según reglas.
- [ ] **Tarea 4.3** — Cancelación de sesión sin generar faltas, cobros ni honorarios, y creación de sesión extra.
  - Entregable: sesión cancelada y sesión extra funcionando.
- [ ] **Tarea 4.4** — Sustitución de docente titular por suplente en una sesión específica.
  - Entregable: dos marcas de pago independientes por sesión.
- [ ] **Tarea 4.5** — Pantalla de pago a maestros: marcar pagado/pendiente individual o en lote, sin calcular sueldos.
  - Entregable: corte de honorarios por sesión.
- [ ] **Tarea 4.6** — CRUD de alumnos y maestros con foto local, baja con historial y ficha completa.
  - Entregable: datos personales y fotos gestionados sin inflar la base.
- [ ] **Tarea 4.7** — Consulta de asistencia por grupo y fechas.
  - Entregable: historial de asistencia exportable/consultable.

**Criterio de aceptación Fase 4:** sesión con maestro suplente liquidada y reflejada en el corte semanal; sesión cancelada sin efectos financieros.

---

## FASE 5 — Empaquetado y puesta en marcha (Windows)

- [ ] **Tarea 5.1** — Crear `run_app.bat` que inicie Uvicorn y abra Chrome en modo app/kiosko; sin ventanas de terminal.
  - Entregable: doble clic y sistema listo.
- [ ] **Tarea 5.2** — Configurar impresión silenciosa y validar un ticket real en la impresora térmica del dueño.
  - Entregable: 3 tickets consecutivos impresos sin diálogo.
- [ ] **Tarea 5.3** — Empaquetar con PyInstaller o carpeta portable con Python incluido; probar antivirus.
  - Entregable: paquete que corre en una laptop limpia con Windows.
- [ ] **Tarea 5.4** — Probar restauración de base de datos desde USB en una carpeta limpia.
  - Entregable: datos, fotos y folios restaurados correctamente.
- [ ] **Tarea 5.5** — Ejecutar el caso base completo: El Refugio, 35 alumnos, $4,900, sin internet.
  - Entregable: acta de prueba con totales y tickets.

**Criterio de aceptación Fase 5:** el dueño hace doble clic en el escritorio, el sistema arranca sin terminal, imprime sin diálogo y restaura desde USB en otra laptop.

---

## Estado actual

- Fase 1 completada.
- Fase 2 en curso: **Tarea 2.1 completada**.
- Siguiente tarea recomendada: **Tarea 2.2 — atajos de teclado y feedback visual**.
- Pendientes de confirmación con el dueño antes de Fase 2: ancho de rollo (58/80 mm), modelo de impresora, prefijos de folio definitivos, precios de grupos y estrategia de captura inicial de alumnos.
