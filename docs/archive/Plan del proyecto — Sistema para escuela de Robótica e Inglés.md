# Plan del proyecto — Sistema para escuela de Robótica e Inglés

Oct 24, 2026 · @Carlos

## Resumen

El proyecto es un sistema local para que el dueño de la escuela controle sucursales, alumnos, grupos, cobros y pago a maestros desde una sola laptop con Windows, sin depender de internet.

- **Usuario:** solo el dueño, con una laptop (Windows, 8 GB de RAM) que lleva a cada sucursal.
- **Problema:** hoy todo vive en cuadernos y Excel, repartido entre cuatro sucursales (Tototlán, Ocotlán, Poncitlán y El Refugio) y con planes de abrir más.
- **Resultado esperado:** cobrar y marcar asistencia en un solo paso, imprimir el ticket en impresora térmica, ver quién debe, y consultar gráficas de cobros y alumnos activos.
- **Diseño:** moderno y vistoso; al abrir el sistema, lo primero que ve el dueño son las gráficas.

## Flujo del sistema

El corazón del sistema es el día de clase: el alumno llega, el dueño marca su asistencia, el sistema registra el cobro y se imprime el ticket.

1. **Configuración:** el dueño da de alta sucursales (nombre, dirección, teléfono), maestros y grupos. Cada grupo tiene sucursal, horario fijo, bloques de materia con duración, maestros asignados y precio por sesión.
2. **Inscripción:** al alumno nuevo se le cobra una inscripción única, válida para toda la escuela, y se le asigna a un grupo. Después paga solo por sesión.
3. **Generación de sesiones:** el sistema crea automáticamente cada sesión a partir del horario fijo del grupo.
4. **Día de clase:** el dueño abre el grupo, ve la lista y marca "asistió" alumno por alumno conforme pagan. Cada marca registra el cobro (efectivo o transferencia) con el precio vigente del grupo e imprime el ticket.
5. **Falta:** si un alumno ya pagó y no asiste, queda con una clase pendiente de reponer. La puede tomar en otro grupo sin pagar de nuevo.
6. **Deuda:** si el alumno asiste sin pagar, queda con deuda. El dueño ve el listado de quién debe y cuánto, y cobra esas clases después con su propio ticket.
7. **Corrección:** el dueño puede deshacer una asistencia, lo que anula el cobro. El ticket queda como cancelado en el historial y puede reimprimirse con su mismo folio.
8. **Pago a maestros:** al terminar cada sesión, cada maestro que la impartió tiene su propia marca de pagado o pendiente. Si un suplente cubre, se cambia el maestro de esa sesión.
9. **Cancelación y reposición:** una sesión cancelada (festivo, puente) no genera faltas, cobros ni pago a maestros. El dueño puede crear una sesión extra en otra fecha para el mismo grupo.
10. **Baja:** al alumno que deja de asistir se le da de baja y se conserva todo su historial.

## Reglas, excepciones y supuestos

Estas reglas salieron de la entrevista con el dueño y son las que el sistema debe cumplir siempre.

**Reglas de cobro**

- Se cobra el precio exacto del grupo; no hay descuentos ni precios especiales.
- Si el precio de un grupo cambia, los cobros anteriores conservan el monto con que se pagaron.
- Una clase pagada y repuesta en otro grupo no genera un cobro nuevo.
- Se aceptan dos métodos de pago: efectivo y transferencia.
- La inscripción se paga una sola vez y vale para todas las sucursales y materias.

**Reglas de grupos y sesiones**

- Un grupo es una unidad: se registra la asistencia del grupo completo, sin subgrupos ni salones.
- Una sesión puede combinar bloques de Inglés y Robótica (por ejemplo 3 h mitad y mitad, 2 h con 1 + 1, o 3 h solo Inglés).
- La sesión cancelada no cuenta como falta, cobro ni pago a maestro.

**Reglas de maestros**

- Se les paga por sesión impartida, no por semana, y cada maestro tiene su propia marca.
- El sistema no calcula montos ni sueldos; solo marca pagado o pendiente.

**Casos límite contemplados**

- Alumno que asiste sin pagar: queda con deuda y se cobra después.
- Alumno que falta con clase pagada: queda pendiente de reposición.
- Suplente de un maestro: se cambia el maestro de esa sesión específica.
- Asistencia marcada por error: se deshace y se anula el cobro.
- Ticket perdido o atascado: se reimprime con el mismo folio.

**Supuestos tomados (por confirmar con el dueño)**

- El sistema pide contraseña al abrirse.
- El folio es consecutivo con prefijo por sucursal, por ejemplo REF-0001.
- Todo en español y montos en pesos mexicanos.

## Modelo de datos

Hay diez tablas; la clave es que cada pago guarda su propio monto y que deudas y reposiciones se calculan desde asistencias y pagos, sin tablas extra.

| Tabla | Campos principales | Notas |
| --- | --- | --- |
| sucursales | nombre, dirección, teléfono, prefijo de folio, activa | Se agregan desde el sistema sin tocar código |
| alumnos | nombre, fecha de nacimiento, tutor y teléfono, escuela de procedencia, alergias o notas, personas autorizadas para recoger, foto, fecha de inscripción, estado | Estado activo o baja; la baja conserva el historial |
| maestros | nombre, fecha de nacimiento, teléfono, correo, dirección, especialidad, fecha de ingreso, contacto de emergencia, foto, activo | La edad se calcula desde la fecha de nacimiento |
| grupos | sucursal, nombre, días y horario, precio por sesión, activo | El precio es editable; no altera pagos pasados |
| bloques\_grupo | grupo, materia, orden, duración en minutos, maestro | Define la mezcla de Inglés y Robótica |
| grupo\_alumnos | grupo, alumno, fecha de alta, fecha de baja | Un alumno puede estar en varios grupos y sucursales |
| sesiones | grupo, fecha, estado (programada, impartida, cancelada), es\_extra | Se generan desde el horario del grupo |
| sesion\_maestros | sesión, maestro, pagado, fecha de pago | Una fila por maestro por sesión; el suplente reemplaza al titular |
| asistencias | sesión, alumno, estado (asistió o faltó), es\_reposición, repone\_a, pago | Una asistencia con pago vacío es deuda |
| pagos | folio, alumno, sucursal, tipo (inscripción o sesión), monto, método (efectivo o transferencia), fecha, estado (vigente o cancelado) | El monto se guarda en el pago, no se lee del grupo |

**Cómo se calculan los casos especiales**

- **Deuda:** asistencias con estado "asistió" y sin pago. El listado de quién debe es una consulta sobre esa condición.
- **Reposición pendiente:** asistencias con estado "faltó" que tienen pago y aún no tienen otra asistencia que la reponga.
- **Reposición hecha:** nueva asistencia en otro grupo con es\_reposición activo, apuntando a la falta original y al mismo pago, sin cobro nuevo.
- **Anulación:** el pago pasa a estado cancelado y la asistencia se deshace; el folio no se reutiliza.
- **Fotos:** se guardan como archivos en una carpeta local y la base solo guarda la ruta.

## Módulos y pantallas

La pantalla más importante es el cobro rápido, porque en un jueves como el de El Refugio pasan unos 35 alumnos uno por uno antes de las 3 pm.

| Módulo | Qué hace | Prioridad |
| --- | --- | --- |
| Acceso | Contraseña para abrir el sistema | Alta |
| Dashboard | Gráficas al abrir: cobrado hoy, cobrado en la semana (total y por sucursal), alumnos activos por sucursal | Alta |
| Cobro de clase | Lista del grupo del día; un toque en el alumno registra asistencia, cobro e imprime ticket; botones para método de pago y para deshacer | Alta |
| Alumnos | Alta, edición, ficha con foto, baja con historial | Alta |
| Grupos y sesiones | Crear grupos con bloques y precio, ver sesiones generadas, cancelar, cambiar maestro, crear sesión extra | Alta |
| Sucursales | Alta y edición de sucursales | Media |
| Maestros | Alta, edición, ficha con foto, asignación a grupos | Media |
| Deudas | Listado de quién debe y cuánto, con cobro posterior y ticket | Alta |
| Reposiciones | Lista de clases pagadas pendientes de reponer y registro de la reposición | Media |
| Pago a maestros | Sesiones impartidas con marca de pagado por maestro, individual o varias a la vez | Media |
| Asistencia de grupo | Consulta de asistencia por grupo y fechas | Media |
| Respaldos | Copia automática a la USB y aviso si lleva varios días sin respaldar | Alta |

**Ticket térmico:** contiene escuela y sucursal, fecha, alumno, grupo y materia, monto, método de pago y folio. Se genera como una página de ancho angosto, lista para imprimirse desde el navegador en la impresora térmica, sin cuadro de diálogo en cada cobro, y se puede reimprimir con el mismo folio. Falta confirmar el ancho del rollo (58 o 80 mm).

**Diseño:** moderno y colorido, con tarjetas de datos limpias, jerarquía clara, tonos pastel y formas redondeadas, que es una de las tendencias de [dashboards de 2026](https://www.muz.li/blog/best-dashboard-design-examples-inspirations-for-2026). La pantalla de cobro debe priorizar botones grandes y pocos pasos sobre la decoración.

## Arquitectura y stack

El sistema corre completo en la laptop del dueño: una aplicación web local, una base de datos en un archivo y un respaldo automático a la USB.

&#91;embedded content: arquitectura local · 5 componentes y 2 dispositivos\]

El navegador habla con un servidor local; la base y las fotos viven en la laptop y solo el respaldo sale a la USB.

| Capa | Recomendación | Por qué |
| --- | --- | --- |
| Interfaz | Plantillas Jinja2 con HTMX o Alpine.js, y Chart.js incluida localmente | Sin proceso de compilación; se abre en el navegador sin internet |
| Servidor | Python con FastAPI, escuchando solo en 127.0.0.1 | Ligero para 8 GB de RAM y sin acceso desde otros equipos |
| Base de datos | SQLite en modo WAL con SQLAlchemy y migraciones con Alembic | Un solo archivo y cambios de estructura controlados |
| Dinero y folios | Montos como enteros en centavos; folio generado dentro de una transacción | Los totales siempre cuadran y el folio nunca se repite |
| Acceso | Contraseña guardada con hash (argon2 o bcrypt) | Protege los datos de menores y los pagos |
| Fotos | Carpeta local; la base guarda la ruta | Evita inflar la base |
| Ticket | Página de ancho angosto con impresión silenciosa de Chrome (--kiosk-printing) o envío directo ESC/POS | Evita un cuadro de impresión en cada uno de los 35 cobros |
| Respaldo | API de respaldo de SQLite hacia la USB | Copia consistente aunque el sistema esté en uso |
| Arranque | Acceso directo que levanta el servidor y abre el navegador | El dueño no ve terminales |
| Empaquetado | Carpeta portable con Python incluido o instalador; probar con el antivirus pronto | PyInstaller a veces da falsos positivos en Windows |

Docker puede servirte en tu desarrollo, pero no se recomienda en la laptop del dueño por su memoria. Una base en la nube como Supabase queda fuera de esta versión porque requiere conexión. Si prefieres React para tu portafolio, también funciona, pero suma un paso de compilación.

## Fases de desarrollo

El desarrollo va en cinco fases, y cada una termina en una puerta de prueba antes de seguir con la siguiente.

&#91;embedded content: ruta de desarrollo · 5 fases con su puerta de prueba\]

El rombo de cada fase es su puerta: no se avanza hasta cumplirla. La Fase 3 va resaltada porque es el corazón del sistema. No pongo fechas porque dependen de las horas semanales que dediques; con ese dato las calculo.

## Criterios de calidad y pruebas

El sistema está bien si un jueves completo de El Refugio se cobra sin errores y sin filas largas.

**Caso de prueba base:** grupo de El Refugio, jueves de 3 a 5 pm, 1 h de Inglés y 1 h de Robótica, dos maestros, 35 alumnos y $140 por sesión. Si los 35 pagan, el total del día debe ser $4,900.

| Prueba | Resultado esperado |
| --- | --- |
| Cobrar a los 35 alumnos | Un ticket por alumno; cada cobro toma pocos segundos (meta propuesta: menos de 5 s) |
| Total del día en el dashboard | Coincide con la suma de tickets vigentes ($4,900 en el caso base) |
| Deshacer una asistencia | Resta el monto del total y deja el ticket como cancelado |
| Alumno que asiste sin pagar | Aparece en deudas con $140; al cobrarlo sale del listado y genera ticket |
| Falta con clase pagada | Aparece en reposiciones; al reponerla en otro grupo el total cobrado no cambia |
| Cambio de precio del grupo | Los cobros anteriores conservan su monto |
| Sesión cancelada | No genera faltas, deuda ni pago pendiente a maestros |
| Dos maestros en una sesión | Dos marcas de pago independientes; el suplente reemplaza al titular |
| Reimpresión | Mismo folio y mismos datos que el ticket original |
| Sin internet | Todo funciona y los datos siguen ahí al reiniciar la laptop |
| Respaldo | La USB se puede restaurar en otra laptop limpia (se prueba la restauración, no solo la copia) |

**Errores que el sistema debe evitar a toda costa:** cobrar dos veces una clase repuesta, perder datos por falta de respaldo, y reutilizar o borrar un folio.

## Riesgos, pendientes y siguiente acción

El mayor riesgo es perder los datos si la laptop falla, y por eso el respaldo es un requisito y no un extra.

| Riesgo o pendiente | Qué hacer |
| --- | --- |
| Pérdida de datos por una sola laptop | Respaldo automático a la USB, aviso si lleva varios días sin respaldar y prueba de restauración; una copia en la nube queda como mejora si el dueño tiene cuenta de Google |
| Docker en una laptop de 8 GB | Evitarlo en la máquina del dueño y usar una app ligera; Docker puede quedar solo para tu desarrollo |
| Impresora térmica | Confirmar modelo y ancho de rollo (58 u 80 mm) y probar una página de ticket real con impresión silenciosa antes de construir el resto; un cuadro de diálogo por cada cobro frenaría la fila de 35 alumnos |
| Datos de menores (tutores, alergias, fotos) | Contraseña de acceso, datos solo en la laptop y respaldos protegidos |
| Alumnos que ya existen en cuadernos y Excel | No se habló de importarlos; definir si se capturan a mano o con una carga inicial desde Excel |
| Precios de los grupos | Aún se desconocen; son un campo editable, no un valor fijo |
| Supuestos sin confirmar | Contraseña de acceso, folio con prefijo por sucursal, español y pesos mexicanos |
| Fuera del alcance actual | Recordatorios por WhatsApp, varios usuarios, app móvil y uso desde más de una computadora |

**Siguiente acción recomendada:**

1. Confirmar con el dueño los supuestos de la tabla y el ancho del rollo de la impresora.
2. Probar un ticket de ejemplo en su impresora térmica con impresión silenciosa, imprimiendo varios seguidos como en un jueves real.
3. Empezar la Fase 1 con el esqueleto del sistema, la base de datos y el respaldo a USB.
