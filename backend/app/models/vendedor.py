from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Boolean, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database import Base

class Vendedor(Base):
    __tablename__ = "vendedores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    whatsapp: Mapped[str] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(120))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    leads_max_dia: Mapped[int] = mapped_column(SmallInteger, default=20)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
