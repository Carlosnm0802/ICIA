from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.billing import Asistencia, FolioContador, Pago
    from app.models.staff import Maestro, SesionMaestro


class Sucursal(Base):
    __tablename__ = "sucursales"
    __table_args__ = (
        UniqueConstraint("nombre", name="uq_sucursales_nombre"),
        UniqueConstraint("prefijo_folio", name="uq_sucursales_prefijo_folio"),
        CheckConstraint(
            "activa IN (0, 1)",
            name="ck_sucursales_activa",
        ),
        CheckConstraint(
            "length(trim(prefijo_folio)) BETWEEN 2 AND 8",
            name="ck_sucursales_prefijo_longitud",
        ),
        CheckConstraint(
            "prefijo_folio = upper(prefijo_folio)",
            name="ck_sucursales_prefijo_mayusculas",
        ),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    direccion: Mapped[str | None] = mapped_column(Text)
    telefono: Mapped[str | None] = mapped_column(Text)
    prefijo_folio: Mapped[str] = mapped_column(Text, nullable=False)
    activa: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
    )
    creada_en: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    grupos: Mapped[list[Grupo]] = relationship("Grupo", back_populates="sucursal")
    pagos: Mapped[list[Pago]] = relationship("Pago", back_populates="sucursal")
    folio_contador: Mapped[FolioContador | None] = relationship(
        "FolioContador",
        back_populates="sucursal",
        uselist=False,
    )


class Alumno(Base):
    __tablename__ = "alumnos"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('activo', 'baja')",
            name="ck_alumnos_estado",
        ),
        CheckConstraint(
            "fecha_nacimiento IS NULL OR fecha_nacimiento GLOB "
            "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'",
            name="ck_alumnos_fecha_nacimiento",
        ),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    fecha_nacimiento: Mapped[str | None] = mapped_column(Text)
    tutor: Mapped[str | None] = mapped_column(Text)
    telefono_tutor: Mapped[str | None] = mapped_column(Text)
    escuela_procedencia: Mapped[str | None] = mapped_column(Text)
    alergias_notas: Mapped[str | None] = mapped_column(Text)
    personas_autorizadas: Mapped[str | None] = mapped_column(Text)
    foto_ruta: Mapped[str | None] = mapped_column(Text)
    fecha_inscripcion: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("CURRENT_DATE"),
    )
    estado: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'activo'"),
    )
    creado_en: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    actualizado_en: Mapped[str | None] = mapped_column(Text)

    grupos: Mapped[list[GrupoAlumno]] = relationship(
        "GrupoAlumno",
        back_populates="alumno",
    )
    pagos: Mapped[list[Pago]] = relationship("Pago", back_populates="alumno")
    asistencias: Mapped[list[Asistencia]] = relationship(
        "Asistencia",
        back_populates="alumno",
        foreign_keys="Asistencia.alumno_id",
    )


class Grupo(Base):
    __tablename__ = "grupos"
    __table_args__ = (
        UniqueConstraint(
            "sucursal_id",
            "nombre",
            name="uq_grupos_sucursal_nombre",
        ),
        CheckConstraint(
            "precio_centavos >= 0",
            name="ck_grupos_precio",
        ),
        CheckConstraint(
            "activo IN (0, 1)",
            name="ck_grupos_activo",
        ),
        CheckConstraint(
            "hora_inicio GLOB '[0-9][0-9]:[0-9][0-9]'",
            name="ck_grupos_hora_inicio",
        ),
        CheckConstraint(
            "hora_fin GLOB '[0-9][0-9]:[0-9][0-9]'",
            name="ck_grupos_hora_fin",
        ),
        CheckConstraint(
            "hora_fin > hora_inicio",
            name="ck_grupos_horario",
        ),
        Index("idx_grupos_sucursal", "sucursal_id"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sucursal_id: Mapped[int] = mapped_column(
        ForeignKey(
            "sucursales.id",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    dias_semana: Mapped[str] = mapped_column(Text, nullable=False)
    hora_inicio: Mapped[str] = mapped_column(Text, nullable=False)
    hora_fin: Mapped[str] = mapped_column(Text, nullable=False)
    precio_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    activo: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
    )
    creado_en: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    actualizado_en: Mapped[str | None] = mapped_column(Text)

    sucursal: Mapped[Sucursal] = relationship("Sucursal", back_populates="grupos")
    bloques: Mapped[list[BloqueGrupo]] = relationship(
        "BloqueGrupo",
        back_populates="grupo",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    alumnos: Mapped[list[GrupoAlumno]] = relationship(
        "GrupoAlumno",
        back_populates="grupo",
    )
    sesiones: Mapped[list[Sesion]] = relationship("Sesion", back_populates="grupo")


class BloqueGrupo(Base):
    __tablename__ = "bloques_grupo"
    __table_args__ = (
        UniqueConstraint("grupo_id", "orden", name="uq_bloques_grupo_grupo_orden"),
        CheckConstraint(
            "materia IN ('ingles', 'robotica')",
            name="ck_bloques_grupo_materia",
        ),
        CheckConstraint("orden > 0", name="ck_bloques_grupo_orden"),
        CheckConstraint(
            "duracion_minutos > 0",
            name="ck_bloques_grupo_duracion",
        ),
        Index("idx_bloques_grupo_grupo", "grupo_id"),
        Index("idx_bloques_grupo_maestro", "maestro_id"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    grupo_id: Mapped[int] = mapped_column(
        ForeignKey(
            "grupos.id",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    materia: Mapped[str] = mapped_column(Text, nullable=False)
    orden: Mapped[int] = mapped_column(Integer, nullable=False)
    duracion_minutos: Mapped[int] = mapped_column(Integer, nullable=False)
    maestro_id: Mapped[int] = mapped_column(
        ForeignKey(
            "maestros.id",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    grupo: Mapped[Grupo] = relationship("Grupo", back_populates="bloques")
    maestro: Mapped[Maestro] = relationship("Maestro", back_populates="bloques")


class GrupoAlumno(Base):
    __tablename__ = "grupo_alumnos"
    __table_args__ = (
        CheckConstraint(
            "fecha_baja IS NULL OR fecha_baja >= fecha_alta",
            name="ck_grupo_alumnos_fechas",
        ),
        Index("idx_grupo_alumnos_alumno", "alumno_id"),
        Index(
            "ux_grupo_alumnos_activo",
            "grupo_id",
            "alumno_id",
            unique=True,
            sqlite_where=text("fecha_baja IS NULL"),
        ),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    grupo_id: Mapped[int] = mapped_column(
        ForeignKey(
            "grupos.id",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    alumno_id: Mapped[int] = mapped_column(
        ForeignKey(
            "alumnos.id",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    fecha_alta: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("CURRENT_DATE"),
    )
    fecha_baja: Mapped[str | None] = mapped_column(Text)
    creado_en: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    grupo: Mapped[Grupo] = relationship("Grupo", back_populates="alumnos")
    alumno: Mapped[Alumno] = relationship("Alumno", back_populates="grupos")


class Sesion(Base):
    __tablename__ = "sesiones"
    __table_args__ = (
        UniqueConstraint("grupo_id", "fecha", name="uq_sesiones_grupo_fecha"),
        CheckConstraint(
            "estado IN ('programada', 'impartida', 'cancelada')",
            name="ck_sesiones_estado",
        ),
        CheckConstraint("es_extra IN (0, 1)", name="ck_sesiones_es_extra"),
        CheckConstraint(
            "fecha GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'",
            name="ck_sesiones_fecha",
        ),
        Index("idx_sesiones_grupo_fecha", "grupo_id", "fecha"),
        Index("idx_sesiones_fecha_estado", "fecha", "estado"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    grupo_id: Mapped[int] = mapped_column(
        ForeignKey(
            "grupos.id",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    fecha: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'programada'"),
    )
    es_extra: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    creada_en: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    grupo: Mapped[Grupo] = relationship("Grupo", back_populates="sesiones")
    asistencias: Mapped[list[Asistencia]] = relationship(
        "Asistencia",
        back_populates="sesion",
    )
    maestros: Mapped[list[SesionMaestro]] = relationship(
        "SesionMaestro",
        back_populates="sesion",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
