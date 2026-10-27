"""esquema inicial

Revision ID: 7edfe740fe74
Revises: 
Create Date: 2026-10-27 13:11:23.442166

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7edfe740fe74'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('alumnos',
    sa.Column('id', sa.Integer(), nullable=True),
    sa.Column('nombre', sa.Text(), nullable=False),
    sa.Column('fecha_nacimiento', sa.Text(), nullable=True),
    sa.Column('tutor', sa.Text(), nullable=True),
    sa.Column('telefono_tutor', sa.Text(), nullable=True),
    sa.Column('escuela_procedencia', sa.Text(), nullable=True),
    sa.Column('alergias_notas', sa.Text(), nullable=True),
    sa.Column('personas_autorizadas', sa.Text(), nullable=True),
    sa.Column('foto_ruta', sa.Text(), nullable=True),
    sa.Column('fecha_inscripcion', sa.Text(), server_default=sa.text('(CURRENT_DATE)'), nullable=False),
    sa.Column('estado', sa.Text(), server_default=sa.text("'activo'"), nullable=False),
    sa.Column('creado_en', sa.Text(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('actualizado_en', sa.Text(), nullable=True),
    sa.CheckConstraint("estado IN ('activo', 'baja')", name='ck_alumnos_estado'),
    sa.CheckConstraint("fecha_nacimiento IS NULL OR fecha_nacimiento GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'", name='ck_alumnos_fecha_nacimiento'),
    sa.PrimaryKeyConstraint('id'),
    sqlite_autoincrement=True
    )
    op.create_table('configuracion',
    sa.Column('clave', sa.Text(), nullable=True),
    sa.Column('valor', sa.Text(), nullable=False),
    sa.Column('actualizado_en', sa.Text(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('clave')
    )
    op.create_table('maestros',
    sa.Column('id', sa.Integer(), nullable=True),
    sa.Column('nombre', sa.Text(), nullable=False),
    sa.Column('fecha_nacimiento', sa.Text(), nullable=True),
    sa.Column('telefono', sa.Text(), nullable=True),
    sa.Column('correo', sa.Text(), nullable=True),
    sa.Column('direccion', sa.Text(), nullable=True),
    sa.Column('especialidad', sa.Text(), nullable=True),
    sa.Column('fecha_ingreso', sa.Text(), nullable=True),
    sa.Column('contacto_emergencia', sa.Text(), nullable=True),
    sa.Column('foto_ruta', sa.Text(), nullable=True),
    sa.Column('activo', sa.Integer(), server_default=sa.text('1'), nullable=False),
    sa.Column('creado_en', sa.Text(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('actualizado_en', sa.Text(), nullable=True),
    sa.CheckConstraint("fecha_nacimiento IS NULL OR fecha_nacimiento GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'", name='ck_maestros_fecha_nacimiento'),
    sa.CheckConstraint('activo IN (0, 1)', name='ck_maestros_activo'),
    sa.PrimaryKeyConstraint('id'),
    sqlite_autoincrement=True
    )
    op.create_table('sucursales',
    sa.Column('id', sa.Integer(), nullable=True),
    sa.Column('nombre', sa.Text(), nullable=False),
    sa.Column('direccion', sa.Text(), nullable=True),
    sa.Column('telefono', sa.Text(), nullable=True),
    sa.Column('prefijo_folio', sa.Text(), nullable=False),
    sa.Column('activa', sa.Integer(), server_default=sa.text('1'), nullable=False),
    sa.Column('creada_en', sa.Text(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.CheckConstraint('activa IN (0, 1)', name='ck_sucursales_activa'),
    sa.CheckConstraint('length(trim(prefijo_folio)) BETWEEN 2 AND 8', name='ck_sucursales_prefijo_longitud'),
    sa.CheckConstraint('prefijo_folio = upper(prefijo_folio)', name='ck_sucursales_prefijo_mayusculas'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('nombre', name='uq_sucursales_nombre'),
    sa.UniqueConstraint('prefijo_folio', name='uq_sucursales_prefijo_folio'),
    sqlite_autoincrement=True
    )
    op.create_table('folio_contadores',
    sa.Column('sucursal_id', sa.Integer(), nullable=True),
    sa.Column('ultimo_consecutivo', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.CheckConstraint('ultimo_consecutivo >= 0', name='ck_folio_contadores_consecutivo'),
    sa.ForeignKeyConstraint(['sucursal_id'], ['sucursales.id'], onupdate='CASCADE', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('sucursal_id')
    )
    op.create_table('grupos',
    sa.Column('id', sa.Integer(), nullable=True),
    sa.Column('sucursal_id', sa.Integer(), nullable=False),
    sa.Column('nombre', sa.Text(), nullable=False),
    sa.Column('dias_semana', sa.Text(), nullable=False),
    sa.Column('hora_inicio', sa.Text(), nullable=False),
    sa.Column('hora_fin', sa.Text(), nullable=False),
    sa.Column('precio_centavos', sa.Integer(), nullable=False),
    sa.Column('activo', sa.Integer(), server_default=sa.text('1'), nullable=False),
    sa.Column('creado_en', sa.Text(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('actualizado_en', sa.Text(), nullable=True),
    sa.CheckConstraint("hora_fin GLOB '[0-9][0-9]:[0-9][0-9]'", name='ck_grupos_hora_fin'),
    sa.CheckConstraint("hora_inicio GLOB '[0-9][0-9]:[0-9][0-9]'", name='ck_grupos_hora_inicio'),
    sa.CheckConstraint('activo IN (0, 1)', name='ck_grupos_activo'),
    sa.CheckConstraint('hora_fin > hora_inicio', name='ck_grupos_horario'),
    sa.CheckConstraint('precio_centavos >= 0', name='ck_grupos_precio'),
    sa.ForeignKeyConstraint(['sucursal_id'], ['sucursales.id'], onupdate='CASCADE', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('sucursal_id', 'nombre', name='uq_grupos_sucursal_nombre'),
    sqlite_autoincrement=True
    )
    with op.batch_alter_table('grupos', schema=None) as batch_op:
        batch_op.create_index('idx_grupos_sucursal', ['sucursal_id'], unique=False)

    op.create_table('pagos',
    sa.Column('id', sa.Integer(), nullable=True),
    sa.Column('folio', sa.Text(), nullable=False),
    sa.Column('alumno_id', sa.Integer(), nullable=False),
    sa.Column('sucursal_id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.Text(), nullable=False),
    sa.Column('monto_centavos', sa.Integer(), nullable=False),
    sa.Column('metodo', sa.Text(), nullable=False),
    sa.Column('fecha', sa.Text(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('estado', sa.Text(), server_default=sa.text("'vigente'"), nullable=False),
    sa.Column('motivo_cancelacion', sa.Text(), nullable=True),
    sa.Column('cancelado_en', sa.Text(), nullable=True),
    sa.Column('creado_en', sa.Text(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.CheckConstraint("(estado = 'cancelado' AND cancelado_en IS NOT NULL) OR (estado = 'vigente')", name='ck_pagos_cancelacion'),
    sa.CheckConstraint("estado IN ('vigente', 'cancelado')", name='ck_pagos_estado'),
    sa.CheckConstraint("folio GLOB '[A-Z][A-Z0-9-]*-[0-9][0-9][0-9][0-9]'", name='ck_pagos_folio_formato'),
    sa.CheckConstraint("metodo IN ('efectivo', 'transferencia')", name='ck_pagos_metodo'),
    sa.CheckConstraint("tipo IN ('inscripcion', 'sesion')", name='ck_pagos_tipo'),
    sa.CheckConstraint('monto_centavos >= 0', name='ck_pagos_monto'),
    sa.ForeignKeyConstraint(['alumno_id'], ['alumnos.id'], onupdate='CASCADE', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['sucursal_id'], ['sucursales.id'], onupdate='CASCADE', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('folio', name='uq_pagos_folio'),
    sa.UniqueConstraint('id', 'alumno_id', name='uq_pagos_id_alumno'),
    sqlite_autoincrement=True
    )
    with op.batch_alter_table('pagos', schema=None) as batch_op:
        batch_op.create_index('idx_pagos_alumno_fecha', ['alumno_id', 'fecha'], unique=False)
        batch_op.create_index('idx_pagos_fecha_estado', ['fecha', 'estado'], unique=False)
        batch_op.create_index('idx_pagos_sucursal_fecha', ['sucursal_id', 'fecha'], unique=False)

    op.create_table('bloques_grupo',
    sa.Column('id', sa.Integer(), nullable=True),
    sa.Column('grupo_id', sa.Integer(), nullable=False),
    sa.Column('materia', sa.Text(), nullable=False),
    sa.Column('orden', sa.Integer(), nullable=False),
    sa.Column('duracion_minutos', sa.Integer(), nullable=False),
    sa.Column('maestro_id', sa.Integer(), nullable=False),
    sa.CheckConstraint("materia IN ('ingles', 'robotica')", name='ck_bloques_grupo_materia'),
    sa.CheckConstraint('duracion_minutos > 0', name='ck_bloques_grupo_duracion'),
    sa.CheckConstraint('orden > 0', name='ck_bloques_grupo_orden'),
    sa.ForeignKeyConstraint(['grupo_id'], ['grupos.id'], onupdate='CASCADE', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['maestro_id'], ['maestros.id'], onupdate='CASCADE', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('grupo_id', 'orden', name='uq_bloques_grupo_grupo_orden'),
    sqlite_autoincrement=True
    )
    with op.batch_alter_table('bloques_grupo', schema=None) as batch_op:
        batch_op.create_index('idx_bloques_grupo_grupo', ['grupo_id'], unique=False)
        batch_op.create_index('idx_bloques_grupo_maestro', ['maestro_id'], unique=False)

    op.create_table('grupo_alumnos',
    sa.Column('id', sa.Integer(), nullable=True),
    sa.Column('grupo_id', sa.Integer(), nullable=False),
    sa.Column('alumno_id', sa.Integer(), nullable=False),
    sa.Column('fecha_alta', sa.Text(), server_default=sa.text('(CURRENT_DATE)'), nullable=False),
    sa.Column('fecha_baja', sa.Text(), nullable=True),
    sa.Column('creado_en', sa.Text(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.CheckConstraint('fecha_baja IS NULL OR fecha_baja >= fecha_alta', name='ck_grupo_alumnos_fechas'),
    sa.ForeignKeyConstraint(['alumno_id'], ['alumnos.id'], onupdate='CASCADE', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['grupo_id'], ['grupos.id'], onupdate='CASCADE', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sqlite_autoincrement=True
    )
    with op.batch_alter_table('grupo_alumnos', schema=None) as batch_op:
        batch_op.create_index('idx_grupo_alumnos_alumno', ['alumno_id'], unique=False)
        batch_op.create_index('ux_grupo_alumnos_activo', ['grupo_id', 'alumno_id'], unique=True, sqlite_where=sa.text('fecha_baja IS NULL'))

    op.create_table('sesiones',
    sa.Column('id', sa.Integer(), nullable=True),
    sa.Column('grupo_id', sa.Integer(), nullable=False),
    sa.Column('fecha', sa.Text(), nullable=False),
    sa.Column('estado', sa.Text(), server_default=sa.text("'programada'"), nullable=False),
    sa.Column('es_extra', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('creada_en', sa.Text(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.CheckConstraint("estado IN ('programada', 'impartida', 'cancelada')", name='ck_sesiones_estado'),
    sa.CheckConstraint("fecha GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'", name='ck_sesiones_fecha'),
    sa.CheckConstraint('es_extra IN (0, 1)', name='ck_sesiones_es_extra'),
    sa.ForeignKeyConstraint(['grupo_id'], ['grupos.id'], onupdate='CASCADE', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('grupo_id', 'fecha', name='uq_sesiones_grupo_fecha'),
    sqlite_autoincrement=True
    )
    with op.batch_alter_table('sesiones', schema=None) as batch_op:
        batch_op.create_index('idx_sesiones_fecha_estado', ['fecha', 'estado'], unique=False)
        batch_op.create_index('idx_sesiones_grupo_fecha', ['grupo_id', 'fecha'], unique=False)

    op.create_table('asistencias',
    sa.Column('id', sa.Integer(), nullable=True),
    sa.Column('sesion_id', sa.Integer(), nullable=False),
    sa.Column('alumno_id', sa.Integer(), nullable=False),
    sa.Column('estado', sa.Text(), nullable=False),
    sa.Column('es_reposicion', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('repone_a_id', sa.Integer(), nullable=True),
    sa.Column('pago_id', sa.Integer(), nullable=True),
    sa.Column('precio_aplicado_centavos', sa.Integer(), nullable=True),
    sa.Column('registrada_en', sa.Text(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.CheckConstraint("(es_reposicion = 0) OR (estado = 'asistio')", name='ck_asistencias_reposicion_estado'),
    sa.CheckConstraint("estado IN ('asistio', 'falto')", name='ck_asistencias_estado'),
    sa.CheckConstraint('(es_reposicion = 0 AND repone_a_id IS NULL) OR (es_reposicion = 1 AND repone_a_id IS NOT NULL)', name='ck_asistencias_reposicion'),
    sa.CheckConstraint('es_reposicion IN (0, 1)', name='ck_asistencias_es_reposicion'),
    sa.CheckConstraint('precio_aplicado_centavos IS NULL OR precio_aplicado_centavos >= 0', name='ck_asistencias_precio'),
    sa.CheckConstraint('repone_a_id IS NULL OR repone_a_id <> id', name='ck_asistencias_repone_a'),
    sa.ForeignKeyConstraint(['alumno_id'], ['alumnos.id'], onupdate='CASCADE', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['pago_id', 'alumno_id'], ['pagos.id', 'pagos.alumno_id'], name='fk_asistencias_pago_alumno', onupdate='CASCADE', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['repone_a_id', 'alumno_id'], ['asistencias.id', 'asistencias.alumno_id'], name='fk_asistencias_repone_alumno', onupdate='CASCADE', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['sesion_id'], ['sesiones.id'], onupdate='CASCADE', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id', 'alumno_id', name='uq_asistencias_id_alumno'),
    sqlite_autoincrement=True
    )
    with op.batch_alter_table('asistencias', schema=None) as batch_op:
        batch_op.create_index('idx_asistencias_alumno', ['alumno_id'], unique=False)
        batch_op.create_index('idx_asistencias_pago', ['pago_id'], unique=False)
        batch_op.create_index('idx_asistencias_sesion', ['sesion_id'], unique=False)
        batch_op.create_index('ux_asistencias_reposicion', ['sesion_id', 'alumno_id', 'repone_a_id'], unique=True, sqlite_where=sa.text('es_reposicion = 1'))
        batch_op.create_index('ux_asistencias_sesion_alumno', ['sesion_id', 'alumno_id'], unique=True, sqlite_where=sa.text('es_reposicion = 0'))

    op.create_table('sesion_maestros',
    sa.Column('id', sa.Integer(), nullable=True),
    sa.Column('sesion_id', sa.Integer(), nullable=False),
    sa.Column('maestro_id', sa.Integer(), nullable=False),
    sa.Column('pagado', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('fecha_pago', sa.Text(), nullable=True),
    sa.CheckConstraint('pagado IN (0, 1)', name='ck_sesion_maestros_pagado'),
    sa.ForeignKeyConstraint(['maestro_id'], ['maestros.id'], onupdate='CASCADE', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['sesion_id'], ['sesiones.id'], onupdate='CASCADE', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('sesion_id', 'maestro_id', name='uq_sesion_maestros_sesion_maestro'),
    sqlite_autoincrement=True
    )
    with op.batch_alter_table('sesion_maestros', schema=None) as batch_op:
        batch_op.create_index('idx_sesion_maestros_maestro', ['maestro_id', 'pagado'], unique=False)

    op.execute(
        """
        CREATE TRIGGER trg_sucursal_folio_inicial AFTER INSERT ON sucursales
        BEGIN
            INSERT INTO folio_contadores (sucursal_id, ultimo_consecutivo)
            VALUES (NEW.id, 0);
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_pagos_folio_inmutable BEFORE UPDATE OF folio ON pagos
        BEGIN
            SELECT RAISE(ABORT, 'El folio de un pago no puede modificarse');
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_pagos_no_eliminar BEFORE DELETE ON pagos
        BEGIN
            SELECT RAISE(ABORT, 'Los pagos no se eliminan; se cancelan');
        END
        """
    )
    op.execute(
        """
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
          AND (a.pago_id IS NULL OR p.estado = 'cancelado')
        """
    )
    op.execute(
        """
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
          )
        """
    )
    op.execute(
        """
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
        GROUP BY date(p.fecha), p.sucursal_id, su.nombre
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP VIEW IF EXISTS v_recaudacion_diaria")
    op.execute("DROP VIEW IF EXISTS v_reposiciones_pendientes")
    op.execute("DROP VIEW IF EXISTS v_deudas")
    op.execute("DROP TRIGGER IF EXISTS trg_pagos_no_eliminar")
    op.execute("DROP TRIGGER IF EXISTS trg_pagos_folio_inmutable")
    op.execute("DROP TRIGGER IF EXISTS trg_sucursal_folio_inicial")

    with op.batch_alter_table('sesion_maestros', schema=None) as batch_op:
        batch_op.drop_index('idx_sesion_maestros_maestro')

    op.drop_table('sesion_maestros')
    with op.batch_alter_table('asistencias', schema=None) as batch_op:
        batch_op.drop_index('ux_asistencias_sesion_alumno', sqlite_where=sa.text('es_reposicion = 0'))
        batch_op.drop_index('ux_asistencias_reposicion', sqlite_where=sa.text('es_reposicion = 1'))
        batch_op.drop_index('idx_asistencias_sesion')
        batch_op.drop_index('idx_asistencias_pago')
        batch_op.drop_index('idx_asistencias_alumno')

    op.drop_table('asistencias')
    with op.batch_alter_table('sesiones', schema=None) as batch_op:
        batch_op.drop_index('idx_sesiones_grupo_fecha')
        batch_op.drop_index('idx_sesiones_fecha_estado')

    op.drop_table('sesiones')
    with op.batch_alter_table('grupo_alumnos', schema=None) as batch_op:
        batch_op.drop_index('ux_grupo_alumnos_activo', sqlite_where=sa.text('fecha_baja IS NULL'))
        batch_op.drop_index('idx_grupo_alumnos_alumno')

    op.drop_table('grupo_alumnos')
    with op.batch_alter_table('bloques_grupo', schema=None) as batch_op:
        batch_op.drop_index('idx_bloques_grupo_maestro')
        batch_op.drop_index('idx_bloques_grupo_grupo')

    op.drop_table('bloques_grupo')
    with op.batch_alter_table('pagos', schema=None) as batch_op:
        batch_op.drop_index('idx_pagos_sucursal_fecha')
        batch_op.drop_index('idx_pagos_fecha_estado')
        batch_op.drop_index('idx_pagos_alumno_fecha')

    op.drop_table('pagos')
    with op.batch_alter_table('grupos', schema=None) as batch_op:
        batch_op.drop_index('idx_grupos_sucursal')

    op.drop_table('grupos')
    op.drop_table('folio_contadores')
    op.drop_table('sucursales')
    op.drop_table('maestros')
    op.drop_table('configuracion')
    op.drop_table('alumnos')
