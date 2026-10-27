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
    from app.models.academic import BloqueGrupo, Sesion


class Maestro(Base):
    __tablename__ = "maestros"
    __table_args__ = (
        CheckConstraint(
            "activo IN (0, 1)",
            name="ck_maestros_activo",
        ),
        CheckConstraint(
            "fecha_nacimiento IS NULL OR fecha_nacimiento GLOB "
            "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'",
            name="ck_maestros_fecha_nacimiento",
        ),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    fecha_nacimiento: Mapped[str | None] = mapped_column(Text)
    telefono: Mapped[str | None] = mapped_column(Text)
    correo: Mapped[str | None] = mapped_column(Text)
    direccion: Mapped[str | None] = mapped_column(Text)
    especialidad: Mapped[str | None] = mapped_column(Text)
    fecha_ingreso: Mapped[str | None] = mapped_column(Text)
    contacto_emergencia: Mapped[str | None] = mapped_column(Text)
    foto_ruta: Mapped[str | None] = mapped_column(Text)
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

    bloques: Mapped[list[BloqueGrupo]] = relationship(
        "BloqueGrupo",
        back_populates="maestro",
    )
    sesiones: Mapped[list[SesionMaestro]] = relationship(
        "SesionMaestro",
        back_populates="maestro",
    )


class SesionMaestro(Base):
    __tablename__ = "sesion_maestros"
    __table_args__ = (
        UniqueConstraint(
            "sesion_id",
            "maestro_id",
            name="uq_sesion_maestros_sesion_maestro",
        ),
        CheckConstraint("pagado IN (0, 1)", name="ck_sesion_maestros_pagado"),
        Index("idx_sesion_maestros_maestro", "maestro_id", "pagado"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sesion_id: Mapped[int] = mapped_column(
        ForeignKey(
            "sesiones.id",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    maestro_id: Mapped[int] = mapped_column(
        ForeignKey(
            "maestros.id",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    pagado: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    fecha_pago: Mapped[str | None] = mapped_column(Text)

    sesion: Mapped[Sesion] = relationship("Sesion", back_populates="maestros")
    maestro: Mapped[Maestro] = relationship("Maestro", back_populates="sesiones")
