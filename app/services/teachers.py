from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from unicodedata import normalize

from fastapi import UploadFile
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.models import (
    BloqueGrupo,
    Grupo,
    Maestro,
    Sesion,
    SesionMaestro,
    Sucursal,
)
from app.services import photos

MATERIAS = {
    "ingles": "Inglés",
    "robotica": "Robótica",
}


class TeacherError(Exception):
    pass


@dataclass(frozen=True)
class MaestroResumen:
    id: int
    nombre: str
    telefono: str | None
    correo: str | None
    especialidad: str | None
    activo: bool
    foto_ruta: str | None
    grupos_activos: int


@dataclass(frozen=True)
class GrupoMaestro:
    grupo_id: int
    nombre: str
    sucursal_nombre: str
    dias_semana: str
    hora_inicio: str
    hora_fin: str
    activo: bool
    bloques: tuple[str, ...]


@dataclass(frozen=True)
class MarcaSesion:
    marca_id: int
    sesion_id: int
    fecha: str
    grupo_nombre: str
    sucursal_nombre: str
    pagado: bool
    fecha_pago: str | None
    es_suplencia: bool
    titular_nombre: str | None
    estado_sesion: str


@dataclass(frozen=True)
class MaestroFicha:
    maestro: Maestro
    grupos: list[GrupoMaestro]
    sesiones: list[MarcaSesion]
    total_pagadas: int
    total_pendientes: int


@dataclass(frozen=True)
class DatosMaestro:
    nombre: str
    fecha_nacimiento: str | None
    telefono: str | None
    correo: str | None
    direccion: str | None
    especialidad: str | None
    fecha_ingreso: str | None
    contacto_emergencia: str | None


def _limpiar(valor: str | None) -> str:
    return " ".join((valor or "").split())


def _opcional(valor: str | None) -> str | None:
    limpio = _limpiar(valor)
    return limpio or None


def _exigir(valor: str | None, campo: str) -> str:
    limpio = _limpiar(valor)
    if not limpio:
        raise TeacherError(f"{campo} es obligatorio.")
    return limpio


def _fecha(
    valor: str | None,
    campo: str,
    *,
    no_futura: bool = False,
) -> str | None:
    limpio = _limpiar(valor)
    if not limpio:
        return None
    try:
        fecha = date.fromisoformat(limpio)
    except ValueError as exc:
        raise TeacherError(f"{campo} debe tener formato AAAA-MM-DD.") from exc
    if no_futura and fecha > date.today():
        raise TeacherError(f"{campo} no puede estar en el futuro.")
    return fecha.isoformat()


def _clave_orden(nombre: str) -> str:
    sin_acentos = normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    return sin_acentos.casefold()


def _datos_maestro(
    *,
    nombre: str,
    fecha_nacimiento: str | None,
    telefono: str | None,
    correo: str | None,
    direccion: str | None,
    especialidad: str | None,
    fecha_ingreso: str | None,
    contacto_emergencia: str | None,
) -> DatosMaestro:
    correo_limpio = _opcional(correo)
    if correo_limpio and (
        "@" not in correo_limpio
        or correo_limpio.startswith("@")
        or correo_limpio.endswith("@")
    ):
        raise TeacherError("El correo no tiene un formato válido.")
    return DatosMaestro(
        nombre=_exigir(nombre, "El nombre"),
        fecha_nacimiento=_fecha(
            fecha_nacimiento,
            "La fecha de nacimiento",
            no_futura=True,
        ),
        telefono=_opcional(telefono),
        correo=correo_limpio,
        direccion=_opcional(direccion),
        especialidad=_opcional(especialidad),
        fecha_ingreso=_fecha(
            fecha_ingreso,
            "La fecha de ingreso",
            no_futura=True,
        ),
        contacto_emergencia=_opcional(contacto_emergencia),
    )


def listar_maestros(
    db: Session,
    *,
    q: str | None = None,
    estado: str = "activo",
) -> list[MaestroResumen]:
    if estado not in {"activo", "inactivo", "todos"}:
        raise TeacherError("El estado solicitado no es válido.")

    grupos_activos = (
        select(func.count(func.distinct(BloqueGrupo.grupo_id)))
        .join(Grupo, Grupo.id == BloqueGrupo.grupo_id)
        .where(
            BloqueGrupo.maestro_id == Maestro.id,
            Grupo.activo == 1,
        )
        .correlate(Maestro)
        .scalar_subquery()
    )
    consulta = select(Maestro, grupos_activos.label("grupos_activos"))
    if estado == "activo":
        consulta = consulta.where(Maestro.activo == 1)
    elif estado == "inactivo":
        consulta = consulta.where(Maestro.activo == 0)

    filas = db.execute(consulta).all()
    busqueda = _clave_orden(_limpiar(q))
    maestros: list[MaestroResumen] = []
    for maestro, total in filas:
        if busqueda:
            texto = _clave_orden(
                " ".join(
                    valor
                    for valor in (
                        maestro.nombre,
                        maestro.especialidad or "",
                        maestro.correo or "",
                        maestro.telefono or "",
                    )
                    if valor
                )
            )
            if busqueda not in texto:
                continue
        maestros.append(
            MaestroResumen(
                id=maestro.id,
                nombre=maestro.nombre,
                telefono=maestro.telefono,
                correo=maestro.correo,
                especialidad=maestro.especialidad,
                activo=bool(maestro.activo),
                foto_ruta=maestro.foto_ruta,
                grupos_activos=int(total or 0),
            )
        )
    return sorted(maestros, key=lambda item: _clave_orden(item.nombre))


def obtener_maestro(db: Session, maestro_id: int) -> Maestro | None:
    return db.scalar(select(Maestro).where(Maestro.id == maestro_id))


def obtener_ficha(db: Session, maestro_id: int) -> MaestroFicha | None:
    maestro = obtener_maestro(db, maestro_id)
    if maestro is None:
        return None

    filas_grupos = db.execute(
        select(Grupo, Sucursal, BloqueGrupo)
        .join(BloqueGrupo, BloqueGrupo.grupo_id == Grupo.id)
        .join(Sucursal, Sucursal.id == Grupo.sucursal_id)
        .where(BloqueGrupo.maestro_id == maestro.id)
        .order_by(
            Grupo.activo.desc(),
            Sucursal.nombre,
            Grupo.nombre,
            BloqueGrupo.orden,
        )
    ).all()
    agrupados: dict[int, dict] = {}
    for grupo, sucursal, bloque in filas_grupos:
        if grupo.id not in agrupados:
            agrupados[grupo.id] = {
                "grupo": grupo,
                "sucursal": sucursal,
                "bloques": [],
            }
        agrupados[grupo.id]["bloques"].append(
            f"{MATERIAS[bloque.materia]} · {bloque.duracion_minutos} min"
        )
    grupos = [
        GrupoMaestro(
            grupo_id=datos["grupo"].id,
            nombre=datos["grupo"].nombre,
            sucursal_nombre=datos["sucursal"].nombre,
            dias_semana=datos["grupo"].dias_semana,
            hora_inicio=datos["grupo"].hora_inicio,
            hora_fin=datos["grupo"].hora_fin,
            activo=bool(datos["grupo"].activo),
            bloques=tuple(datos["bloques"]),
        )
        for datos in agrupados.values()
    ]

    titular = aliased(Maestro)
    filas_sesiones = db.execute(
        select(
            SesionMaestro,
            Sesion,
            Grupo,
            Sucursal,
            titular.nombre,
        )
        .join(Sesion, Sesion.id == SesionMaestro.sesion_id)
        .join(Grupo, Grupo.id == Sesion.grupo_id)
        .join(Sucursal, Sucursal.id == Grupo.sucursal_id)
        .outerjoin(
            titular,
            titular.id == SesionMaestro.maestro_titular_id,
        )
        .where(SesionMaestro.maestro_id == maestro.id)
        .order_by(Sesion.fecha.desc(), Sesion.id.desc())
        .limit(50)
    ).all()
    sesiones = [
        MarcaSesion(
            marca_id=marca.id,
            sesion_id=sesion.id,
            fecha=sesion.fecha,
            grupo_nombre=grupo.nombre,
            sucursal_nombre=sucursal_nombre,
            pagado=bool(marca.pagado),
            fecha_pago=marca.fecha_pago,
            es_suplencia=marca.maestro_titular_id is not None,
            titular_nombre=titular_nombre,
            estado_sesion=sesion.estado,
        )
        for marca, sesion, grupo, sucursal_nombre, titular_nombre in filas_sesiones
    ]

    conteos = dict(
        db.execute(
            select(SesionMaestro.pagado, func.count(SesionMaestro.id))
            .where(SesionMaestro.maestro_id == maestro.id)
            .group_by(SesionMaestro.pagado)
        ).all()
    )
    return MaestroFicha(
        maestro=maestro,
        grupos=grupos,
        sesiones=sesiones,
        total_pagadas=int(conteos.get(1, 0)),
        total_pendientes=int(conteos.get(0, 0)),
    )


def crear_maestro(
    db: Session,
    *,
    nombre: str,
    fecha_nacimiento: str | None = None,
    telefono: str | None = None,
    correo: str | None = None,
    direccion: str | None = None,
    especialidad: str | None = None,
    fecha_ingreso: str | None = None,
    contacto_emergencia: str | None = None,
    foto: UploadFile | None = None,
) -> Maestro:
    datos = _datos_maestro(
        nombre=nombre,
        fecha_nacimiento=fecha_nacimiento,
        telefono=telefono,
        correo=correo,
        direccion=direccion,
        especialidad=especialidad,
        fecha_ingreso=fecha_ingreso,
        contacto_emergencia=contacto_emergencia,
    )
    ruta_foto = photos.guardar_foto(foto, "maestros")
    maestro = Maestro(
        nombre=datos.nombre,
        fecha_nacimiento=datos.fecha_nacimiento,
        telefono=datos.telefono,
        correo=datos.correo,
        direccion=datos.direccion,
        especialidad=datos.especialidad,
        fecha_ingreso=datos.fecha_ingreso,
        contacto_emergencia=datos.contacto_emergencia,
        foto_ruta=ruta_foto,
        activo=1,
    )
    db.add(maestro)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        photos.borrar_foto(ruta_foto)
        raise TeacherError(
            "No se pudo crear el maestro: datos inválidos."
        ) from exc
    except Exception:
        db.rollback()
        photos.borrar_foto(ruta_foto)
        raise
    db.refresh(maestro)
    return maestro


def actualizar_maestro(
    db: Session,
    maestro_id: int,
    *,
    nombre: str,
    fecha_nacimiento: str | None = None,
    telefono: str | None = None,
    correo: str | None = None,
    direccion: str | None = None,
    especialidad: str | None = None,
    fecha_ingreso: str | None = None,
    contacto_emergencia: str | None = None,
    foto: UploadFile | None = None,
    quitar_foto: bool = False,
) -> Maestro:
    maestro = obtener_maestro(db, maestro_id)
    if maestro is None:
        raise TeacherError("El maestro no existe.")

    datos = _datos_maestro(
        nombre=nombre,
        fecha_nacimiento=fecha_nacimiento,
        telefono=telefono,
        correo=correo,
        direccion=direccion,
        especialidad=especialidad,
        fecha_ingreso=fecha_ingreso,
        contacto_emergencia=contacto_emergencia,
    )
    ruta_anterior = maestro.foto_ruta
    ruta_nueva = photos.guardar_foto(foto, "maestros")

    maestro.nombre = datos.nombre
    maestro.fecha_nacimiento = datos.fecha_nacimiento
    maestro.telefono = datos.telefono
    maestro.correo = datos.correo
    maestro.direccion = datos.direccion
    maestro.especialidad = datos.especialidad
    maestro.fecha_ingreso = datos.fecha_ingreso
    maestro.contacto_emergencia = datos.contacto_emergencia
    if ruta_nueva is not None:
        maestro.foto_ruta = ruta_nueva
    elif quitar_foto:
        maestro.foto_ruta = None
    maestro.actualizado_en = text("CURRENT_TIMESTAMP")

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        photos.borrar_foto(ruta_nueva)
        raise TeacherError(
            "No se pudo actualizar el maestro: datos inválidos."
        ) from exc
    except Exception:
        db.rollback()
        photos.borrar_foto(ruta_nueva)
        raise
    if ruta_anterior and ruta_anterior != maestro.foto_ruta:
        photos.borrar_foto(ruta_anterior)
    db.refresh(maestro)
    return maestro


def cambiar_estado_maestro(
    db: Session,
    maestro_id: int,
    activo: bool,
) -> Maestro:
    maestro = obtener_maestro(db, maestro_id)
    if maestro is None:
        raise TeacherError("El maestro no existe.")
    if bool(maestro.activo) == activo:
        return maestro

    if not activo:
        grupos_activos = db.scalar(
            select(func.count(func.distinct(BloqueGrupo.grupo_id)))
            .join(Grupo, Grupo.id == BloqueGrupo.grupo_id)
            .where(
                BloqueGrupo.maestro_id == maestro.id,
                Grupo.activo == 1,
            )
        )
        if grupos_activos:
            raise TeacherError(
                "No se puede dar de baja: el maestro tiene grupos activos. "
                "Reasigna sus bloques primero."
            )

    maestro.activo = 1 if activo else 0
    maestro.actualizado_en = text("CURRENT_TIMESTAMP")
    db.commit()
    db.refresh(maestro)
    return maestro
