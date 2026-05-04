import enum
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    String, BigInteger, Integer, DateTime, Enum, ForeignKey, Text, Numeric, SmallInteger
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database import Base

class StatusFunil(str, enum.Enum):
    NOVO = "NOVO"
    CONTATADO = "CONTATADO"
    EM_NEGOCIACAO = "EM_NEGOCIACAO"
    CONTRATO_ASSINADO = "CONTRATO_ASSINADO"
    PERDIDO = "PERDIDO"
    GANHO = "GANHO"

class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conversa_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("conversas.id"), unique=True
    )
    anuncio_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("anuncios.id"))
    score_interesse: Mapped[int] = mapped_column(SmallInteger)
    nome: Mapped[str | None] = mapped_column(String(120))
    telefone: Mapped[str] = mapped_column(String(20))
    resumo_ia: Mapped[str | None] = mapped_column(Text)
    sugestao_abordagem: Mapped[str | None] = mapped_column(Text)
    atribuido_a: Mapped[int | None] = mapped_column(Integer, ForeignKey("vendedores.id"))
    status_funil: Mapped[StatusFunil] = mapped_column(
        Enum(StatusFunil, name="status_funil"), default=StatusFunil.NOVO
    )
    valor_estimado: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
