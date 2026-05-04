from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict
from app.models.anuncio import FonteAnuncio, StatusContato

class AnuncioBase(BaseModel):
    fonte: FonteAnuncio
    url: str
    url_canonica: str
    titulo: str
    modelo: str | None = None
    marca: str | None = None
    ano: int | None = None
    km: int | None = None
    preco: Decimal | None = None
    cidade: str
    bairro: str | None = None
    nome_vendedor: str | None = None
    telefone: str | None = None
    descricao: str | None = None
    fotos_urls: list[str] = Field(default_factory=list)
    vendedor_tipo: str = "PARTICULAR"
    publicado_em: datetime | None = None
    dados_extras: dict = Field(default_factory=dict)

class AnuncioCreate(AnuncioBase):
    hash_unico: str

class AnuncioRead(AnuncioBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    hash_unico: str
    capturado_em: datetime
    status_contato: StatusContato

class AnuncioLote(BaseModel):
    anuncios: list[AnuncioCreate]

class AnuncioStatusUpdate(BaseModel):
    status_contato: StatusContato
