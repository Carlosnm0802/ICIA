from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.academic import Alumno, Sesion, Sucursal


class FolioContador(Base):
    __tablename__ = "folio_contadores"
    __table_args__ = (
        CheckConstraint(
            "ultimo_consecutivo >= 0",
            name="ck_folio_contadores_consecutivo",
        ),
    )

    sucursal_id: Mapped[int] = mapped_column(
        ForeignKey(
            "sucursales.id",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )
    ultimo_consecutivo: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    sucursal: Mapped[Sucursal] = relationship(
        "Sucursal",
        back_populates="folio_contador",
    )


class Pago(Base):
    __tablename__ = "pagos"
    __table_args__ = (
        UniqueConstraint("folio", name="uq_pagos_folio"),
        UniqueConstraint("id", "alumno_id", name="uq_pagos_id_alumno"),
        CheckConstraint(
            "tipo IN ('inscripcion', 'sesion')",
            name="ck_pagos_tipo",
        ),
        CheckConstraint(
            "monto_centavos >= 0",
            name="ck_pagos_monto",
        ),
        CheckConstraint(
            "metodo IN ('efectivo', 'transferencia')",
            name="ck_pagos_metodo",
        ),
        CheckConstraint(
            "estado IN ('vigente', 'cancelado')",
            name="ck_pagos_estado",
        ),
        CheckConstraint(
            "folio GLOB '[A-Z][A-Z0-9-]*-[0-9][0-9][0-9][0-9]'",
            name="ck_pagos_folio_formato",
        ),
        CheckConstraint(
            "(estado = 'cancelado' AND cancelado_en IS NOT NULL) "
            "OR (estado = 'vigente')",
            name="ck_pagos_cancelacion",
        ),
        Index("idx_pagos_alumno_fecha", "alumno_id", "fecha"),
        Index("idx_pagos_sucursal_fecha", "sucursal_id", "fecha"),
        Index("idx_pagos_fecha_estado", "fecha", "estado"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    folio: Mapped[str] = mapped_column(Text, nullable=False)
    alumno_id: Mapped[int] = mapped_column(
        ForeignKey(
            "alumnos.id",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    sucursal_id: Mapped[int] = mapped_column(
        ForeignKey(
            "sucursales.id",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    monto_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    metodo: Mapped[str] = mapped_column(Text, nullable=False)
    fecha: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    estado: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'vigente'"),
    )
    motivo_cancelacion: Mapped[str | None] = mapped_column(Text)
    cancelado_en: Mapped[str | None] = mapped_column(Text)
    creado_en: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    alumno: Mapped[Alumno] = relationship("Alumno", back_populates="pagos")
    sucursal: Mapped[Sucursal] = relationship("Sucursal", back_populates="pagos")


class Asistencia(Base):
    __tablename__ = "asistencias"
    __table_args__ = (
        UniqueConstraint("id", "alumno_id", name="uq_asistencias_id_alumno"),
        ForeignKeyConstraint(
            ["pago_id", "alumno_id"],
            ["pagos.id", "pagos.alumno_id"],
            name="fk_asistencias_pago_alumno",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["repone_a_id", "alumno_id"],
            ["asistencias.id", "asistencias.alumno_id"],
            name="fk_asistencias_repone_alumno",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "estado IN ('asistio', 'falto')",
            name="ck_asistencias_estado",
        ),
        CheckConstraint(
            "es_reposicion IN (0, 1)",
            name="ck_asistencias_es_reposicion",
        ),
        CheckConstraint(
            "precio_aplicado_centavos IS NULL "
            "OR precio_aplicado_centavos >= 0",
            name="ck_asistencias_precio",
        ),
        CheckConstraint(
            "(es_reposicion = 0 AND repone_a_id IS NULL) "
            "OR (es_reposicion = 1 AND repone_a_id IS NOT NULL)",
            name="ck_asistencias_reposicion",
        ),
        CheckConstraint(
            "(es_reposicion = 0) OR (estado = 'asistio')",
            name="ck_asistencias_reposicion_estado",
        ),
        CheckConstraint(
            "repone_a_id IS NULL OR repone_a_id <> id",
            name="ck_asistencias_repone_a",
        ),
        Index("idx_asistencias_sesion", "sesion_id"),
        Index("idx_asistencias_alumno", "alumno_id"),
        Index("idx_asistencias_pago", "pago_id"),
        Index(
            "ux_asistencias_sesion_alumno",
            "sesion_id",
            "alumno_id",
            unique=True,
            sqlite_where=text("es_reposicion = 0"),
        ),
        Index(
            "ux_asistencias_reposicion",
            "sesion_id",
            "alumno_id",
            "repone_a_id",
            unique=True,
            sqlite_where=text("es_reposicion = 1"),
        ),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sesion_id: Mapped[int] = mapped_column(
        ForeignKey(
            "sesiones.id",
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
    estado: Mapped[str] = mapped_column(Text, nullable=False)
    es_reposicion: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    repone_a_id: Mapped[int | None] = mapped_column(Integer)
    pago_id: Mapped[int | None] = mapped_column(Integer)
    precio_aplicado_centavos: Mapped[int | None] = mapped_column(Integer)
    registrada_en: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    sesion: Mapped[Sesion] = relationship("Sesion", back_populates="asistencias")
    alumno: Mapped[Alumno] = relationship(
        "Alumno",
        back_populates="asistencias",
        foreign_keys=[alumno_id],
    )
