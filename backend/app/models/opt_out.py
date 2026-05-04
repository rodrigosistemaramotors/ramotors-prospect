from datetime import datetime
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database import Base

class OptOut(Base):
    __tablename__ = "opt_outs"

    telefone: Mapped[str] = mapped_column(String(20), primary_key=True)
    motivo: Mapped[str | None] = mapped_column(String(60))
    origem: Mapped[str | None] = mapped_column(String(40))
    registrado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
