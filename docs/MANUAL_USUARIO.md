# Manual de usuario — ICIA

**Sistema de gestión para escuela de Robótica e Inglés**

Este manual explica cómo usar ICIA en el día a día: cobrar clases, marcar
asistencia, imprimir tickets, consultar deudas, respaldar la información y
restaurarla si fuera necesario.

> ICIA funciona sin internet. Todos los datos viven en la laptop y en los
> respaldos que tú generes.

---

## Inicio rápido

1. **Abrir ICIA:** doble clic en el acceso directo **ICIA** del Escritorio.
   No se abre ninguna terminal; el navegador muestra el sistema.
2. **Entrar:** escribe tu contraseña y pulsa **Entrar**.
3. **Cobrar:** entra a **Cobro Express**, elige sucursal, grupo y sesión.
   - `Espacio`: cobrar con el método seleccionado.
   - `F1`: cobrar en efectivo.
   - `F2`: cobrar por transferencia.
   - `F3`: registrar “asistió sin pagar” (genera deuda).
   - Flechas: moverte entre alumnos.
   - `Esc`: limpiar la selección.
4. **Al terminar:** cierra sesión y, si usaste la USB, pulsa **Respaldar ahora**
   en **Configuración**.

---

## 1. Abrir y cerrar ICIA

### Abrir

- Usa el acceso directo **ICIA** del Escritorio o del Menú Inicio.
- Si no existe el acceso directo, abre `C:\ICIA\crear_acceso_directo.vbs` una
  sola vez para crearlo.
- No abras `run_app.bat` directamente; puede mostrar una ventana de terminal.

### Cerrar

- Lo normal es cerrar la pestaña del navegador y apagar la laptop.
- Si necesitas detener el sistema por completo, usa `detener_icia.bat` y espera
  unos segundos.
- No apagues la laptop a la fuerza mientras se está cobrando.

---

## 2. Iniciar sesión

### Primera vez

La primera vez que se abre ICIA, la pantalla pide **crear la contraseña**:

- Debe tener al menos 8 caracteres.
- Hay que escribirla dos veces.
- Pulsa **Guardar contraseña**.

Guarda esa contraseña en un lugar seguro. Actualmente el sistema no tiene una
pantalla para cambiarla; si se pierde, se necesita soporte técnico.

### Acceso normal

1. Escribe la contraseña.
2. Pulsa **Entrar**.
3. Para salir, usa **Cerrar sesión** al final del menú lateral.

---

## 3. Dashboard

Es la primera pantalla después de entrar. Muestra:

- **Cobrado hoy.**
- **Cobrado en la semana.**
- **Deudas pendientes.**
- **Alumnos activos.**
- **Recaudación por sucursal** en una gráfica.

Los totales se actualizan conforme se registran cobros. No necesitas refrescar
manualmente la página.

---

## 4. Cobro Express

Es la pantalla más importante. Permite cobrar y marcar asistencia en un solo
paso.

### Antes de cobrar

1. Entra a **Cobro Express**.
2. Elige la **sucursal**.
3. Elige el **grupo**.
4. Elige la **sesión** del día.

Si la sesión del día no existe, usa el botón para crearla o genera las sesiones
desde **Grupos**.

### Cobrar a un alumno

1. Selecciona al alumno con el mouse o las flechas.
2. Pulsa:
   - `Espacio` para cobrar con el método activo.
   - `F1` para efectivo.
   - `F2` para transferencia.
3. El sistema registra la asistencia, el pago y el folio, y abre el ticket.
4. El ticket se imprime solo si ICIA se abrió con el acceso directo y la
   impresora está configurada.

### Registrar una deuda

Si el alumno asistió pero no pagó:

1. Selecciona al alumno.
2. Pulsa `F3` o el botón de “Asistió sin pagar”.

El alumno queda en **Deudas** por el monto de la sesión.

### Marcar una falta

Si el alumno no llegó, usa la opción de marcar falta. Si la clase ya estaba
pagada, la falta aparecerá en **Reposiciones**.

### Deshacer una asistencia

Si cobraste por error:

1. Busca al alumno en la lista.
2. Usa **Deshacer asistencia**.

El pago queda **cancelado**, el folio se conserva y la asistencia se deshace.
El folio no se reutiliza.

### Reimprimir un ticket

Puedes reimprimir por folio desde la pantalla del ticket o desde el formulario
de cobro. La reimpresión conserva el mismo folio y los mismos datos.

---

## 5. Alumnos

En **Alumnos** puedes:

- Dar de alta un alumno nuevo.
- Editar sus datos.
- Agregar o quitar grupos.
- Ver su ficha completa.
- Subir o cambiar su foto.
- Dar de baja al alumno conservando todo su historial.

La **fecha de inscripción** es un dato informativo. Por ahora el sistema no
tiene una pantalla para cobrar la inscripción (ver Limitaciones actuales).

---

## 6. Grupos y sesiones

En **Grupos** puedes:

- Crear un grupo con sucursal, nombre, días, horario y precio por sesión.
- Agregar bloques de materia (por ejemplo, Inglés y Robótica), con orden,
  duración y maestro.
- Generar las sesiones a partir del horario.
- Crear una sesión extra en otra fecha.
- Cancelar una sesión (no genera faltas, cobros ni pagos a maestros).
- Reactivar una sesión cancelada.
- Registrar la sustitución de un maestro por un suplente en una sesión
  específica.
- Reprogramar una sesión.

---

## 7. Maestros

En **Maestros** puedes:

- Dar de alta un maestro.
- Editar sus datos.
- Consultar su ficha.
- Subir o cambiar su foto.
- Asignarlo a grupos desde la pantalla de grupos.

---

## 8. Deudas

En **Deudas** aparecen los alumnos que asistieron sin pagar.

1. Localiza al alumno.
2. Usa el cobro rápido.
3. Elige el método de pago.

Se genera un ticket nuevo y la deuda desaparece del listado.

---

## 9. Reposiciones

En **Reposiciones** aparecen las faltas con clase pagada que aún no se reponen.

Para registrar una reposición:

1. Entra a **Reposiciones**.
2. Elige la falta pendiente.
3. Selecciona el grupo y la fecha donde se repondrá.
4. Confirma.

La reposición **no genera un cobro nuevo**.

---

## 10. Pago a maestros

En **Pago a maestros** se muestran las sesiones impartidas.

- Puedes marcar una sesión como pagada o pendiente.
- También puedes marcar varias a la vez.
- ICIA solo lleva la marca de pagado/pendiente; **no calcula sueldos**.

Si una sesión tuvo suplente, cada maestro tiene su propia marca.

---

## 11. Asistencias

En **Asistencias** puedes consultar el historial por grupo y rango de fechas.

- La consulta muestra los alumnos y su estado.
- Puedes exportar el resultado a CSV para abrirlo en Excel.

---

## 12. Configuración

En **Configuración** se ajustan tres cosas:

### Impresión térmica

- Elegir el ancho del ticket: **58 mm** u **80 mm**.
- Usar **Imprimir ticket de prueba** para comprobar la impresora.

### Respaldo

- Ver el último respaldo.
- Elegir la carpeta de respaldos (puede ser una USB).
- Pulsar **Respaldar ahora**.

### Restaurar respaldo

- Seleccionar un archivo ZIP de respaldo.
- Pulsar **Preparar restauración**.
- Cerrar ICIA con `detener_icia.bat`.
- Volver a abrir ICIA para aplicar la restauración.

---

## 13. Respaldos

### Cuándo respaldar

- Al terminar cada día de clases.
- Antes de restaurar o mover la información.
- Al menos una vez por semana si no usaste la USB.

### Cómo respaldar

1. Conecta la USB.
2. Entra a **Configuración**.
3. Escribe la carpeta de destino, por ejemplo `D:\RespaldoICIA`.
4. Pulsa **Guardar carpeta**.
5. Pulsa **Respaldar ahora**.

El respaldo es un archivo ZIP que contiene:

- `icia.db` (la base de datos).
- `manifest.json` (información del respaldo).
- `photos/` (las fotos de alumnos y maestros).

### Cómo restaurar

1. Copia el ZIP a la laptop.
2. Entra a **Configuración → Restaurar respaldo**.
3. Selecciona el ZIP y pulsa **Preparar restauración**.
4. Cierra ICIA con `detener_icia.bat`.
5. Abre ICIA de nuevo.

ICIA crea automáticamente un respaldo de seguridad antes de reemplazar los
datos.

> No copies `icia.db` a mano mientras ICIA está abierto. Usa siempre la opción
> de respaldo y restauración.

---

## 14. Problemas comunes

### ICIA no abre

- Verifica que exista la carpeta `C:\ICIA` completa.
- Usa el acceso directo **ICIA**.
- Si el acceso directo no existe, abre `C:\ICIA\crear_acceso_directo.vbs`.
- Si el problema continúa, contacta a soporte.

### El navegador no muestra ICIA

- Espera unos segundos: el servidor tarda un poco en iniciar.
- Revisa que no haya otra instancia de ICIA abierta.
- Cierra todo y vuelve a abrir con el acceso directo.

### La impresora no imprime

- Confirma que la impresora esté encendida y con papel.
- Verifica que sea la impresora predeterminada de Windows.
- Abre ICIA con el acceso directo, no con `run_app.bat`.
- Prueba con **Configuración → Imprimir ticket de prueba**.

### Aparece el diálogo de impresión

- ICIA debe abrirse con el acceso directo para usar `--kiosk-printing`.
- Cierra el navegador y vuelve a abrir ICIA desde el acceso directo.

### El antivirus bloquea ICIA

- Permite `C:\ICIA\ICIA.exe` o agrega `C:\ICIA` como exclusión.
- Si Windows SmartScreen muestra una advertencia, permite el archivo solo si
  lo instaló soporte técnico.

### Quedó una restauración pendiente

- Cierra ICIA con `detener_icia.bat`.
- Vuelve a abrir ICIA; la restauración se aplicará al iniciar.

### Aparece “puerto ocupado”

- Cierra todas las ventanas de ICIA.
- Espera unos segundos y vuelve a abrir.
- Si persiste, reinicia la laptop o contacta a soporte.

### Olvidé la contraseña

Actualmente no hay una pantalla de recuperación. Contacta a soporte técnico
para restablecerla.

---

## 15. Reglas importantes

- **No borres folios.** Un pago se cancela, pero su folio se conserva.
- **No copies la base de datos a mano** con ICIA abierto.
- **No apagues la laptop a la fuerza** durante un cobro.
- **Respaldar no es opcional:** es la única forma de recuperar la información.
- **Los datos son de menores:** mantén la laptop y la USB en un lugar seguro.
- **No compartas los respaldos** ni los subas a internet.

---

## 16. Checklist del día de clase

- [ ] Abrir ICIA con el acceso directo.
- [ ] Iniciar sesión.
- [ ] Verificar sucursal, grupo y sesión.
- [ ] Cobrar a los alumnos.
- [ ] Revisar deudas y reposiciones al terminar.
- [ ] Imprimir o reimprimir tickets faltantes.
- [ ] Conectar la USB y respaldar.
- [ ] Cerrar sesión.

---

## 17. Limitaciones actuales

Estas funciones todavía no están disponibles o están pendientes de validación:

- **Cobro de inscripción:** solo se guarda la fecha de inscripción; aún no hay
  pantalla para cobrarla.
- **Respaldo manual:** el respaldo se genera al pulsar **Respaldar ahora**; el
  recordatorio aparece en Configuración.
- **Cambio de contraseña:** no hay pantalla para cambiarla después del primer
  acceso.
- **Impresora:** falta confirmar el modelo real y el ancho definitivo (58 u 80 mm).
- **Validación en Windows:** la instalación física en la laptop del dueño y la
  restauración desde USB están en proceso de validación.
- **Un solo usuario:** no hay roles ni acceso desde varias computadoras.
- **Sueldos:** ICIA no calcula sueldos; solo marca pagos por sesión.
- **Importación desde Excel:** no está disponible; los alumnos se capturan
  manualmente.

---

**ICIA** — Sistema de gestión para escuela de Robótica e Inglés
