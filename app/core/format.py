from datetime import date

DIAS = (
    "lunes",
    "martes",
    "miércoles",
    "jueves",
    "viernes",
    "sábado",
    "domingo",
)
MESES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def formato_mxn(centavos: int) -> str:
    signo = "-" if centavos < 0 else ""
    entero, resto = divmod(abs(centavos), 100)
    return f"{signo}${entero:,}.{resto:02d}"


def formato_fecha(iso: str) -> str:
    try:
        fecha = date.fromisoformat(iso)
    except ValueError:
        return iso
    return fecha.strftime("%d/%m/%Y")


def formato_fecha_corta(iso: str) -> str:
    try:
        fecha = date.fromisoformat(iso)
    except ValueError:
        return iso
    return fecha.strftime("%d/%m")


def formato_fecha_larga(iso: str) -> str:
    try:
        fecha = date.fromisoformat(iso)
    except ValueError:
        return iso
    dia = DIAS[fecha.weekday()].capitalize()
    mes = MESES[fecha.month - 1]
    return f"{dia} {fecha.day} de {mes} de {fecha.year}"
