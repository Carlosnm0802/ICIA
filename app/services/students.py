from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from unicodedata import normalize

from fastapi import UploadFile
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Alumno,
    Asistencia,
    Grupo,
    GrupoAlumno,
    Pago,
    Sesion,
    Sucursal,
)
from app.services import photos


class StudentError(Exception):
    pass


@dataclass(frozen=True)
class AlumnoResumen:
    id: int
    nombre: str
    tutor: str | None
    telefono_tutor: str | None
    estado: str
    foto_ruta: str | None
    grupos_activos: int


@dataclass(frozen=True)
class GrupoInscripcion:
    inscripcion_id: int
    grupo_id: int
    grupo_nombre: str
    sucursal_nombre: str
    dias_semana: str
    hora_inicio: str
    hora_fin: str
    precio_centavos: int
    fecha_alta: str
    fecha_baja: str | None
    activa: bool


@dataclass(frozen=True)
class PagoAlumno:
    id: int
    folio: str
    tipo: str
    monto_centavos: int
    metodo: str
    fecha: str
    estado: str


@dataclass(frozen=True)
class AsistenciaAlumno:
    fecha: str
    grupo_nombre: str
    sucursal_nombre: str
    estado: str
    es_reposicion: bool


@dataclass(frozen=True)
class AlumnoFicha:
    alumno: Alumno
    grupos: list[GrupoInscripcion]
    pagos: list[PagoAlumno]
    asistencias: list[AsistenciaAlumno]
    total_asistio: int
    total_falto: int


@dataclass(frozen=True)
class DatosAlumno:
    nombre: str
    fecha_nacimiento: str | None
    tutor: str | None
    telefono_tutor: str | None
    escuela_procedencia: str | None
    alergias_notas: str | None
    personas_autorizadas: str | None
    fecha_inscripcion: str


def _limpiar(valor: str | None) -> str:
    return " ".join((valor or "").split())


def _opcional(valor: str | None) -> str | None:
    limpio = _limpiar(valor)
    return limpio or None


def _exigir(valor: str | None, campo: str) -> str:
    limpio = _limpiar(valor)
    if not limpio:
        raise StudentError(f"{campo} es obligatorio.")
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
        raise StudentError(f"{campo} debe tener formato AAAA-MM-DD.") from exc
    if no_futura and fecha > date.today():
        raise StudentError(f"{campo} no puede estar en el futuro.")
    return fecha.isoformat()


def _clave_orden(nombre: str) -> str:
    sin_acentos = normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    return sin_acentos.casefold()


def _datos_alumno(
    *,
    nombre: str,
    fecha_nacimiento: str | None,
    tutor: str | None,
    telefono_tutor: str | None,
    escuela_procedencia: str | None,
    alergias_notas: str | None,
    personas_autorizadas: str | None,
    fecha_inscripcion: str | None,
    fecha_inscripcion_actual: str | None = None,
) -> DatosAlumno:
    return DatosAlumno(
        nombre=_exigir(nombre, "El nombre"),
        fecha_nacimiento=_fecha(
            fecha_nacimiento,
            "La fecha de nacimiento",
            no_futura=True,
        ),
        tutor=_opcional(tutor),
        telefono_tutor=_opcional(telefono_tutor),
        escuela_procedencia=_opcional(escuela_procedencia),
        alergias_notas=_opcional(alergias_notas),
        personas_autorizadas=_opcional(personas_autorizadas),
        fecha_inscripcion=(
            _fecha(
                fecha_inscripcion,
                "La fecha de inscripción",
                no_futura=True,
            )
            or fecha_inscripcion_actual
            or date.today().isoformat()
        ),
    )


def listar_alumnos(
    db: Session,
    *,
    q: str | None = None,
    estado: str = "activo",
    grupo_id: int | None = None,
) -> list[AlumnoResumen]:
    if estado not in {"activo", "baja", "todos"}:
        raise StudentError("El estado solicitado no es válido.")

    grupos_activos = (
        select(func.count(GrupoAlumno.id))
        .where(
            GrupoAlumno.alumno_id == Alumno.id,
            GrupoAlumno.fecha_baja.is_(None),
        )
        .correlate(Alumno)
        .scalar_subquery()
    )
    consulta = select(Alumno, grupos_activos.label("grupos_activos"))
    if estado != "todos":
        consulta = consulta.where(Alumno.estado == estado)
    if grupo_id is not None:
        consulta = consulta.where(
            Alumno.id.in_(
                select(GrupoAlumno.alumno_id).where(
                    GrupoAlumno.grupo_id == grupo_id,
                    GrupoAlumno.fecha_baja.is_(None),
                )
            )
        )

    filas = db.execute(consulta).all()
    busqueda = _clave_orden(_limpiar(q))
    alumnos: list[AlumnoResumen] = []
    for alumno, total in filas:
        if busqueda:
            texto = _clave_orden(
                " ".join(
                    valor
                    for valor in (
                        alumno.nombre,
                        alumno.tutor or "",
                        alumno.telefono_tutor or "",
                    )
                    if valor
                )
            )
            if busqueda not in texto:
                continue
        alumnos.append(
            AlumnoResumen(
                id=alumno.id,
                nombre=alumno.nombre,
                tutor=alumno.tutor,
                telefono_tutor=alumno.telefono_tutor,
                estado=alumno.estado,
                foto_ruta=alumno.foto_ruta,
                grupos_activos=int(total or 0),
            )
        )
    return sorted(alumnos, key=lambda item: _clave_orden(item.nombre))


def obtener_alumno(db: Session, alumno_id: int) -> Alumno | None:
    return db.scalar(select(Alumno).where(Alumno.id == alumno_id))


def obtener_ficha(db: Session, alumno_id: int) -> AlumnoFicha | None:
    alumno = obtener_alumno(db, alumno_id)
    if alumno is None:
        return None

    filas_grupos = db.execute(
        select(GrupoAlumno, Grupo, Sucursal)
        .join(Grupo, Grupo.id == GrupoAlumno.grupo_id)
        .join(Sucursal, Sucursal.id == Grupo.sucursal_id)
        .where(GrupoAlumno.alumno_id == alumno.id)
        .order_by(
            GrupoAlumno.fecha_baja.is_(None).desc(),
            GrupoAlumno.fecha_alta.desc(),
            Grupo.nombre,
        )
    ).all()
    grupos = [
        GrupoInscripcion(
            inscripcion_id=inscripcion.id,
            grupo_id=grupo.id,
            grupo_nombre=grupo.nombre,
            sucursal_nombre=sucursal.nombre,
            dias_semana=grupo.dias_semana,
            hora_inicio=grupo.hora_inicio,
            hora_fin=grupo.hora_fin,
            precio_centavos=grupo.precio_centavos,
            fecha_alta=inscripcion.fecha_alta,
            fecha_baja=inscripcion.fecha_baja,
            activa=inscripcion.fecha_baja is None,
        )
        for inscripcion, grupo, sucursal in filas_grupos
    ]

    pagos = [
        PagoAlumno(
            id=pago.id,
            folio=pago.folio,
            tipo=pago.tipo,
            monto_centavos=pago.monto_centavos,
            metodo=pago.metodo,
            fecha=pago.fecha,
            estado=pago.estado,
        )
        for pago in db.scalars(
            select(Pago)
            .where(Pago.alumno_id == alumno.id)
            .order_by(Pago.fecha.desc(), Pago.id.desc())
        )
    ]

    filas_asistencias = db.execute(
        select(Asistencia, Sesion.fecha, Grupo.nombre, Sucursal.nombre)
        .join(Sesion, Sesion.id == Asistencia.sesion_id)
        .join(Grupo, Grupo.id == Sesion.grupo_id)
        .join(Sucursal, Sucursal.id == Grupo.sucursal_id)
        .where(Asistencia.alumno_id == alumno.id)
        .order_by(Sesion.fecha.desc(), Asistencia.id.desc())
        .limit(20)
    ).all()
    asistencias = [
        AsistenciaAlumno(
            fecha=fecha,
            grupo_nombre=grupo_nombre,
            sucursal_nombre=sucursal_nombre,
            estado=asistencia.estado,
            es_reposicion=bool(asistencia.es_reposicion),
        )
        for asistencia, fecha, grupo_nombre, sucursal_nombre in filas_asistencias
    ]

    conteos = dict(
        db.execute(
            select(Asistencia.estado, func.count(Asistencia.id))
            .where(Asistencia.alumno_id == alumno.id)
            .group_by(Asistencia.estado)
        ).all()
    )
    return AlumnoFicha(
        alumno=alumno,
        grupos=grupos,
        pagos=pagos,
        asistencias=asistencias,
        total_asistio=int(conteos.get("asistio", 0)),
        total_falto=int(conteos.get("falto", 0)),
    )


def crear_alumno(
    db: Session,
    *,
    nombre: str,
    fecha_nacimiento: str | None = None,
    tutor: str | None = None,
    telefono_tutor: str | None = None,
    escuela_procedencia: str | None = None,
    alergias_notas: str | None = None,
    personas_autorizadas: str | None = None,
    fecha_inscripcion: str | None = None,
    foto: UploadFile | None = None,
) -> Alumno:
    datos = _datos_alumno(
        nombre=nombre,
        fecha_nacimiento=fecha_nacimiento,
        tutor=tutor,
        telefono_tutor=telefono_tutor,
        escuela_procedencia=escuela_procedencia,
        alergias_notas=alergias_notas,
        personas_autorizadas=personas_autorizadas,
        fecha_inscripcion=fecha_inscripcion,
    )
    ruta_foto = photos.guardar_foto(foto, "alumnos")
    alumno = Alumno(
        nombre=datos.nombre,
        fecha_nacimiento=datos.fecha_nacimiento,
        tutor=datos.tutor,
        telefono_tutor=datos.telefono_tutor,
        escuela_procedencia=datos.escuela_procedencia,
        alergias_notas=datos.alergias_notas,
        personas_autorizadas=datos.personas_autorizadas,
        fecha_inscripcion=datos.fecha_inscripcion,
        foto_ruta=ruta_foto,
        estado="activo",
    )
    db.add(alumno)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        photos.borrar_foto(ruta_foto)
        raise StudentError(
            "No se pudo crear el alumno: datos inválidos."
        ) from exc
    except Exception:
        db.rollback()
        photos.borrar_foto(ruta_foto)
        raise
    db.refresh(alumno)
    return alumno


def actualizar_alumno(
    db: Session,
    alumno_id: int,
    *,
    nombre: str,
    fecha_nacimiento: str | None = None,
    tutor: str | None = None,
    telefono_tutor: str | None = None,
    escuela_procedencia: str | None = None,
    alergias_notas: str | None = None,
    personas_autorizadas: str | None = None,
    fecha_inscripcion: str | None = None,
    foto: UploadFile | None = None,
    quitar_foto: bool = False,
) -> Alumno:
    alumno = obtener_alumno(db, alumno_id)
    if alumno is None:
        raise StudentError("El alumno no existe.")

    datos = _datos_alumno(
        nombre=nombre,
        fecha_nacimiento=fecha_nacimiento,
        tutor=tutor,
        telefono_tutor=telefono_tutor,
        escuela_procedencia=escuela_procedencia,
        alergias_notas=alergias_notas,
        personas_autorizadas=personas_autorizadas,
        fecha_inscripcion=fecha_inscripcion,
        fecha_inscripcion_actual=alumno.fecha_inscripcion,
    )
    ruta_anterior = alumno.foto_ruta
    ruta_nueva = photos.guardar_foto(foto, "alumnos")

    alumno.nombre = datos.nombre
    alumno.fecha_nacimiento = datos.fecha_nacimiento
    alumno.tutor = datos.tutor
    alumno.telefono_tutor = datos.telefono_tutor
    alumno.escuela_procedencia = datos.escuela_procedencia
    alumno.alergias_notas = datos.alergias_notas
    alumno.personas_autorizadas = datos.personas_autorizadas
    alumno.fecha_inscripcion = datos.fecha_inscripcion
    if ruta_nueva is not None:
        alumno.foto_ruta = ruta_nueva
    elif quitar_foto:
        alumno.foto_ruta = None
    alumno.actualizado_en = text("CURRENT_TIMESTAMP")

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        photos.borrar_foto(ruta_nueva)
        raise StudentError(
            "No se pudo actualizar el alumno: datos inválidos."
        ) from exc
    except Exception:
        db.rollback()
        photos.borrar_foto(ruta_nueva)
        raise
    if ruta_anterior and ruta_anterior != alumno.foto_ruta:
        photos.borrar_foto(ruta_anterior)
    db.refresh(alumno)
    return alumno


def cambiar_estado_alumno(
    db: Session,
    alumno_id: int,
    estado: str,
) -> Alumno:
    if estado not in {"activo", "baja"}:
        raise StudentError("El estado del alumno no es válido.")
    alumno = obtener_alumno(db, alumno_id)
    if alumno is None:
        raise StudentError("El alumno no existe.")
    if alumno.estado == estado:
        return alumno

    hoy = date.today().isoformat()
    if estado == "baja":
        db.execute(
            update(GrupoAlumno)
            .where(
                GrupoAlumno.alumno_id == alumno.id,
                GrupoAlumno.fecha_baja.is_(None),
                GrupoAlumno.fecha_alta <= hoy,
            )
            .values(fecha_baja=hoy)
        )
    alumno.estado = estado
    alumno.actualizado_en = text("CURRENT_TIMESTAMP")
    db.commit()
    db.refresh(alumno)
    return alumno


def agregar_grupo(
    db: Session,
    alumno_id: int,
    grupo_id: int,
) -> GrupoAlumno:
    alumno = obtener_alumno(db, alumno_id)
    if alumno is None:
        raise StudentError("El alumno no existe.")
    if alumno.estado != "activo":
        raise StudentError("Un alumno dado de baja no puede inscribirse.")
    grupo = db.scalar(
        select(Grupo).where(Grupo.id == grupo_id, Grupo.activo == 1)
    )
    if grupo is None:
        raise StudentError("Selecciona un grupo activo.")
    existente = db.scalar(
        select(GrupoAlumno.id).where(
            GrupoAlumno.alumno_id == alumno.id,
            GrupoAlumno.grupo_id == grupo.id,
            GrupoAlumno.fecha_baja.is_(None),
        )
    )
    if existente is not None:
        raise StudentError("El alumno ya está inscrito en ese grupo.")

    inscripcion = GrupoAlumno(
        alumno_id=alumno.id,
        grupo_id=grupo.id,
        fecha_alta=date.today().isoformat(),
    )
    db.add(inscripcion)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise StudentError(
            "No se pudo inscribir al alumno en el grupo."
        ) from exc
    db.refresh(inscripcion)
    return inscripcion


def dar_baja_grupo(
    db: Session,
    alumno_id: int,
    inscripcion_id: int,
) -> GrupoAlumno:
    inscripcion = db.scalar(
        select(GrupoAlumno).where(
            GrupoAlumno.id == inscripcion_id,
            GrupoAlumno.alumno_id == alumno_id,
        )
    )
    if inscripcion is None:
        raise StudentError("La inscripción no existe.")
    if inscripcion.fecha_baja is not None:
        return inscripcion

    hoy = date.today().isoformat()
    if inscripcion.fecha_alta > hoy:
        raise StudentError(
            "La fecha de alta es posterior a hoy; revisa la inscripción."
        )
    inscripcion.fecha_baja = hoy
    db.commit()
    db.refresh(inscripcion)
    return inscripcion
