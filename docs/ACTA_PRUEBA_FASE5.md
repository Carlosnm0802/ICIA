# Acta de prueba — Fase 5

**Producto:** ICIA — Sistema de gestión para escuela de Robótica e Inglés
**Fecha de preparación:** 7 de noviembre de 2026
**Última actualización:** 9 de noviembre de 2026
**Responsable técnico:** Desarrollo ICIA
**Estado:** preparación local completada; validación física pendiente

---

## 1. Alcance

Esta acta documenta la preparación de la Fase 5 y separa lo que ya se puede
comprobar en desarrollo de lo que requiere la laptop Windows y la impresora
térmica del dueño.

| Tarea | Estado | Evidencia |
| --- | --- | --- |
| 5.1 Arranque sin terminal | Preparada | `run_app.bat`, `iniciar_icia.vbs`, `app/launcher.py`, `app/stop.py`, `packaging/crear_acceso_directo.vbs`, `tests/test_launcher.py`, `tests/test_stop.py` |
| 5.2 Impresión térmica real | Pendiente | `ticket.html`, `ticket.css`, ticket de prueba en Configuración; falta impresora |
| 5.3 Empaquetado PyInstaller | Preparado | `packaging/icia.spec`, `packaging/build_windows.bat`, `requirements-build.txt`, `tests/test_windows_packaging.py`; falta compilar en Windows |
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
asistencia y pago en una sola operación, genera el ticket y consulta el
comprobante por folio.

La suite completa del proyecto debe cerrar en verde antes de tocar la laptop
del dueño. Al 9 de noviembre de 2026: **264 passed**.

---

## 3. Preparación del paquete en Windows

La compilación con PyInstaller **debe hacerse en Windows**; macOS no genera un
ejecutable válido para la laptop del dueño.

### 3.1 Requisitos

- Laptop Windows con Python 3.12 instalado.
- Conexión a internet solo durante la preparación (para instalar dependencias).
- La aplicación final funciona sin internet.

### 3.2 Compilación

Desde la carpeta del proyecto en Windows:

```bat
py -3.12 -m venv .venv
packaging\build_windows.bat
```

`build_windows.bat`:

1. Verifica que exista `.venv`.
2. Instala `requirements.txt` y `requirements-build.txt`.
3. Compila `packaging\icia.spec` con PyInstaller.
4. Copia `run_app.bat`, `iniciar_icia.vbs`, `detener_icia.bat` y
   `crear_acceso_directo.vbs` a `dist\`.

### 3.3 Instalación

1. Copiar la carpeta `dist\` completa a `C:\ICIA` (nunca a `Program Files`).
2. Abrir `C:\ICIA\crear_acceso_directo.vbs`.
3. Confirmar que aparece el acceso directo **ICIA** en el Escritorio y en el
   Menú Inicio.
4. Abrir ICIA con el acceso directo (no con `run_app.bat`).

El acceso directo ejecuta `wscript //nologo iniciar_icia.vbs`, por lo que no
muestra ventana de terminal. `iniciar_icia.vbs` usa `ICIA.exe` cuando existe y
cae a `.venv\Scripts\pythonw.exe` en modo desarrollo.

### 3.4 Antivirus

- Probar el primer arranque con el antivirus del dueño activo.
- Si Windows Defender o SmartScreen bloquea el ejecutable, agregar `C:\ICIA`
  como exclusión o permitir el archivo.
- Registrar el resultado en la sección de cierre.

---

## 4. Impresión térmica

### 4.1 Preparación

1. Instalar el controlador de la impresora térmica.
2. Configurarla como **impresora predeterminada** de Windows.
3. Abrir ICIA con el acceso directo, para que Chrome arranque con
   `--kiosk-printing`.
4. En **Configuración**, elegir el ancho real del rollo: 58 u 80 mm.

### 4.2 Prueba real

1. Abrir **Configuración → Imprimir ticket de prueba**.
2. Confirmar que imprime **sin diálogo**.
3. Cobrar 3 alumnos consecutivos e imprimir sus tickets.
4. Verificar que los 3 tickets salen completos, legibles y sin márgenes
   excesivos.
5. Confirmar que la reimpresión conserva folio y datos originales.

### 4.3 Validación alternativa sin impresora

Si la impresora térmica aún no está disponible:

1. En Chrome, abrir el ticket de prueba y usar **Imprimir → Guardar como PDF**.
2. Verificar en la vista previa:
   - Tamaño de página igual al ancho configurado (58 u 80 mm).
   - Sin encabezados ni pies de página del navegador.
   - Contenido completo y sin cortes.
3. Esta validación confirma el diseño, **no** la impresión silenciosa real.
   La ausencia de diálogo solo se confirma con la impresora física.

---

## 5. Respaldo y restauración desde USB

### 5.1 Crear el respaldo

1. Conectar la USB.
2. En **Configuración → Respaldo**, escribir la carpeta de destino
   (ej. `D:\RespaldoICIA`) y guardar.
3. Pulsar **Respaldar ahora**.
4. Verificar que el ZIP contiene:
   - `icia.db`
   - `manifest.json`
   - `photos/`

### 5.2 Restaurar en una carpeta o laptop limpia

1. Copiar `dist\` a `C:\ICIA` e iniciar ICIA una vez para crear la estructura.
2. En **Configuración → Restaurar respaldo**, seleccionar el ZIP de la USB y
   pulsar **Preparar restauración**.
3. Cerrar ICIA con `detener_icia.bat` (parada ordenada; espera el cierre del
   servidor).
4. Volver a abrir ICIA: la restauración se aplica al iniciar.
5. Verificar:
   - Datos de alumnos, grupos, sesiones y pagos restaurados.
   - Fotos presentes en `data\photos`.
   - Folios conservados y consecutivo correcto.
   - Respaldo de seguridad creado automáticamente antes de aplicar.

> No reemplazar `icia.db` mientras el servidor está en ejecución. La
> restauración se aplica al volver a abrir ICIA.

---

## 6. Lista de verificación en Windows

Marcar cada punto en la laptop del dueño:

- [ ] Compilar con `packaging\build_windows.bat` sin errores.
- [ ] Copiar la carpeta `dist\` a `C:\ICIA` (nunca a `Program Files`).
- [ ] Ejecutar `C:\ICIA\crear_acceso_directo.vbs` y confirmar los accesos.
- [ ] Abrir el acceso directo **ICIA** y confirmar que no aparece terminal.
- [ ] Confirmar que el navegador abre en modo aplicación sobre `127.0.0.1:8000`.
- [ ] Verificar que el antivirus no bloquea `ICIA.exe`.
- [ ] Configurar el ancho real del rollo (58 u 80 mm) en Configuración.
- [ ] Imprimir el ticket de prueba sin diálogo de impresión.
- [ ] Cobrar 3 alumnos consecutivos e imprimir sus tickets.
- [ ] Reimprimir un ticket y comparar folio y datos con el original.
- [ ] Cerrar ICIA con `detener_icia.bat` y confirmar que no queda proceso vivo.
- [ ] Volver a abrir ICIA; confirmar que pagos y folios siguen.
- [ ] Conectar la USB y crear un respaldo completo desde Configuración.
- [ ] Verificar que el ZIP contiene `icia.db`, `manifest.json` y `photos/`.
- [ ] Preparar una restauración desde el ZIP, cerrar y reiniciar ICIA.
- [ ] Confirmar que datos, fotos y folios quedaron restaurados.
- [ ] Ejecutar el caso base de 35 alumnos y anotar el total del día.
- [ ] Verificar el total: **$4,900.00 MXN**.

---

## 7. Resultado esperado del caso base

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

## 8. Observaciones

- El ancho de impresión aún no está confirmado con el modelo real de impresora.
- La compilación con PyInstaller debe hacerse en Windows.
- Los scripts `.bat` y `.vbs` se guardan con finales de línea CRLF para Windows.
- La parada usa un archivo marcador `data\icia.stop`; si el cierre ordenado no
  ocurre, se recurre a `SIGTERM` como respaldo.
- El respaldo de seguridad se crea automáticamente antes de aplicar una
  restauración.
- La validación con PDF confirma diseño, no impresión silenciosa.

---

## 9. Cierre

| Validación | Responsable | Fecha | Resultado |
| --- | --- | --- | --- |
| Caso base automatizado | Desarrollo | 2026-11-07 | Aprobado |
| Suite completa de pruebas | Desarrollo | 2026-11-09 | 264 passed |
| Arranque sin terminal en Windows | Dueño / soporte | | |
| Impresión real sin diálogo | Dueño / soporte | | |
| Restauración en laptop limpia | Dueño / soporte | | |
| Caso base físico de $4,900 | Dueño / soporte | | |
