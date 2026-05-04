from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.models.conversa import EstadoConversa
from app.models.mensagem import DirecaoMensagem

class MensagemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    direcao: DirecaoMensagem
    conteudo: str
    classificacao_ia: str | None = None
    criada_em: datetime
    enviada_em: datetime | None = None

class ConversaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    anuncio_id: int
    instancia_id: int
    telefone: str
    estado: EstadoConversa
    score_interesse: int | None = None
    iniciada_em: datetime
    ultima_mensagem_em: datetime | None = None

class MensagemRecebidaInput(BaseModel):
    telefone_remetente: str
    instancia_evolution_id: str
    conteudo: str
    timestamp_whatsapp: datetime | None = None

class ProximaPendenteOutput(BaseModel):
    conversa_id: int
    mensagem_id: int
    instancia_id: int
    instancia_evolution_id: str
    telefone_destino: str
    mensagem: str

class IntervencaoInput(BaseModel):
    mensagem: str = Field(min_length=1, max_length=2000)

class EncerramentoInput(BaseModel):
    motivo: str = Field(min_length=1, max_length=200)
