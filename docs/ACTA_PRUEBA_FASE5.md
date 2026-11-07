# Acta de prueba — Fase 5

**Producto:** ICIA — Sistema de gestión para escuela de Robótica e Inglés
**Fecha de preparación:** 7 de noviembre de 2026
**Responsable técnico:** Desarrollo ICIA
**Estado:** preparación local completada; validación física pendiente

---

## 1. Alcance

Esta acta documenta la preparación de la Fase 5 y separa lo que ya se puede
comprobar en desarrollo de lo que requiere la laptop Windows y la impresora
térmica del dueño.

| Tarea | Estado | Evidencia |
| --- | --- | --- |
| 5.1 Arranque sin terminal | Preparada | `run_app.bat`, `iniciar_icia.vbs`, `app/launcher.py`, `tests/test_launcher.py` |
| 5.2 Impresión térmica real | Pendiente | `ticket.html`, `ticket.css`, ticket de prueba en Configuración; falta impresora |
| 5.3 Empaquetado PyInstaller | Preparado | `packaging/icia.spec`, `packaging/build_windows.bat`, `requirements-build.txt`; falta compilar en Windows |
| 5.4 Restauración desde USB | Preparada | `app/services/backup_service.py`, `app/services/restore_service.py`, `tests/test_backup_full.py`; falta probar en laptop limpia |
| 5.5 Caso base completo | Parcial | `tests/test_aceptacion_fase5.py` con 35 alumnos y $4,900; falta acta firmada con impresión real |

---

## 2. Caso base automatizado

**Escenario:** El Refugio, grupo Jueves 3-5 PM, 35 alumnos, $140 por sesión.

| Concepto | Valor |
| --- | --- |
| Alumnos cobrados | 35 |
| Precio por sesión | $140.00 MXN |
| Total esperado | $4,900.00 MXN |
| Total en centavos | 490000 |
| Folios generados | REF-0001 a REF-0035 |
| Duplicados de folio | 0 |
| Prueba | `tests/test_aceptacion_fase5.py` |
| Resultado | Aprobada en desarrollo |

La prueba usa el flujo real de Cobro Express: crea la sesión del día, registra
asistencia y pago en una sola operación, genera el tickete y consulta el
comprobante por folio.

---

## 3. Lista de verificación en Windows

Marcar cada punto en la laptop del dueño:

- [ ] Copiar la carpeta `dist\` a `C:\ICIA` (nunca a `Program Files`).
- [ ] Abrir `ICIA.exe` con doble clic y confirmar que no aparece terminal.
- [ ] Confirmar que el navegador abre en modo aplicación sobre `127.0.0.1:8000`.
- [ ] Configurar el ancho real del rollo (58 u 80 mm) en Configuración.
- [ ] Imprimir el ticket de prueba sin diálogo de impresión.
- [ ] Cobrar 3 alumnos consecutivos e imprimir sus tickets.
- [ ] Cerrar y volver a abrir ICIA; confirmar que los pagos y folios siguen.
- [ ] Conectar la USB y crear un respaldo completo desde Configuración.
- [ ] Verificar que el ZIP contiene `icia.db`, `manifest.json` y `photos/`.
- [ ] Preparar una restauración desde el ZIP y reiniciar ICIA.
- [ ] Confirmar que datos, fotos y folios quedaron restaurados.
- [ ] Ejecutar el caso base de 35 alumnos y anotar el total del día.
- [ ] Verificar el total: **$4,900.00 MXN**.

---

## 4. Resultado esperado del caso base

| Campo | Resultado esperado |
| --- | --- |
| Total del día | $4,900.00 |
| Alumnos con pago vigente | 35 |
| Alumnos con deuda | 0 |
| Folios | REF-0001 a REF-0035 |
| Tickets impresos | 35 |
| Internet requerido | Ninguno |
| Terminal visible | Ninguna |

---

## 5. Observaciones

- El ancho de impresión aún no está confirmado con el modelo real de impresora.
- La compilación con PyInstaller debe hacerse en Windows; macOS no genera un
  ejecutable válido para la laptop del dueño.
- La restauración se aplica al volver a abrir ICIA, después de usar
  `detener_icia.bat`; así se evita reemplazar la base mientras el servidor está
  en ejecución.
- El respaldo de seguridad se crea automáticamente antes de aplicar una
  restauración.

---

## 6. Cierre

| Validación | Responsable | Fecha | Resultado |
| --- | --- | --- | --- |
| Caso base automatizado | Desarrollo | 2026-11-07 | Aprobado |
| Arranque sin terminal en Windows | Dueño / soporte | | |
| Impresión real sin diálogo | Dueño / soporte | | |
| Restauración en laptop limpia | Dueño / soporte | | |
| Caso base físico de $4,900 | Dueño / soporte | | |
