import enum
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    String, Integer, BigInteger, Numeric, DateTime, Enum, Text, JSON, SmallInteger
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database import Base

class FonteAnuncio(str, enum.Enum):
    OLX = "OLX"
    USADOFACIL = "USADOFACIL"
    OUTROS = "OUTROS"

class StatusContato(str, enum.Enum):
    PENDENTE = "PENDENTE"
    MENSAGEM_GERADA = "MENSAGEM_GERADA"
    ENVIANDO = "ENVIANDO"
    ENVIADO = "ENVIADO"
    ENTREGUE = "ENTREGUE"
    LIDO = "LIDO"
    RESPONDIDO = "RESPONDIDO"
    FALHOU = "FALHOU"
    IGNORADO = "IGNORADO"
    OPT_OUT = "OPT_OUT"

class Anuncio(Base):
    __tablename__ = "anuncios"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    fonte: Mapped[FonteAnuncio] = mapped_column(Enum(FonteAnuncio, name="fonte_anuncio"))
    url: Mapped[str] = mapped_column(Text)
    url_canonica: Mapped[str] = mapped_column(Text)
    hash_unico: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    titulo: Mapped[str] = mapped_column(Text)
    modelo: Mapped[str | None] = mapped_column(String(120))
    marca: Mapped[str | None] = mapped_column(String(60))
    ano: Mapped[int | None] = mapped_column(SmallInteger)
    km: Mapped[int | None] = mapped_column(Integer)
    preco: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    cidade: Mapped[str] = mapped_column(String(60), index=True)
    bairro: Mapped[str | None] = mapped_column(String(120))
    nome_vendedor: Mapped[str | None] = mapped_column(String(120))
    telefone: Mapped[str | None] = mapped_column(String(20), index=True)
    descricao: Mapped[str | None] = mapped_column(Text)
    fotos_urls: Mapped[list] = mapped_column(JSON, default=list)
    vendedor_tipo: Mapped[str] = mapped_column(String(20), default="PARTICULAR")
    capturado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    publicado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status_contato: Mapped[StatusContato] = mapped_column(
        Enum(StatusContato, name="status_contato"),
        default=StatusContato.PENDENTE,
        index=True,
    )
    dados_extras: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
