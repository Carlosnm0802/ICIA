PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;

BEGIN;

CREATE TABLE sucursales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    direccion TEXT,
    telefono TEXT,
    prefijo_folio TEXT NOT NULL UNIQUE,
    activa INTEGER NOT NULL DEFAULT 1 CHECK (activa IN (0, 1)),
    creada_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (length(trim(prefijo_folio)) BETWEEN 2 AND 8),
    CHECK (prefijo_folio = upper(prefijo_folio))
);

CREATE TABLE alumnos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    fecha_nacimiento TEXT,
    tutor TEXT,
    telefono_tutor TEXT,
    escuela_procedencia TEXT,
    alergias_notas TEXT,
    personas_autorizadas TEXT,
    foto_ruta TEXT,
    fecha_inscripcion TEXT NOT NULL DEFAULT CURRENT_DATE,
    estado TEXT NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'baja')),
    creado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TEXT,
    CHECK (fecha_nacimiento IS NULL OR fecha_nacimiento GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')
);

CREATE TABLE maestros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    fecha_nacimiento TEXT,
    telefono TEXT,
    correo TEXT,
    direccion TEXT,
    especialidad TEXT,
    fecha_ingreso TEXT,
    contacto_emergencia TEXT,
    foto_ruta TEXT,
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    creado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TEXT,
    CHECK (fecha_nacimiento IS NULL OR fecha_nacimiento GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')
);

CREATE TABLE grupos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sucursal_id INTEGER NOT NULL REFERENCES sucursales(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    nombre TEXT NOT NULL,
    dias_semana TEXT NOT NULL,
    hora_inicio TEXT NOT NULL,
    hora_fin TEXT NOT NULL,
    precio_centavos INTEGER NOT NULL CHECK (precio_centavos >= 0),
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    creado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TEXT,
    UNIQUE (sucursal_id, nombre),
    CHECK (hora_inicio GLOB '[0-9][0-9]:[0-9][0-9]'),
    CHECK (hora_fin GLOB '[0-9][0-9]:[0-9][0-9]'),
    CHECK (hora_fin > hora_inicio)
);

CREATE TABLE bloques_grupo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    grupo_id INTEGER NOT NULL REFERENCES grupos(id) ON UPDATE CASCADE ON DELETE CASCADE,
    materia TEXT NOT NULL CHECK (materia IN ('ingles', 'robotica')),
    orden INTEGER NOT NULL CHECK (orden > 0),
    duracion_minutos INTEGER NOT NULL CHECK (duracion_minutos > 0),
    maestro_id INTEGER NOT NULL REFERENCES maestros(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    UNIQUE (grupo_id, orden)
);

CREATE TABLE grupo_alumnos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    grupo_id INTEGER NOT NULL REFERENCES grupos(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    alumno_id INTEGER NOT NULL REFERENCES alumnos(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    fecha_alta TEXT NOT NULL DEFAULT CURRENT_DATE,
    fecha_baja TEXT,
    creado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (fecha_baja IS NULL OR fecha_baja >= fecha_alta)
);

CREATE TABLE sesiones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    grupo_id INTEGER NOT NULL REFERENCES grupos(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    fecha TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'programada' CHECK (estado IN ('programada', 'impartida', 'cancelada')),
    es_extra INTEGER NOT NULL DEFAULT 0 CHECK (es_extra IN (0, 1)),
    creada_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (grupo_id, fecha),
    CHECK (fecha GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')
);

CREATE TABLE sesion_maestros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sesion_id INTEGER NOT NULL REFERENCES sesiones(id) ON UPDATE CASCADE ON DELETE CASCADE,
    maestro_id INTEGER NOT NULL REFERENCES maestros(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    pagado INTEGER NOT NULL DEFAULT 0 CHECK (pagado IN (0, 1)),
    fecha_pago TEXT,
    UNIQUE (sesion_id, maestro_id)
);

CREATE TABLE folio_contadores (
    sucursal_id INTEGER PRIMARY KEY REFERENCES sucursales(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    ultimo_consecutivo INTEGER NOT NULL DEFAULT 0 CHECK (ultimo_consecutivo >= 0)
);

CREATE TABLE pagos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    folio TEXT NOT NULL UNIQUE,
    alumno_id INTEGER NOT NULL REFERENCES alumnos(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    sucursal_id INTEGER NOT NULL REFERENCES sucursales(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    tipo TEXT NOT NULL CHECK (tipo IN ('inscripcion', 'sesion')),
    monto_centavos INTEGER NOT NULL CHECK (monto_centavos >= 0),
    metodo TEXT NOT NULL CHECK (metodo IN ('efectivo', 'transferencia')),
    fecha TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    estado TEXT NOT NULL DEFAULT 'vigente' CHECK (estado IN ('vigente', 'cancelado')),
    motivo_cancelacion TEXT,
    cancelado_en TEXT,
    creado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (id, alumno_id),
    CHECK (folio GLOB '[A-Z][A-Z0-9-]*-[0-9][0-9][0-9][0-9]'),
    CHECK ((estado = 'cancelado' AND cancelado_en IS NOT NULL) OR (estado = 'vigente'))
);

CREATE TABLE asistencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sesion_id INTEGER NOT NULL REFERENCES sesiones(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    alumno_id INTEGER NOT NULL REFERENCES alumnos(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    estado TEXT NOT NULL CHECK (estado IN ('asistio', 'falto')),
    es_reposicion INTEGER NOT NULL DEFAULT 0 CHECK (es_reposicion IN (0, 1)),
    repone_a_id INTEGER,
    pago_id INTEGER,
    precio_aplicado_centavos INTEGER CHECK (precio_aplicado_centavos IS NULL OR precio_aplicado_centavos >= 0),
    registrada_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (id, alumno_id),
    FOREIGN KEY (pago_id, alumno_id) REFERENCES pagos(id, alumno_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (repone_a_id, alumno_id) REFERENCES asistencias(id, alumno_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CHECK ((es_reposicion = 0 AND repone_a_id IS NULL) OR (es_reposicion = 1 AND repone_a_id IS NOT NULL)),
    CHECK ((es_reposicion = 0) OR (estado = 'asistio')),
    CHECK (repone_a_id IS NULL OR repone_a_id <> id)
);

CREATE TABLE configuracion (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL,
    actualizado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_grupos_sucursal ON grupos(sucursal_id);
CREATE INDEX idx_bloques_grupo_grupo ON bloques_grupo(grupo_id);
CREATE INDEX idx_bloques_grupo_maestro ON bloques_grupo(maestro_id);
CREATE INDEX idx_grupo_alumnos_alumno ON grupo_alumnos(alumno_id);
CREATE UNIQUE INDEX ux_grupo_alumnos_activo ON grupo_alumnos(grupo_id, alumno_id) WHERE fecha_baja IS NULL;
CREATE INDEX idx_sesiones_grupo_fecha ON sesiones(grupo_id, fecha);
CREATE INDEX idx_sesiones_fecha_estado ON sesiones(fecha, estado);
CREATE INDEX idx_sesion_maestros_maestro ON sesion_maestros(maestro_id, pagado);
CREATE INDEX idx_pagos_alumno_fecha ON pagos(alumno_id, fecha);
CREATE INDEX idx_pagos_sucursal_fecha ON pagos(sucursal_id, fecha);
CREATE INDEX idx_pagos_fecha_estado ON pagos(fecha, estado);
CREATE INDEX idx_asistencias_sesion ON asistencias(sesion_id);
CREATE INDEX idx_asistencias_alumno ON asistencias(alumno_id);
CREATE INDEX idx_asistencias_pago ON asistencias(pago_id);
CREATE UNIQUE INDEX ux_asistencias_sesion_alumno ON asistencias(sesion_id, alumno_id) WHERE es_reposicion = 0;
CREATE UNIQUE INDEX ux_asistencias_reposicion ON asistencias(sesion_id, alumno_id, repone_a_id) WHERE es_reposicion = 1;

CREATE TRIGGER trg_sucursal_folio_inicial AFTER INSERT ON sucursales
BEGIN
    INSERT INTO folio_contadores (sucursal_id, ultimo_consecutivo) VALUES (NEW.id, 0);
END;

CREATE TRIGGER trg_pagos_folio_inmutable BEFORE UPDATE OF folio ON pagos
BEGIN
    SELECT RAISE(ABORT, 'El folio de un pago no puede modificarse');
END;

CREATE TRIGGER trg_pagos_no_eliminar BEFORE DELETE ON pagos
BEGIN
    SELECT RAISE(ABORT, 'Los pagos no se eliminan; se cancelan');
END;

CREATE VIEW v_deudas AS
SELECT
    a.id AS asistencia_id,
    a.alumno_id,
    al.nombre AS alumno,
    s.id AS sesion_id,
    s.fecha AS fecha_sesion,
    g.id AS grupo_id,
    g.nombre AS grupo,
    su.id AS sucursal_id,
    su.nombre AS sucursal,
    COALESCE(a.precio_aplicado_centavos, g.precio_centavos) AS monto_centavos
FROM asistencias a
JOIN alumnos al ON al.id = a.alumno_id
JOIN sesiones s ON s.id = a.sesion_id
JOIN grupos g ON g.id = s.grupo_id
JOIN sucursales su ON su.id = g.sucursal_id
LEFT JOIN pagos p ON p.id = a.pago_id
WHERE a.estado = 'asistio'
  AND (a.pago_id IS NULL OR p.estado = 'cancelado');

CREATE VIEW v_reposiciones_pendientes AS
SELECT
    a.id AS asistencia_id,
    a.alumno_id,
    al.nombre AS alumno,
    s.id AS sesion_id,
    s.fecha AS fecha_falta,
    g.id AS grupo_id,
    g.nombre AS grupo,
    p.id AS pago_id,
    p.folio,
    p.monto_centavos
FROM asistencias a
JOIN alumnos al ON al.id = a.alumno_id
JOIN sesiones s ON s.id = a.sesion_id
JOIN grupos g ON g.id = s.grupo_id
JOIN pagos p ON p.id = a.pago_id
WHERE a.estado = 'falto'
  AND p.estado = 'vigente'
  AND NOT EXISTS (
      SELECT 1
      FROM asistencias r
      WHERE r.repone_a_id = a.id
        AND r.estado = 'asistio'
  );

CREATE VIEW v_recaudacion_diaria AS
SELECT
    date(p.fecha) AS fecha,
    p.sucursal_id,
    su.nombre AS sucursal,
    COUNT(*) AS tickets,
    SUM(p.monto_centavos) AS total_centavos
FROM pagos p
JOIN sucursales su ON su.id = p.sucursal_id
WHERE p.estado = 'vigente'
GROUP BY date(p.fecha), p.sucursal_id, su.nombre;

COMMIT;
