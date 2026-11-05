# ICIA — Guía de estudio por fases

Este documento explica el proyecto **ICIA** como si estuvieras aprendiendo a programarlo desde cero. La idea es que puedas leerlo por fases, entender qué problema resolvimos, qué piezas construimos y qué conceptos conviene dominar antes de avanzar.

> Estado actual: **Fases 1, 2 y 3 completadas**. La siguiente fase es la **Fase 4: grupos, sesiones, maestros y pago a maestros**. La suite actual tiene **165 pruebas automatizadas**.

---

## 1. Cómo leer esta guía

Cada fase tiene la misma estructura:

1. **Problema:** qué necesidad del negocio resolvemos.
2. **Solución:** qué construimos técnicamente.
3. **Conceptos:** ideas de programación que aparecen.
4. **Archivos clave:** dónde está el código.
5. **Pruebas:** cómo comprobamos que funciona.
6. **Preguntas de repaso:** para estudiar sin memorizar.

La regla más importante del proyecto es: **una tarea a la vez**. Primero se implementa, luego se prueba, después se documenta y finalmente se hace commit. No se adelanta la siguiente fase.

---

## 2. Mapa general del proyecto

```text
Navegador
   |
   v
FastAPI + Jinja2
   |
   v
Routers  ->  Services  ->  SQLAlchemy  ->  SQLite
   |            |
   |            +-- reglas de negocio
   +-- páginas HTML y respuestas JSON
```

La aplicación es un **monolito local**:

- Corre en `127.0.0.1:8000`.
- No depende de internet.
- Usa SQLite como única fuente de verdad.
- Guarda el dinero en centavos enteros.
- Genera folios únicos y nunca los reutiliza.
- Está pensada para una sola persona: el dueño de la escuela.

| Fase | Objetivo | Estado |
| --- | --- | --- |
| Fase 1 | Base técnica, base de datos, datos semilla y respaldo USB | Completada |
| Fase 2 | Cobro Express, tickets, deudas, anulación, login y descarga de tickets | Completada |
| Fase 3 | Dashboard, deudas y reposiciones | Completada |
| Fase 4 | Grupos, sesiones, maestros y pago a maestros | Siguiente |
| Fase 5 | Empaquetado, impresión real y puesta en marcha en Windows | Planeada |

---

## 3. Fase 1 — Esqueleto, base de datos y respaldo USB

### 3.1 Problema

Antes de cobrar necesitábamos una base confiable: un servidor local, una base de datos, datos de prueba y una forma de respaldar la información. Sin esta fase, cualquier función posterior sería inestable.

### 3.2 Qué construimos

- La estructura del proyecto con FastAPI.
- La configuración central con `APP_NAME = "ICIA"`.
- La conexión a SQLite con modo WAL.
- Los modelos de la base de datos y la migración inicial con Alembic.
- Los datos semilla:
  - 4 sucursales: `TOT`, `OCO`, `PON`, `REF`.
  - 2 maestros.
  - 1 grupo de El Refugio: **Jueves 3-5 PM**.
  - 35 alumnos.
  - Precio del grupo: **$140.00**, guardado como `14000` centavos.
- El servicio de respaldo con la API de SQLite.
- Las primeras pruebas automatizadas.

### 3.3 Conceptos importantes

**FastAPI** es el servidor web. Recibe peticiones del navegador y responde con HTML o JSON.

**SQLAlchemy** es la capa que traduce objetos de Python a tablas de SQLite. En lugar de escribir SQL por todos lados, usamos modelos como `Alumno`, `Grupo` y `Pago`.

**Alembic** es el sistema de migraciones. Piensa en él como el “control de versiones” de la estructura de la base de datos. Si mañana agregamos una columna, Alembic registra ese cambio de forma ordenada.

**SQLite en modo WAL** significa Write-Ahead Logging. Es una forma de que las lecturas no bloqueen a las escrituras. Para una aplicación local con cobros rápidos, es una pieza clave.

**Datos semilla** son datos iniciales reproducibles. Nos permiten probar el sistema sin capturar 35 alumnos a mano cada vez.

**Backup API de SQLite** permite copiar la base de datos de forma consistente aunque la aplicación esté en uso. No se debe copiar el archivo `.db` con el explorador mientras se está escribiendo.

### 3.4 Archivos clave

| Archivo | Qué hace |
| --- | --- |
| `app/main.py` | Crea la aplicación FastAPI y registra routers. |
| `app/core/config.py` | Define `APP_NAME`, rutas, puerto y configuraciones. |
| `app/core/database.py` | Crea el engine de SQLite y aplica los PRAGMAs. |
| `app/models/` | Define las tablas con SQLAlchemy. |
| `app/services/seed.py` | Carga sucursales, maestros, grupo y alumnos de prueba. |
| `app/services/backup_service.py` | Copia la base de datos y verifica integridad. |
| `alembic/` | Migraciones de la base de datos. |
| `schemas/database_schema.sql` | Contrato técnico del esquema. |

### 3.5 Pruebas de esta fase

- `tests/test_database.py`
- `tests/test_migrations.py`
- `tests/test_models.py`
- `tests/test_seed.py`
- `tests/test_backup.py`
- `tests/test_config.py`

Estas pruebas verifican que la base se crea, que las tablas existen, que los datos semilla son correctos y que el respaldo conserva la integridad.

### 3.6 Preguntas de repaso

1. ¿Por qué el dinero se guarda como entero en centavos y no como `FLOAT`?
2. ¿Qué ventaja da SQLite en modo WAL?
3. ¿Para qué sirve Alembic si ya tenemos modelos de SQLAlchemy?
4. ¿Por qué no se debe copiar `icia.db` con el explorador mientras la app está abierta?
5. ¿Qué diferencia hay entre datos semilla y datos reales?

---

## 4. Fase 2 — Cobro Express y tickets térmicos

Esta es la fase más importante del sistema: el momento en que el dueño cobra a los alumnos.

### 4.1 Problema

El dueño necesitaba cobrar rápido, marcar asistencia, imprimir un ticket y dejar registro de deudas y anulaciones. Todo debía ocurrir sin internet, sin filas largas y sin errores financieros.

### 4.2 La regla central: todo o nada

El cobro ejecuta tres acciones dentro de una sola transacción:

1. Registrar la asistencia.
2. Registrar el pago con el precio vigente.
3. Generar el folio y dejar listo el ticket.

Si algo falla, se revierte todo. No debe quedar una asistencia sin pago ni un pago sin asistencia.

Piensa en una transferencia bancaria: no se descuenta el dinero de una cuenta si no se abona en la otra. Aquí pasa lo mismo.

### 4.3 Tareas de la fase

| Tarea | Qué se hizo |
| --- | --- |
| 2.1 | Pantalla de Cobro Express con sucursal, grupo, sesión y lista alfabética. |
| 2.2 | Atajos de teclado: `Espacio`, `F1`, `F2`, `F3`, flechas y `Esc`. |
| 2.3 | Folios atómicos por sucursal, por ejemplo `REF-0001`. |
| 2.4 | Transacción atómica de asistencia + pago + folio. |
| 2.5 | Ticket térmico de 58/80 mm con identidad `ICIA`. |
| 2.6 | Botón “Asistió sin pagar” para registrar deuda. |
| 2.7 | Botón “Deshacer asistencia” con pago cancelado y folio conservado. |
| 2.8 | Reimpresión de ticket por folio con los mismos datos. |
| 2.9 | Login local con contraseña hasheada y sesión de 12 horas. |
| 2.10 | Descarga de ticket en HTML autocontenido. |

### 4.4 Folios: el número que nunca se repite

Un folio tiene el formato:

```text
{PREFIJO_SUCURSAL}-{CONSECUTIVO_DE_4_DIGITOS}
```

Ejemplos:

```text
REF-0001
REF-0002
TOT-0001
```

El consecutivo vive en la tabla `folio_contadores`. Se incrementa dentro de una transacción `BEGIN IMMEDIATE`, que bloquea temporalmente la escritura para evitar que dos cobros obtengan el mismo número.

Regla de oro: **un folio nunca se reutiliza ni se borra**. Si se anula un pago, el pago cambia a estado `cancelado`, pero conserva su folio.

### 4.5 Tickets térmicos

El ticket es una página HTML independiente con estilos para impresión:

- Ancho configurable de 58 mm u 80 mm.
- Encabezado `ICIA`.
- Sucursal, fecha, alumno, grupo, materias, método de pago, monto y folio.
- Botón de impresión.
- Autoimpresión cuando se abre con `?auto=1`.
- Reimpresión por folio.

La descarga de ticket genera un archivo HTML **autocontenido**: el CSS va dentro del archivo, así que se puede abrir sin conexión y conserva el diseño.

### 4.6 Deuda y anulación

**Deuda:** el alumno asistió pero no pagó. Se crea una asistencia con `pago_id = NULL`. No hay folio porque todavía no hay pago.

**Anulación:** se deshace una asistencia. Si había pago, el pago pasa a `cancelado` y se guarda la fecha y el motivo. La asistencia se elimina. El folio se conserva para auditoría.

Esto enseña una idea importante: en sistemas financieros no siempre se borra. Muchas veces se **cancela** y se conserva el historial.

### 4.7 Login y seguridad

La contraseña no se guarda en texto plano. Se guarda un hash con `bcrypt` en la tabla `configuracion`, bajo la clave `auth_password_hash`.

La sesión usa una cookie llamada `icia_session`:

- `HttpOnly`.
- `SameSite=Lax`.
- Expiración de 12 horas por defecto.
- Firma HMAC para detectar manipulaciones.

En el primer arranque, si no existe contraseña, el sistema muestra una pantalla para crearla. No hay contraseña por defecto.

### 4.8 Un bug que encontró la prueba de aceptación

La prueba de aceptación de Fase 2 descubrió un problema real: la dependencia de autenticación leía la contraseña y dejaba una transacción abierta. Después, el cobro intentaba hacer `BEGIN IMMEDIATE` y fallaba porque la sesión ya estaba en una transacción.

La solución fue cerrar esa lectura con `db.rollback()` antes de continuar.

Lección: las pruebas unitarias no siempre detectan la interacción entre piezas. Las pruebas de aceptación, que recorren el flujo completo, sí.

### 4.9 Prueba de aceptación de Fase 2

El criterio fue:

- Cobrar 10 alumnos consecutivos en menos de 30 segundos.
- Generar tickets.
- Registrar deuda.
- Anular una asistencia.
- Conservar folios únicos.
- Mostrar `ICIA` en login y tickets.

La prueba se ejecutó con una base temporal y un servidor real. Resultado:

```text
10 cobros consecutivos: 0.051 s
Folios generados: REF-0001 a REF-0010
Deuda, anulación y descarga HTML: OK
ACEPTACIÓN FASE 2: OK
```

### 4.10 Archivos clave

| Archivo | Qué hace |
| --- | --- |
| `app/routers/pos.py` | Rutas de Cobro Express, tickets y descarga. |
| `app/services/cashier.py` | Cobro atómico, deuda y anulación. |
| `app/services/folios.py` | Consecutivos por sucursal. |
| `app/services/pos.py` | Listado de sucursales, grupos, sesiones y roster. |
| `app/services/thermal_printer.py` | Datos del ticket y consulta por folio. |
| `app/routers/auth.py` | Login, primer uso y logout. |
| `app/core/security.py` | Hash, cookie, token y protección de rutas. |
| `app/templates/pos.html` | Pantalla de Cobro Express. |
| `app/templates/ticket.html` | Ticket térmico y modo descarga. |
| `app/static/js/pos.js` | Atajos, cobro, deuda y anulación sin recargar. |
| `app/static/css/app.css` | Estilos de la aplicación. |
| `app/static/css/ticket.css` | Estilos del ticket térmico. |
| `tests/test_aceptacion_fase2.py` | Flujo completo de aceptación. |

### 4.11 Preguntas de repaso

1. ¿Qué significa que un cobro sea atómico?
2. ¿Por qué se usa `BEGIN IMMEDIATE` para los folios?
3. ¿Qué pasa con el folio cuando se anula un pago?
4. ¿Cómo se representa una deuda en la base de datos?
5. ¿Por qué la contraseña se guarda como hash y no como texto?
6. ¿Qué diferencia hay entre reimprimir un ticket y descargarlo?
7. ¿Por qué la prueba de aceptación encontró un bug que las pruebas unitarias no vieron?

---

## 5. Fase 3 — Dashboard, deudas y reposiciones

### 5.1 Problema

En la Fase 2 logramos cobrar rápidamente, emitir tickets y registrar asistencias. Pero una escuela no se maneja a ciegas: el dueño necesita saber al instante cuánto dinero ingresó hoy, cuánto lleva en la semana, qué alumnos deben clases que ya tomaron y qué alumnos faltaron pero tienen derecho a reponer su clase.

Además, cuando un alumno moroso paga, ese dinero debe reflejarse de inmediato en los ingresos sin descuadrar la caja; y cuando un alumno repone una clase, esa reposición **nunca debe generar un cobro nuevo** porque la clase ya fue pagada.

### 5.2 Qué construimos

Completamos las 5 tareas de la Fase 3:

- **Tarea 3.1 — Dashboard con KPIs (`/dashboard`):** cuatro tarjetas principales con métricas clave:
  1. **Cobrado hoy:** monto total en centavos formateado a MXN y cantidad de tickets emitidos hoy.
  2. **Cobrado en la semana:** acumulado desde el lunes hasta hoy con su número de tickets.
  3. **Deudas pendientes:** cantidad de asistencias sin pago y monto pendiente por cobrar.
  4. **Alumnos activos:** total de alumnos inscritos en estado activo.
- **Tarea 3.2 — Gráfica de recaudación por sucursal con Chart.js local:**
  - Endpoint JSON `/dashboard/recaudacion` con el desglose semanal por sucursal (`TOT`, `OCO`, `PON`, `REF`).
  - Librería `chart.umd.min.js` (Chart.js 4.6.1) guardada de forma 100% local en `app/static/vendor/chart.js/`, cumpliendo la regla inviolable de cero dependencias de internet en runtime.
  - Script `dashboard.js` que consulta el endpoint local y dibuja una gráfica de barras responsiva.
- **Tarea 3.3 — Módulo de cobranza de deudas (`/deudas`):**
  - Listado de todos los alumnos que tienen asistencia registrada sin pago o con pago cancelado (vía la vista `v_deudas`).
  - Botón de cobro rápido con selección de método (Efectivo o Transferencia).
  - Al cobrar una deuda, se ejecuta una transacción atómica: asigna folio consecutivo atómico, crea el registro `Pago`, actualiza la `Asistencia`, actualiza de inmediato el dashboard e imprime el ticket térmico mediante un `iframe` silencioso.
- **Tarea 3.4 — Módulo de reposiciones pendientes (`/reposiciones`) y "Marcar falta":**
  - Botón **"Marcar falta"** en Cobro Express: permite registrar la inasistencia de un alumno que ya pagó, conservando intacto su pago y folio, y enviándolo automáticamente a la lista de reposiciones.
  - Pantalla `/reposiciones`: lista las faltas con pago vigente y permite seleccionar una sesión programada de **otro grupo**.
  - Al registrar la reposición, se crea una nueva `Asistencia` con `es_reposicion = 1`, `repone_a_id = falta.id` y reutiliza el mismo `pago_id`. **Cero cobros nuevos, cero folios nuevos y cero tickets.**
- **Tarea 3.5 — Pruebas de consistencia y prueba integral de aceptación (`tests/test_aceptacion_fase3.py`):**
  - Validaciones de borde: sesiones destino canceladas o de grupos inactivos quedan excluidas.
  - Bloqueo estricto de anulación: una falta que ya fue repuesta no puede ser deshecha en la sesión origen.
  - Escenario integral: 2 cobros + 1 falta + 1 deuda + reposición a otro grupo + cobro de deuda = totales matemáticamente exactos.

### 5.3 Conceptos importantes explicados para un alumno

#### A. Vistas de base de datos (SQL Views) como contratos
En lugar de escribir consultas gigantescas con múltiples `JOIN` en cada parte del código, SQLite soporta **Vistas** (`CREATE VIEW`).
- `v_deudas`: une `asistencias`, `alumnos`, `sesiones`, `grupos` y `sucursales` donde el estado es `asistio` y `pago_id IS NULL`. Para el código Python, consultar `v_deudas` es tan simple como hacer un `SELECT * FROM v_deudas`.
- `v_reposiciones_pendientes`: busca asistencias con estado `falto`, con pago vigente, que aún no tengan otra asistencia que las reponga (`NOT EXISTS (SELECT 1 FROM asistencias r WHERE r.repone_a_id = a.id)`).

#### B. La regla sagrada de la reposición: ¿por qué no hay un nuevo Pago?
Si un alumno paga $140.00 por su clase del jueves pero no asiste por enfermedad, la escuela ya tiene su dinero. Cuando el alumno viene el sábado a reponer en otro grupo:
1. Asistió al salón del sábado (se registra una fila en `asistencias`).
2. Pero **no debe ingresar dinero a caja ni emitirse un nuevo folio**.
3. Por eso, en la base de datos la nueva asistencia tiene:
   - `es_reposicion = 1`
   - `repone_a_id = id_de_la_falta`
   - `pago_id = id_del_pago_original` (reutilizado)
4. El total recaudado en el dashboard permanece exactamente igual antes y después de reponer.

#### C. Librerías frontend sin CDN (Offline estricto)
Muchos tutoriales web te enseñan a agregar Chart.js así:
`<script src="https://cdn.jsdelivr.net/..."></script>`
En este proyecto **eso está prohibido**. Si el dueño está en una sucursal sin señal o se cae el internet, la pantalla no cargaría o la gráfica se rompería.
Descargamos el archivo JavaScript compilado (`chart.umd.min.js`), lo colocamos dentro de `app/static/vendor/chart.js/` y lo servimos como archivo estático local.

#### D. Transacción atómica al cobrar deudas
Cobrar una deuda no es simplemente "cambiar un texto en la pantalla". En `cashier.py`, la función `cobrar_deuda()` ejecuta dentro de `BEGIN IMMEDIATE`:
1. Verifica que la deuda siga pendiente (evita cobros duplicados simultáneos).
2. Genera el siguiente folio atómico de la sucursal (ej. `REF-0025`).
3. Inserta el registro `Pago` con fecha y hora actual.
4. Vincula `asistencia.pago_id = nuevo_pago.id`.
5. Hace `commit()`.
Si la luz se va o la base de datos se traba a la mitad, se hace `rollback()` y la base de datos queda limpia, sin pagos huérfanos.

### 5.4 Archivos clave de la Fase 3

| Archivo | Qué hace |
| --- | --- |
| `app/routers/dashboard.py` | Ruta `/dashboard` con las tarjetas KPI y `/dashboard/recaudacion` para la gráfica. |
| `app/routers/debts.py` | Rutas de `/deudas` (listado y cobro) y `/reposiciones` (listado y asignación a otro grupo). |
| `app/services/reports.py` | Consultas analíticas: `resumen_dashboard()`, `recaudacion_por_sucursal()`, `listar_deudas()`, `listar_reposiciones_pendientes()`. |
| `app/services/cashier.py` | Reglas transaccionales: `cobrar_deuda()`, `marcar_falta()`, `registrar_reposicion()` y protección en `deshacer_asistencia()`. |
| `app/static/vendor/chart.js/` | Archivo vendorizado local de Chart.js (sin CDN). |
| `app/static/js/dashboard.js` | Código del cliente que inicializa la gráfica con Chart.js local. |
| `app/templates/dashboard.html` | Plantilla del dashboard con KPIs y contenedor de la gráfica. |
| `app/templates/debts/index.html` | Plantilla de cobro rápido de deudas con ticket embebido. |
| `app/templates/debts/repositions.html` | Plantilla para ver faltas y elegir el grupo/sesión destino para reponer. |
| `tests/test_dashboard.py` | Pruebas de KPIs, fechas de corte semanal y gráfica local. |
| `tests/test_debts.py` | Pruebas de cobro rápido de deudas y prevención de cobro duplicado. |
| `tests/test_repositions.py` | Pruebas de faltas, rechazo de mismo grupo, rechazo de sesiones canceladas y bloqueo de anulación. |
| `tests/test_aceptacion_fase3.py` | Escenario integral de aceptación de la Fase 3. |

### 5.5 Prueba de aceptación de Fase 3

El criterio formal de aceptación del proyecto para esta fase fue:
> *"Al cobrar una deuda, el dashboard actualiza automáticamente los totales recaudados; reponer una clase no genera cobro nuevo."*

Construimos `tests/test_aceptacion_fase3.py`, que simula un flujo real de la escuela:
1. Se abre sesión en El Refugio y se cobra a 2 alumnos ($280.00 en total).
2. Alumno 2 se marca como **Falta** (pago se conserva, clase queda pendiente de reposición).
3. Alumno 3 ingresa como **Asistió sin pagar** (deuda de $140.00).
4. **Verificación intermedia del Dashboard:** refleja $280.00 recaudados, 2 tickets vigentes, 1 deuda pendiente ($140.00).
5. Se repone la falta del Alumno 2 asignándolo a la sesión de Robótica de Tototlán:
   - Se valida que **no se generó ningún pago nuevo**.
   - El dashboard y la recaudación se mantienen exactamente en $280.00.
   - La lista de reposiciones pendientes baja a 0.
6. Se cobra la deuda del Alumno 3 desde el módulo `/deudas`:
   - Se genera el folio `REF-0003` y ticket térmico.
   - La lista de deudas baja a 0.
   - El dashboard y la recaudación saltan automáticamente a **$420.00** con **3 tickets vigentes** y **$0.00 en deudas**.

Resultado de la prueba: **PASÓ AL 100% en 1.14 segundos.**

### 5.6 Preguntas de repaso

1. ¿Por qué el dinero recaudado en el dashboard no cambia cuando un alumno repone una clase?
2. ¿Cómo sabe SQLite si una falta ya fue repuesta o sigue pendiente en `v_reposiciones_pendientes`?
3. ¿Por qué guardamos Chart.js en `app/static/vendor/` en lugar de cargarlo con un script de internet?
4. Si un alumno tiene una falta ya repuesta en otro grupo, ¿por qué el sistema le prohíbe hacer clic en "Deshacer asistencia" en la sesión original?
5. ¿Qué tablas se modifican cuando se hace clic en "Cobrar deuda"?
6. Si una sucursal no ha tenido ningún cobro en la semana, ¿debe aparecer en la gráfica de recaudación o debe ocultarse? (Pista: debe aparecer con $0.00).
7. ¿Cómo se evita que dos personas cobren la misma deuda al mismo tiempo generando dos cobros por error?

---

## 6. Fase 4 — Grupos, sesiones y pago a maestros

### 6.1 Problema

El sistema necesita administrar la operación académica: sucursales, grupos, horarios, sesiones, maestros y suplencias.

### 6.2 Qué se planea construir

- CRUD de sucursales y grupos.
- Grupos con varios bloques: Inglés y Robótica.
- Generación automática de sesiones.
- Cancelación de sesiones sin efectos financieros.
- Sesiones extra.
- Sustitución de maestro titular por suplente.
- Pantalla de pago a maestros: solo marcar pagado/pendiente.
- CRUD de alumnos y maestros con foto local.
- Consulta de asistencia por grupo y fechas.

### 6.3 Idea clave

El sistema **no calcula sueldos**. Solo registra si una sesión ya se pagó o sigue pendiente. Esa decisión evita meter reglas de nómina que no fueron solicitadas.

---

## 7. Fase 5 — Empaquetado y puesta en marcha

### 7.1 Problema

El dueño no debe ver terminales ni comandos. Debe abrir el sistema con doble clic en Windows.

### 7.2 Qué se planea construir

- `run_app.bat` para iniciar Uvicorn y abrir Chrome.
- Impresión silenciosa con `--kiosk-printing`.
- Empaquetado con PyInstaller o carpeta portable.
- Prueba de restauración desde USB en otra laptop.
- Prueba completa con 35 alumnos y total de $4,900.

### 7.3 Criterio de aceptación de Fase 5

El dueño hace doble clic, el sistema abre sin terminal, imprime sin diálogo y puede restaurar los datos desde una USB en una laptop limpia.

---

## 8. Conceptos transversales

Estos conceptos aparecen en todas las fases y conviene dominarlos.

### 8.1 Offline-first

Ningún recurso debe venir de internet en tiempo de ejecución. Fuentes, CSS, JavaScript y librerías viven en `app/static/vendor/` o en el proyecto.

### 8.2 Dinero en centavos

Nunca usar `FLOAT` para dinero. Se guarda `14000` y se muestra `$140.00` solo en la interfaz. Esto evita errores de redondeo.

### 8.3 Transacciones

Una transacción agrupa varias operaciones. Si una falla, se revierte todo. Es la base de la confiabilidad del cobro.

### 8.4 Trazabilidad

No se borra el historial. Los pagos se cancelan, los alumnos se dan de baja y las asistencias se conservan o se marcan según la regla del negocio.

### 8.5 Pruebas

- **Prueba unitaria:** verifica una pieza pequeña.
- **Prueba de integración:** verifica varias piezas juntas.
- **Prueba de aceptación:** recorre el flujo completo como lo haría el usuario.

### 8.6 Git y ramas

Flujo recomendado:

```bash
git switch main
git pull --ff-only origin main
git switch -c fase-3-dashboard
```

Al terminar una tarea:

```bash
.venv/bin/python -m pytest -q
git add .
git commit -m "feat: descripcion corta"
git push -u origin fase-3-dashboard
```

Después se abre el pull request, se revisa, se hace merge y se borra la rama.

---

## 9. Glosario

| Término | Significado |
| --- | --- |
| FastAPI | Framework de Python para crear la API y servir la aplicación. |
| Jinja2 | Motor de plantillas HTML. |
| SQLAlchemy | ORM para trabajar con la base de datos desde Python. |
| Alembic | Herramienta de migraciones de base de datos. |
| SQLite | Base de datos local en un solo archivo. |
| WAL | Modo de SQLite que mejora la concurrencia entre lecturas y escrituras. |
| Router | Archivo que agrupa rutas de FastAPI. |
| Service | Archivo con lógica de negocio. |
| Modelo | Representación Python de una tabla. |
| Folio | Número único de un pago. |
| Centavos | Unidad entera para guardar dinero. |
| bcrypt | Algoritmo para hashear contraseñas. |
| Cookie | Pequeño dato que el navegador guarda para mantener la sesión. |
| KPI | Indicador clave de desempeño. |
| Reposición | Clase pagada que se recupera después de una falta. |
| CDN | Servicio externo que sirve archivos por internet; prohibido en runtime. |

---

## 10. Ruta de estudio recomendada

1. Lee `PRD.md` para entender el negocio.
2. Lee `ARCHITECTURE.md` para entender la estructura técnica.
3. Lee `ROADMAP_TASKS.md` para ver el orden de las tareas.
4. Estudia esta guía por fases.
5. Abre los archivos clave de cada fase.
6. Ejecuta las pruebas y lee los nombres de los tests.
7. Responde las preguntas de repaso sin mirar el código.
8. Al empezar una tarea nueva, crea una rama y sigue el ciclo: implementar, probar, documentar, commit.

---

## 11. Comandos útiles

```bash
# Ejecutar todas las pruebas
.venv/bin/python -m pytest -q

# Ejecutar solo la aceptación de Fase 2
.venv/bin/python -m pytest -q tests/test_aceptacion_fase2.py

# Cargar datos semilla
.venv/bin/python -m app.services.seed

# Levantar el servidor local
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000

# Verificar sintaxis de Python y JavaScript
.venv/bin/python -m compileall -q app tests
node --check app/static/js/pos.js
```

Para pruebas de aceptación, usa una carpeta temporal y no la base real:

```bash
export ICIA_DATA_DIR=/tmp/icia-fase2-live
rm -rf "$ICIA_DATA_DIR"
.venv/bin/alembic upgrade head
.venv/bin/python -m app.services.seed
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001
```

---

## 12. Resumen final

ICIA empezó como una base local confiable y ya tiene el corazón del negocio funcionando: cobrar, asistir, foliar, imprimir, registrar deuda, anular, reimprimir, autenticar y descargar tickets.

Lo que sigue no es “más código porque sí”. Cada fase responde a una necesidad concreta del dueño:

- **Fase 3:** entender el negocio con datos.
- **Fase 4:** administrar la operación académica.
- **Fase 5:** poner el sistema en manos del dueño sin terminales ni complicaciones.

Si puedes explicar cada fase con tus propias palabras y justificar sus decisiones técnicas, entonces ya no estás memorizando: estás entendiendo el proyecto.
