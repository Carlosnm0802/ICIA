from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import BloqueGrupo, Grupo, Maestro, Pago, Sucursal

DIAS_SEMANA = (
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sábado",
    "Domingo",
)
MATERIAS = {
    "ingles": "Inglés",
    "robotica": "Robótica",
}
_RE_PREFIJO = re.compile(r"^[A-Z0-9]{2,8}$")


class CatalogError(Exception):
    pass


@dataclass(frozen=True)
class SucursalResumen:
    id: int
    nombre: str
    prefijo_folio: str
    direccion: str | None
    telefono: str | None
    activa: bool
    grupos_activos: int


@dataclass(frozen=True)
class BloqueForm:
    materia: str
    orden: int
    duracion_minutos: int
    maestro_id: int


@dataclass(frozen=True)
class GrupoResumen:
    id: int
    sucursal_id: int
    sucursal: str
    nombre: str
    dias_semana: str
    hora_inicio: str
    hora_fin: str
    precio_centavos: int
    activo: bool
    bloques: tuple[str, ...]


@dataclass(frozen=True)
class GrupoEdicion:
    grupo: Grupo
    bloques: list[BloqueGrupo]


def _limpiar(valor: str | None) -> str:
    return " ".join((valor or "").split())


def _opcional(valor: str | None) -> str | None:
    limpio = _limpiar(valor)
    return limpio or None


def _exigir(valor: str | None, campo: str) -> str:
    limpio = _limpiar(valor)
    if not limpio:
        raise CatalogError(f"{campo} es obligatorio.")
    return limpio


def _normalizar_prefijo(valor: str | None) -> str:
    limpio = _limpiar(valor).upper()
    if not _RE_PREFIJO.fullmatch(limpio):
        raise CatalogError(
            "El prefijo debe tener 2 a 8 caracteres: letras y números."
        )
    return limpio


def normalizar_dias(valores: list[str]) -> str:
    seleccionados = {normalizar_dia(valor) for valor in valores}
    if not seleccionados:
        raise CatalogError("Selecciona al menos un día de la semana.")
    ordenados = [dia for dia in DIAS_SEMANA if dia in seleccionados]
    return ",".join(ordenados)


def normalizar_dia(valor: str) -> str:
    limpio = _limpiar(valor)
    if limpio not in DIAS_SEMANA:
        raise CatalogError(f"Día no válido: {limpio}")
    return limpio


def _parse_hora(valor: str | None, campo: str) -> time:
    limpio = _exigir(valor, campo)
    try:
        hora = time.fromisoformat(limpio)
    except ValueError as exc:
        raise CatalogError(f"{campo} debe tener formato HH:MM.") from exc
    if hora.second or hora.microsecond:
        raise CatalogError(f"{campo} debe tener formato HH:MM.")
    return hora


def _minutos(hora: time) -> int:
    return hora.hour * 60 + hora.minute


def parse_precio(valor: str | None) -> int:
    limpio = _limpiar(valor).replace("$", "").replace(",", "")
    if not limpio:
        raise CatalogError("El precio por sesión es obligatorio.")
    try:
        monto = Decimal(limpio)
    except InvalidOperation as exc:
        raise CatalogError("El precio debe ser un número válido.") from exc
    if not monto.is_finite() or monto < 0:
        raise CatalogError("El precio no puede ser negativo.")
    centavos = int(
        (monto * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    if centavos > 100_000_000:
        raise CatalogError("El precio es demasiado alto.")
    return centavos


def sucursal_tiene_pagos(db: Session, sucursal_id: int) -> bool:
    return (
        db.scalar(
            select(Pago.id).where(Pago.sucursal_id == sucursal_id).limit(1)
        )
        is not None
    )


def listar_sucursales_admin(db: Session) -> list[SucursalResumen]:
    grupos_activos = (
        select(func.count(Grupo.id))
        .where(Grupo.sucursal_id == Sucursal.id, Grupo.activo == 1)
        .correlate(Sucursal)
        .scalar_subquery()
    )
    filas = db.execute(
        select(Sucursal, grupos_activos.label("grupos_activos")).order_by(
            Sucursal.nombre
        )
    ).all()
    return [
        SucursalResumen(
            id=sucursal.id,
            nombre=sucursal.nombre,
            prefijo_folio=sucursal.prefijo_folio,
            direccion=sucursal.direccion,
            telefono=sucursal.telefono,
            activa=bool(sucursal.activa),
            grupos_activos=int(total or 0),
        )
        for sucursal, total in filas
    ]


def obtener_sucursal(db: Session, sucursal_id: int) -> Sucursal | None:
    return db.scalar(select(Sucursal).where(Sucursal.id == sucursal_id))


def _validar_nombre_sucursal(
    db: Session,
    nombre: str,
    excluir_id: int | None,
) -> None:
    consulta = select(Sucursal.id).where(func.lower(Sucursal.nombre) == nombre.lower())
    if excluir_id is not None:
        consulta = consulta.where(Sucursal.id != excluir_id)
    if db.scalar(consulta) is not None:
        raise CatalogError("Ya existe una sucursal con ese nombre.")


def _validar_prefijo(
    db: Session,
    prefijo: str,
    excluir_id: int | None,
) -> None:
    consulta = select(Sucursal.id).where(Sucursal.prefijo_folio == prefijo)
    if excluir_id is not None:
        consulta = consulta.where(Sucursal.id != excluir_id)
    if db.scalar(consulta) is not None:
        raise CatalogError("Ese prefijo de folio ya está en uso.")


def crear_sucursal(
    db: Session,
    nombre: str,
    prefijo: str,
    direccion: str | None = None,
    telefono: str | None = None,
) -> Sucursal:
    nombre_limpio = _exigir(nombre, "El nombre")
    prefijo_limpio = _normalizar_prefijo(prefijo)
    _validar_nombre_sucursal(db, nombre_limpio, None)
    _validar_prefijo(db, prefijo_limpio, None)

    sucursal = Sucursal(
        nombre=nombre_limpio,
        prefijo_folio=prefijo_limpio,
        direccion=_opcional(direccion),
        telefono=_opcional(telefono),
    )
    db.add(sucursal)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise CatalogError(
            "No se pudo crear la sucursal: nombre o prefijo duplicado."
        ) from exc
    db.refresh(sucursal)
    return sucursal


def actualizar_sucursal(
    db: Session,
    sucursal_id: int,
    nombre: str,
    prefijo: str,
    direccion: str | None = None,
    telefono: str | None = None,
) -> Sucursal:
    sucursal = obtener_sucursal(db, sucursal_id)
    if sucursal is None:
        raise CatalogError("La sucursal no existe.")

    nombre_limpio = _exigir(nombre, "El nombre")
    _validar_nombre_sucursal(db, nombre_limpio, sucursal.id)

    prefijo_limpio = _normalizar_prefijo(prefijo)
    if prefijo_limpio != sucursal.prefijo_folio:
        if sucursal_tiene_pagos(db, sucursal.id):
            raise CatalogError(
                "El prefijo no se puede cambiar porque la sucursal ya "
                "emitió folios."
            )
        _validar_prefijo(db, prefijo_limpio, sucursal.id)
        sucursal.prefijo_folio = prefijo_limpio

    sucursal.nombre = nombre_limpio
    sucursal.direccion = _opcional(direccion)
    sucursal.telefono = _opcional(telefono)
    sucursal.actualizado_en = text("CURRENT_TIMESTAMP")

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise CatalogError(
            "No se pudo actualizar la sucursal: nombre o prefijo duplicado."
        ) from exc
    db.refresh(sucursal)
    return sucursal


def cambiar_estado_sucursal(
    db: Session,
    sucursal_id: int,
    activa: bool,
) -> Sucursal:
    sucursal = obtener_sucursal(db, sucursal_id)
    if sucursal is None:
        raise CatalogError("La sucursal no existe.")
    if not activa:
        grupos_activos = db.scalar(
            select(func.count(Grupo.id)).where(
                Grupo.sucursal_id == sucursal.id,
                Grupo.activo == 1,
            )
        )
        if grupos_activos:
            raise CatalogError(
                "No se puede desactivar: la sucursal tiene grupos activos. "
                "Desactívalos primero."
            )
    sucursal.activa = 1 if activa else 0
    sucursal.actualizado_en = text("CURRENT_TIMESTAMP")
    db.commit()
    db.refresh(sucursal)
    return sucursal


def listar_maestros_activos(db: Session) -> list[Maestro]:
    return list(
        db.scalars(
            select(Maestro).where(Maestro.activo == 1).order_by(Maestro.nombre)
        )
    )


def _describir_bloques(db: Session, grupo: Grupo) -> tuple[str, ...]:
    filas = db.execute(
        select(BloqueGrupo, Maestro.nombre)
        .join(Maestro, Maestro.id == BloqueGrupo.maestro_id)
        .where(BloqueGrupo.grupo_id == grupo.id)
        .order_by(BloqueGrupo.orden)
    ).all()
    return tuple(
        f"{MATERIAS[bloque.materia]} · {bloque.duracion_minutos} min · {maestro}"
        for bloque, maestro in filas
    )


def listar_grupos_admin(
    db: Session,
    sucursal_id: int | None = None,
    incluir_inactivos: bool = False,
) -> list[GrupoResumen]:
    consulta = (
        select(Grupo, Sucursal.nombre)
        .join(Sucursal, Sucursal.id == Grupo.sucursal_id)
        .order_by(Sucursal.nombre, Grupo.hora_inicio, Grupo.nombre)
    )
    if sucursal_id is not None:
        consulta = consulta.where(Grupo.sucursal_id == sucursal_id)
    if not incluir_inactivos:
        consulta = consulta.where(Grupo.activo == 1)

    resumenes: list[GrupoResumen] = []
    for grupo, sucursal_nombre in db.execute(consulta).all():
        resumenes.append(
            GrupoResumen(
                id=grupo.id,
                sucursal_id=grupo.sucursal_id,
                sucursal=sucursal_nombre,
                nombre=grupo.nombre,
                dias_semana=grupo.dias_semana,
                hora_inicio=grupo.hora_inicio,
                hora_fin=grupo.hora_fin,
                precio_centavos=grupo.precio_centavos,
                activo=bool(grupo.activo),
                bloques=_describir_bloques(db, grupo),
            )
        )
    return resumenes


def obtener_grupo_detalle(
    db: Session,
    grupo_id: int,
) -> GrupoEdicion | None:
    grupo = db.scalar(select(Grupo).where(Grupo.id == grupo_id))
    if grupo is None:
        return None
    bloques = list(
        db.scalars(
            select(BloqueGrupo)
            .where(BloqueGrupo.grupo_id == grupo.id)
            .order_by(BloqueGrupo.orden)
        )
    )
    return GrupoEdicion(grupo=grupo, bloques=bloques)


def _validar_nombre_grupo(
    db: Session,
    sucursal_id: int,
    nombre: str,
    excluir_id: int | None,
) -> None:
    consulta = select(Grupo.id).where(
        Grupo.sucursal_id == sucursal_id,
        func.lower(Grupo.nombre) == nombre.lower(),
    )
    if excluir_id is not None:
        consulta = consulta.where(Grupo.id != excluir_id)
    if db.scalar(consulta) is not None:
        raise CatalogError(
            "Ya existe un grupo con ese nombre en la sucursal."
        )


def _validar_bloques(
    db: Session,
    bloques: list[BloqueForm],
    duracion_total: int,
) -> None:
    if not bloques:
        raise CatalogError("El grupo necesita al menos un bloque.")
    if len(bloques) > 10:
        raise CatalogError("El grupo tiene demasiados bloques.")

    maestros_activos = set(
        db.scalars(select(Maestro.id).where(Maestro.activo == 1))
    )
    suma = 0
    for esperado, bloque in enumerate(bloques, start=1):
        if bloque.orden != esperado:
            raise CatalogError(
                "El orden de los bloques debe ser consecutivo desde 1."
            )
        if bloque.materia not in MATERIAS:
            raise CatalogError("La materia del bloque no es válida.")
        if bloque.duracion_minutos <= 0:
            raise CatalogError(
                "La duración de cada bloque debe ser mayor a cero."
            )
        if bloque.maestro_id not in maestros_activos:
            raise CatalogError(
                "Cada bloque necesita un maestro activo existente."
            )
        suma += bloque.duracion_minutos

    if suma != duracion_total:
        raise CatalogError(
            f"La duración de los bloques suma {suma} min y debe ser igual "
            f"al horario del grupo ({duracion_total} min)."
        )


def _crear_bloques(db: Session, grupo_id: int, bloques: list[BloqueForm]) -> None:
    for bloque in bloques:
        db.add(
            BloqueGrupo(
                grupo_id=grupo_id,
                materia=bloque.materia,
                orden=bloque.orden,
                duracion_minutos=bloque.duracion_minutos,
                maestro_id=bloque.maestro_id,
            )
        )


def _datos_grupo(
    db: Session,
    sucursal_id: int,
    nombre: str,
    dias_semana: list[str],
    hora_inicio: str,
    hora_fin: str,
    precio: str,
    bloques: list[BloqueForm],
    excluir_id: int | None,
) -> tuple[str, str, str, str, int]:
    sucursal = db.scalar(
        select(Sucursal).where(
            Sucursal.id == sucursal_id,
            Sucursal.activa == 1,
        )
    )
    if sucursal is None:
        raise CatalogError("Selecciona una sucursal activa.")

    nombre_limpio = _exigir(nombre, "El nombre")
    _validar_nombre_grupo(db, sucursal_id, nombre_limpio, excluir_id)

    dias = normalizar_dias(dias_semana)
    inicio = _parse_hora(hora_inicio, "La hora de inicio")
    fin = _parse_hora(hora_fin, "La hora de fin")
    duracion_total = _minutos(fin) - _minutos(inicio)
    if duracion_total <= 0:
        raise CatalogError(
            "La hora de fin debe ser mayor que la hora de inicio."
        )

    precio_centavos = parse_precio(precio)
    _validar_bloques(db, bloques, duracion_total)

    return (
        nombre_limpio,
        dias,
        inicio.strftime("%H:%M"),
        fin.strftime("%H:%M"),
        precio_centavos,
    )


def crear_grupo(
    db: Session,
    sucursal_id: int,
    nombre: str,
    dias_semana: list[str],
    hora_inicio: str,
    hora_fin: str,
    precio: str,
    bloques: list[BloqueForm],
) -> Grupo:
    (
        nombre_limpio,
        dias,
        inicio,
        fin,
        precio_centavos,
    ) = _datos_grupo(
        db,
        sucursal_id,
        nombre,
        dias_semana,
        hora_inicio,
        hora_fin,
        precio,
        bloques,
        None,
    )

    grupo = Grupo(
        sucursal_id=sucursal_id,
        nombre=nombre_limpio,
        dias_semana=dias,
        hora_inicio=inicio,
        hora_fin=fin,
        precio_centavos=precio_centavos,
    )
    db.add(grupo)
    db.flush()
    _crear_bloques(db, grupo.id, bloques)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise CatalogError(
            "No se pudo crear el grupo: nombre duplicado o datos inválidos."
        ) from exc
    db.refresh(grupo)
    return grupo


def actualizar_grupo(
    db: Session,
    grupo_id: int,
    sucursal_id: int,
    nombre: str,
    dias_semana: list[str],
    hora_inicio: str,
    hora_fin: str,
    precio: str,
    bloques: list[BloqueForm],
) -> Grupo:
    grupo = db.scalar(select(Grupo).where(Grupo.id == grupo_id))
    if grupo is None:
        raise CatalogError("El grupo no existe.")

    (
        nombre_limpio,
        dias,
        inicio,
        fin,
        precio_centavos,
    ) = _datos_grupo(
        db,
        sucursal_id,
        nombre,
        dias_semana,
        hora_inicio,
        hora_fin,
        precio,
        bloques,
        grupo.id,
    )

    grupo.sucursal_id = sucursal_id
    grupo.nombre = nombre_limpio
    grupo.dias_semana = dias
    grupo.hora_inicio = inicio
    grupo.hora_fin = fin
    grupo.precio_centavos = precio_centavos
    grupo.actualizado_en = text("CURRENT_TIMESTAMP")

    for bloque in list(grupo.bloques):
        db.delete(bloque)
    db.flush()
    _crear_bloques(db, grupo.id, bloques)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise CatalogError(
            "No se pudo actualizar el grupo: nombre duplicado o datos "
            "inválidos."
        ) from exc
    db.refresh(grupo)
    return grupo


def cambiar_estado_grupo(
    db: Session,
    grupo_id: int,
    activo: bool,
) -> Grupo:
    grupo = db.scalar(select(Grupo).where(Grupo.id == grupo_id))
    if grupo is None:
        raise CatalogError("El grupo no existe.")
    if activo:
        sucursal = db.scalar(
            select(Sucursal).where(
                Sucursal.id == grupo.sucursal_id,
                Sucursal.activa == 1,
            )
        )
        if sucursal is None:
            raise CatalogError(
                "No se puede reactivar: la sucursal del grupo está inactiva."
            )
    grupo.activo = 1 if activo else 0
    grupo.actualizado_en = text("CURRENT_TIMESTAMP")
    db.commit()
    db.refresh(grupo)
    return grupo
