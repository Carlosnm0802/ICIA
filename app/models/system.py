from sqlalchemy import Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Configuracion(Base):
    __tablename__ = "configuracion"

    clave: Mapped[str] = mapped_column(Text, primary_key=True, nullable=True)
    valor: Mapped[str] = mapped_column(Text, nullable=False)
    actualizado_en: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
