from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from app.database import get_db
from app.deps import usuario_atual
from app.models import Anuncio, Mensagem, Lead, DirecaoMensagem, StatusFunil

router = APIRouter(prefix="/metricas", tags=["metricas"])

@router.get("/dashboard")
async def dashboard(
    db: AsyncSession = Depends(get_db),
    _u = Depends(usuario_atual),
):
    hoje = date.today()

    anuncios_hoje = await db.scalar(
        select(func.count(Anuncio.id))
        .where(func.date(Anuncio.capturado_em) == hoje)
    )
    msgs_hoje = await db.scalar(
        select(func.count(Mensagem.id))
        .where(func.date(Mensagem.enviada_em) == hoje)
        .where(Mensagem.direcao == DirecaoMensagem.SAIDA)
    )
    respostas_hoje = await db.scalar(
        select(func.count(Mensagem.id))
        .where(func.date(Mensagem.criada_em) == hoje)
        .where(Mensagem.direcao == DirecaoMensagem.ENTRADA)
    )
    leads_quentes = await db.scalar(
        select(func.count(Lead.id))
        .where(Lead.score_interesse >= 70)
        .where(Lead.status_funil == StatusFunil.NOVO)
    )

    taxa = 0.0
    if msgs_hoje and msgs_hoje > 0:
        taxa = round((respostas_hoje or 0) / msgs_hoje * 100, 1)

    return {
        "anuncios_hoje": anuncios_hoje or 0,
        "msgs_hoje": msgs_hoje or 0,
        "respostas_hoje": respostas_hoje or 0,
        "leads_quentes": leads_quentes or 0,
        "taxa_resposta_pct": taxa,
    }
