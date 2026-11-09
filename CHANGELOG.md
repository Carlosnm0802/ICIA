# Changelog

Todos los cambios relevantes de ICIA.

El formato sigue la idea de Keep a Changelog y el versionado semántico
(`MAYOR.MENOR.PARCHE`).

---

## [1.0.0-rc.1] — 2026-11-09

Versión candidata para la presentación al cliente. La operación diaria está
completa; queda pendiente la validación física en Windows.

### Añadido

- Empaquetado para Windows con PyInstaller (`packaging/icia.spec` y
  `packaging/build_windows.bat`).
- Creador de acceso directo `ICIA.lnk` para Escritorio y Menú Inicio, sin
  ventana de terminal (`packaging/crear_acceso_directo.vbs`).
- Parada ordenada del servidor mediante el marcador `icia.stop`, con respaldo
  por `SIGTERM`.
- Respaldo completo en ZIP con base de datos, fotos y manifiesto; restauración
  con respaldo de seguridad automático.
- Manual de usuario para el dueño (`docs/MANUAL_USUARIO.md`).
- Pruebas de empaquetado Windows, rutas empaquetadas y parada ordenada.

### Cambiado

- Scripts `.bat` y `.vbs` guardados con finales de línea CRLF mediante
  `.gitattributes`.
- Hidden imports de PyInstaller ampliados (`bcrypt`, `mako`, `jinja2.ext` y
  `email.mime`).

### Documentado

- README del proyecto con instalación, operación, respaldos y limitaciones.
- Acta de prueba de Fase 5 con checklist de Windows.

### Pendiente

- Compilar y probar el paquete en la laptop Windows del cliente.
- Confirmar modelo y ancho de la impresora térmica (58 u 80 mm).
- Imprimir 3 tickets consecutivos sin diálogo.
- Restaurar desde USB en una carpeta limpia.
- Ejecutar el caso base de 35 alumnos con total de $4,900.00 y firmar el acta.

---

## Historial previo (Fases 1–4)

Antes de esta versión no se crearon etiquetas de liberación.

### Fase 1 — Base del sistema

- Estructura del proyecto, FastAPI en `127.0.0.1:8000`, SQLite en WAL y
  migraciones con Alembic.
- Modelos, datos semilla y respaldo con la API de SQLite.

### Fase 2 — Cobro Express y tickets

- Cobro atómico de asistencia, pago y folio.
- Folios consecutivos por sucursal, anulación sin reutilizar folio y reimpresión.
- Tickets térmicos, descarga HTML y acceso protegido con contraseña.

### Fase 3 — Dashboard, deudas y reposiciones

- KPI de cobrado hoy, cobrado en la semana, deudas y alumnos activos.
- Gráfica de recaudación por sucursal con Chart.js local.
- Cobro de deudas y registro de reposiciones sin cobro nuevo.

### Fase 4 — Grupos, sesiones y maestros

- CRUD de sucursales, grupos, alumnos y maestros con fotos locales.
- Generación automática de sesiones, cancelación, sesión extra y suplencias.
- Pago a maestros por sesión y consulta de asistencia con exportación CSV.
