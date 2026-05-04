import enum
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    String, BigInteger, DateTime, Enum, JSON, ForeignKey, Text, Numeric
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database import Base

class DirecaoMensagem(str, enum.Enum):
    SAIDA = "SAIDA"
    ENTRADA = "ENTRADA"

class Mensagem(Base):
    __tablename__ = "mensagens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conversa_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("conversas.id"), index=True
    )
    direcao: Mapped[DirecaoMensagem] = mapped_column(
        Enum(DirecaoMensagem, name="direcao_mensagem")
    )
    conteudo: Mapped[str] = mapped_column(Text)
    classificacao_ia: Mapped[str | None] = mapped_column(String(40))
    score_ia: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    criada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    entregue_para_envio_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enviada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dados_extras: Mapped[dict] = mapped_column(JSON, default=dict)
