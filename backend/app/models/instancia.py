import enum
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Enum, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database import Base

class StatusInstancia(str, enum.Enum):
    ATIVA = "ATIVA"
    AQUECENDO = "AQUECENDO"
    PAUSADA = "PAUSADA"
    BANIDA = "BANIDA"

class InstanciaWhatsapp(Base):
    __tablename__ = "instancias_whatsapp"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(60), unique=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True)
    evolution_instance_id: Mapped[str] = mapped_column(String(120), unique=True)
    status: Mapped[StatusInstancia] = mapped_column(
        Enum(StatusInstancia, name="status_instancia"),
        default=StatusInstancia.AQUECENDO,
    )
    msgs_enviadas_hoje: Mapped[int] = mapped_column(SmallInteger, default=0)
    msgs_enviadas_total: Mapped[int] = mapped_column(Integer, default=0)
    limite_diario: Mapped[int] = mapped_column(SmallInteger, default=80)
    janela_segundos_min: Mapped[int] = mapped_column(SmallInteger, default=60)
    janela_segundos_max: Mapped[int] = mapped_column(SmallInteger, default=180)
    ultima_msg_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    banida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
