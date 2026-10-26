# PRD.md — Documento de Requisitos de Producto

Proyecto: **ICIA** — Sistema de gestión para escuela de Robótica e Inglés
Versión: 1.0 · Estado: borrador funcional basado en la entrevista con el dueño.

---

## 1. Visión y usuario

### 1.1 Problema
El dueño de una escuela de Robótica e Inglés administra 4 sucursales con cuadernos y hojas de Excel. No tiene una fuente única de verdad para cobros, asistencia, deudas, reposiciones y pagos a maestros. La operación ocurre en una laptop con Windows de 8 GB de RAM, muchas veces sin internet.

### 1.2 Usuario único
- **El dueño de la academia**, quien viaja con su laptop a las sucursales y opera el sistema de principio a fin.
- No hay multi-usuario, ni roles, ni acceso remoto en esta versión.

### 1.3 Sucursales
| Sucursal | Rol | Prefijo de folio |
| --- | --- | --- |
| Tototlán | Matriz | `TOT` |
| Ocotlán | Sucursal | `OCO` |
| Poncitlán | Sucursal | `PON` |
| El Refugio | Sucursal | `REF` |

Los prefijos son editables desde el sistema y no requieren tocar código.

### 1.4 Objetivo
Cobrar y marcar asistencia en un solo paso, imprimir el ticket térmico, ver quién debe y consultar métricas de cobros y alumnos activos, todo sin internet.

### 1.5 Identidad del producto
- El nombre oficial del sistema es **ICIA** y debe mostrarse así en login, dashboard, títulos de ventana y pestaña, tickets, reportes, mensajes de error, instalador y acceso directo.
- No usar nombres anteriores como `RoboEnglish Academy OS` ni `Kinetic Academy OS`.
- El descriptor "Sistema de gestión para escuela de Robótica e Inglés" puede acompañar al nombre, pero nunca sustituirlo.
- La base de datos y los respaldos usan el prefijo `icia` (`icia.db`, `icia_YYYYMMDD_HHMMSS.db`).

---

## 2. Flujo crítico: Cobro Express (día de clase)

1. El dueño inicia sesión con contraseña.
2. Selecciona la sucursal y el grupo del turno activo (ej. El Refugio, jueves 3:00–5:00 PM).
3. El sistema muestra la lista nominal alfabética del grupo.
4. Por cada alumno que llega, el dueño presiona una sola acción (`Espacio`, `F1` efectivo, `F2` transferencia o clic en "Cobrar").
5. Esa acción ejecuta en una transacción atómica:
   - Registra la asistencia del alumno en la sesión.
   - Registra el pago con el precio vigente del grupo y el método elegido.
   - Genera y envía el ticket térmico foliado.
6. Si cualquier paso falla, se revierte todo: no queda asistencia ni pago parcial.

**Meta de desempeño:** menos de 5 segundos por alumno y 35 alumnos cobrados en una sesión sin filas largas.

---

## 3. Alcance funcional

### 3.1 Módulos requeridos

| Módulo | Qué hace | Prioridad |
| --- | --- | --- |
| Acceso | Contraseña para abrir el sistema | Alta |
| Dashboard | Gráficas al abrir: cobrado hoy, cobrado en la semana (total y por sucursal), alumnos activos por sucursal | Alta |
| Cobro de clase | Lista del grupo del día; un toque registra asistencia, cobro e imprime ticket; método de pago y deshacer | Alta |
| Alumnos | Alta, edición, ficha con foto, baja con historial | Alta |
| Grupos y sesiones | Crear grupos con bloques y precio, ver sesiones generadas, cancelar, cambiar maestro, crear sesión extra | Alta |
| Sucursales | Alta y edición de sucursales | Media |
| Maestros | Alta, edición, ficha con foto, asignación a grupos | Media |
| Deudas | Listado de quién debe y cuánto, con cobro posterior y ticket | Alta |
| Reposiciones | Clases pagadas pendientes de reponer y registro de la reposición | Media |
| Pago a maestros | Sesiones impartidas con marca pagado/pendiente por maestro, individual o varias a la vez | Media |
| Asistencia de grupo | Consulta de asistencia por grupo y fechas | Media |
| Respaldos | Copia automática a la USB y aviso si lleva varios días sin respaldar | Alta |

### 3.2 Ticket térmico
- Contenido: escuela y sucursal, fecha, alumno, grupo y materia, monto, método de pago y folio.
- Formato continuo angosto (58 mm u 80 mm; pendiente de confirmar el modelo de impresora).
- Impresión silenciosa desde Chrome (`--kiosk-printing`) o ESC/POS directa.
- Reimpresión con el mismo folio y los mismos datos del original.
- Sin diálogo de impresión en cada cobro.

---

## 4. Reglas de negocio

### 4.1 Cobro
- Se cobra el precio exacto del grupo; no existen descuentos ni precios especiales.
- Si el precio de un grupo cambia, los pagos anteriores conservan el monto con que se pagaron.
- Métodos de pago permitidos: efectivo y transferencia.
- La inscripción se paga una sola vez, es única por alumno y vale para todas las sucursales y materias.
- Una clase pagada y repuesta en otro grupo no genera un cobro nuevo.
- Todo monto se almacena en centavos como entero.

### 4.2 Grupos y sesiones
- Un grupo es una unidad: la asistencia se registra del grupo completo, sin subgrupos ni salones.
- Un grupo pertenece a una sucursal, tiene horario fijo, precio por sesión y uno o varios bloques de materia.
- Una sesión puede combinar bloques de Inglés y Robótica.
- Las sesiones se generan automáticamente a partir del horario fijo del grupo.
- Una sesión cancelada no genera faltas, cobros ni pago a maestros.
- Se puede crear una sesión extra para el mismo grupo en otra fecha.

### 4.3 Maestros
- Se paga por sesión impartida, no por semana, y cada maestro tiene su propia marca.
- El sistema no calcula montos ni sueldos; solo marca pagado o pendiente.
- Un suplente reemplaza al titular únicamente en la sesión específica.

### 4.4 Excepciones y contingencias
- **Deuda:** alumno que asiste sin pagar. Se cobra después con su propio ticket.
- **Reposición pendiente:** alumno que faltó con clase pagada. Puede reponerla en otro grupo sin pago nuevo.
- **Reposición hecha:** nueva asistencia vinculada a la falta original y al mismo pago.
- **Anulación:** se deshace la asistencia y el pago pasa a cancelado; el folio se conserva y no se reutiliza.
- **Baja:** el alumno pasa a inactivo y conserva todo su historial.

---

## 5. Modelo de datos (resumen)

El contrato técnico completo está en `schemas/database_schema.sql`.

| Tabla | Campos principales |
| --- | --- |
| `sucursales` | nombre, dirección, teléfono, prefijo de folio, activa |
| `alumnos` | nombre, fecha de nacimiento, tutor y teléfono, escuela de procedencia, alergias/notas, personas autorizadas, foto, fecha de inscripción, estado |
| `maestros` | nombre, fecha de nacimiento, teléfono, correo, dirección, especialidad, fecha de ingreso, contacto de emergencia, foto, activo |
| `grupos` | sucursal, nombre, días, horario, precio por sesión en centavos, activo |
| `bloques_grupo` | grupo, materia, orden, duración en minutos, maestro |
| `grupo_alumnos` | grupo, alumno, fecha de alta, fecha de baja |
| `sesiones` | grupo, fecha, estado (programada, impartida, cancelada), es_extra |
| `sesion_maestros` | sesión, maestro, pagado, fecha de pago |
| `asistencias` | sesión, alumno, estado (asistió/faltó), es_reposición, repone_a, pago |
| `pagos` | folio, alumno, sucursal, tipo (inscripción/sesión), monto en centavos, método, fecha, estado (vigente/cancelado) |

### 5.1 Cálculos derivados
- **Deuda:** asistencias con estado `asistio` y sin pago vigente.
- **Reposición pendiente:** asistencias con estado `falto`, con pago vigente y sin una asistencia de reposición que las cubra.
- **Reposición hecha:** asistencia con `es_reposicion = 1` que apunta a la falta original y al mismo pago.
- **Fotos:** archivo en carpeta local; la base solo guarda la ruta.

---

## 6. Requisitos no funcionales

| Requisito | Criterio |
| --- | --- |
| Offline | Funciona al 100% sin red; ningún recurso se carga por CDN |
| Rendimiento | Menos de 5 s por cobro; arranque ágil en 8 GB de RAM |
| Integridad | Transacciones atómicas para cobro, anulación, folios y respaldo |
| Persistencia | SQLite en WAL, `synchronous = NORMAL`, `foreign_keys = ON` |
| Seguridad | Contraseña con hash argon2/bcrypt; datos de menores solo en la laptop |
| Portabilidad | Windows, `127.0.0.1:8000`, arranque por doble clic sin terminal |
| Respaldo | Backup consistente a USB con la API de SQLite; aviso si falla |
| Idioma | Interfaz y tickets en español; montos en MXN |
| Diseño | Seguir `DESIGN.md`; Cobro Express prioriza velocidad sobre decoración |

---

## 7. Criterios de aceptación

Caso base: El Refugio, jueves 3–5 PM, 1 h Inglés + 1 h Robótica, 2 maestros, 35 alumnos, $140 por sesión. Total esperado del día: **$4,900**.

| Prueba | Resultado esperado |
| --- | --- |
| Cobrar a los 35 alumnos | Un ticket por alumno; pocos segundos por cobro |
| Total del día en dashboard | Coincide con la suma de tickets vigentes ($4,900) |
| Deshacer una asistencia | Resta el monto del total y deja el ticket cancelado |
| Asistir sin pagar | Aparece en deudas con $140; al cobrarlo sale del listado y genera ticket |
| Faltar con clase pagada | Aparece en reposiciones; al reponerla el total cobrado no cambia |
| Cambio de precio del grupo | Los cobros anteriores conservan su monto |
| Sesión cancelada | No genera faltas, deuda ni pago pendiente a maestros |
| Dos maestros en una sesión | Dos marcas de pago independientes; el suplente reemplaza al titular |
| Reimpresión | Mismo folio y mismos datos que el original |
| Sin internet | Todo funciona y los datos siguen ahí al reiniciar |
| Respaldo | La USB se restaura en otra laptop limpia |

**Errores que el sistema debe evitar a toda costa:** cobrar dos veces una clase repuesta, perder datos por falta de respaldo y reutilizar o borrar un folio.

---

## 8. Fuera de alcance

- Recordatorios por WhatsApp.
- Varios usuarios o roles.
- App móvil.
- Uso desde más de una computadora.
- Cálculo automático de sueldos.
- Sincronización o base de datos en la nube.
- Importación masiva desde Excel (pendiente de definir).

---

## 9. Supuestos y pendientes

| Tema | Estado |
| --- | --- |
| Contraseña de acceso | Supuesto confirmado en la entrevista; implementar |
| Prefijo de folio por sucursal | Supuesto; confirmar con el dueño |
| Español y pesos mexicanos | Supuesto; confirmar con el dueño |
| Ancho del rollo térmico | Pendiente: 58 mm u 80 mm |
| Modelo de impresora | Pendiente |
| Captura inicial de alumnos existentes | Pendiente: manual o carga desde Excel |
| Precios de los grupos | Desconocidos; campo editable |

---

## 10. Riesgos

| Riesgo | Mitigación |
| --- | --- |
| Pérdida de datos por una sola laptop | Respaldo automático a USB, aviso de respaldo vencido y prueba de restauración |
| Docker en laptop de 8 GB | No usar Docker en la máquina del dueño |
| Impresora térmica no compatible | Probar un ticket real con impresión silenciosa antes de construir el resto |
| Datos de menores | Contraseña, datos solo locales y respaldos protegidos |
| Alucinación o cambio de stack por la IA | Seguir `AGENTS.md`, `ARCHITECTURE.md` y `ROADMAP_TASKS.md` al pie de la letra |
