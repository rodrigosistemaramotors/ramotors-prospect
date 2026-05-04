import enum
from datetime import datetime
from sqlalchemy import (
    String, BigInteger, Integer, DateTime, Enum, JSON, ForeignKey, SmallInteger
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database import Base

class EstadoConversa(str, enum.Enum):
    INICIADA = "INICIADA"
    AGUARDANDO_RESPOSTA = "AGUARDANDO_RESPOSTA"
    EM_NEGOCIACAO = "EM_NEGOCIACAO"
    QUALIFICADA = "QUALIFICADA"
    ESCALADA = "ESCALADA"
    ENCERRADA_POSITIVA = "ENCERRADA_POSITIVA"
    ENCERRADA_NEGATIVA = "ENCERRADA_NEGATIVA"
    OPT_OUT = "OPT_OUT"

class Conversa(Base):
    __tablename__ = "conversas"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    anuncio_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("anuncios.id"))
    instancia_id: Mapped[int] = mapped_column(Integer, ForeignKey("instancias_whatsapp.id"))
    telefone: Mapped[str] = mapped_column(String(20), index=True)
    estado: Mapped[EstadoConversa] = mapped_column(
        Enum(EstadoConversa, name="estado_conversa"),
        default=EstadoConversa.INICIADA,
        index=True,
    )
    score_interesse: Mapped[int | None] = mapped_column(SmallInteger)
    iniciada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ultima_mensagem_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    encerrada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dados_extras: Mapped[dict] = mapped_column(JSON, default=dict)
