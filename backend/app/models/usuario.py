from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database import Base

class UsuarioDashboard(Base):
    __tablename__ = "usuarios_dashboard"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(120), unique=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    nome: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20), default="OPERADOR")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
