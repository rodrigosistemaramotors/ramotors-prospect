"""
Webhook publico que recebe mensagens recebidas via Z-API.
URL: https://ramotors-api-cuiaba.onrender.com/webhook/zapi?secret=...

Z-API POSTa o payload no formato:
{
  "instanceId": "...",
  "messageId": "...",
  "phone": "5565999998888",
  "fromMe": false,
  "momment": 1735000000000,
  "type": "ReceivedCallback",
  "text": {"message": "Ola, vi seu carro"}
  # ou audio, image, etc.
}
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database import get_db
from app.config import settings
from app.models import (
    Conversa, EstadoConversa, Mensagem, DirecaoMensagem,
    Anuncio, StatusContato, OptOut, Lead, StatusFunil,
)
from app.services.ia_groq import GroqClient
from app.utils.opt_out_detector import eh_opt_out

router = APIRouter(prefix="/webhook", tags=["webhook"])


def _normalizar_telefone(numero: str) -> str:
    """Adiciona '+' se nao tiver."""
    if not numero:
        return numero
    n = numero.strip()
    if not n.startswith("+"):
        n = "+" + n
    return n


def _variacoes_telefone_br(numero: str) -> list[str]:
    """
    Retorna possiveis variacoes do telefone para celulares brasileiros.

    Z-API/WhatsApp as vezes descarta o '9' inicial do celular (formato antigo
    de 8 digitos vs novo de 9 digitos pos-2012). Pra match no banco a gente
    tenta as duas formas.

    Exemplos:
      '+5565996236037' (13 chars) -> ['+5565996236037', '+556596236037']
      '+556596236037' (12 chars)  -> ['+556596236037', '+5565996236037']
    """
    n = _normalizar_telefone(numero)
    variantes = [n]

    if n.startswith("+55") and len(n) >= 12:
        digits = n[3:]  # remove '+55'
        if len(digits) == 10:
            # Sem o '9' (DDD + 8 digitos). Tenta adicionar o '9'.
            area = digits[:2]
            sub = digits[2:]
            variantes.append(f"+55{area}9{sub}")
        elif len(digits) == 11 and digits[2] == "9":
            # Com o '9'. Tenta sem.
            area = digits[:2]
            sub = digits[3:]
            variantes.append(f"+55{area}{sub}")

    return variantes


def _extrair_conteudo(body: dict) -> str | None:
    """Extrai o texto da mensagem do payload Z-API. Retorna None se nao houver."""
    if body.get("text"):
        msg = body["text"].get("message")
        if msg:
            return msg.strip()

    # Tipos nao suportados - retorna placeholder
    if body.get("audio"):
        return "[mensagem de audio - nao suportada]"
    if body.get("image"):
        return "[mensagem de imagem - nao suportada]"
    if body.get("video"):
        return "[mensagem de video - nao suportada]"
    if body.get("document"):
        return "[documento - nao suportado]"
    if body.get("sticker"):
        return "[sticker - nao suportado]"

    return None


@router.post("/zapi")
async def receber_zapi(
    request: Request,
    secret: str = Query(..., description="Webhook secret"),
    db: AsyncSession = Depends(get_db),
):
    # 1. Autenticacao via secret na URL
    if secret != settings.zapi_webhook_secret:
        logger.warning("Z-API webhook com secret invalido")
        raise HTTPException(401, "Secret invalido")

    # 2. Parse body
    try:
        body = await request.json()
    except Exception:
        logger.error("Z-API webhook com body invalido")
        raise HTTPException(400, "Body invalido")

    # 3. Filtros basicos
    if body.get("fromMe"):
        return {"status": "ignorado_outgoing"}

    phone_raw = body.get("phone") or ""
    if "@g.us" in phone_raw or body.get("isGroup"):
        return {"status": "ignorado_grupo"}

    if not phone_raw:
        return {"status": "ignorado_sem_telefone"}

    conteudo = _extrair_conteudo(body)
    if not conteudo:
        return {"status": "ignorado_sem_conteudo"}

    # 4. Encontrar conversa ativa.
    # Tenta variacoes do telefone (com e sem '9' do celular BR) porque
    # a Z-API normaliza pro formato antigo (12 digitos) e o banco pode
    # ter o formato novo (13 digitos).
    telefone = _normalizar_telefone(phone_raw)
    variantes = _variacoes_telefone_br(phone_raw)
    instance_id = body.get("instanceId", "default")

    q = await db.execute(
        select(Conversa)
        .where(Conversa.telefone.in_(variantes))
        .where(Conversa.estado.notin_([
            EstadoConversa.ENCERRADA_NEGATIVA,
            EstadoConversa.ENCERRADA_POSITIVA,
            EstadoConversa.OPT_OUT,
        ]))
        .order_by(Conversa.iniciada_em.desc())
        .limit(1)
    )
    conversa = q.scalar_one_or_none()
    if not conversa:
        logger.info(
            f"Z-API webhook: conversa nao encontrada para {telefone} "
            f"(tentou variantes: {variantes})"
        )
        return {"status": "ignorado_conversa_inexistente"}

    # 5. Persistir mensagem de entrada
    timestamp_ms = body.get("momment")
    timestamp_ts = (
        datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
        if timestamp_ms else datetime.now(timezone.utc)
    )

    msg_entrada = Mensagem(
        conversa_id=conversa.id,
        direcao=DirecaoMensagem.ENTRADA,
        conteudo=conteudo,
        dados_extras={
            "whatsapp_timestamp": timestamp_ts.isoformat(),
            "zapi_message_id": body.get("messageId"),
            "zapi_instance_id": instance_id,
        },
    )
    db.add(msg_entrada)

    # 6. Opt-out por regex
    if eh_opt_out(conteudo):
        conversa.estado = EstadoConversa.OPT_OUT
        conversa.encerrada_em = datetime.now(timezone.utc)
        anuncio = await db.get(Anuncio, conversa.anuncio_id)
        if anuncio:
            anuncio.status_contato = StatusContato.OPT_OUT
        existe = await db.get(OptOut, conversa.telefone)
        if not existe:
            db.add(OptOut(
                telefone=conversa.telefone,
                motivo="Opt-out automatico por regex",
                origem="auto_regex",
            ))
        await db.commit()
        return {"status": "opt_out", "conversa_id": conversa.id}

    # 7. Buscar historico para IA
    hist_q = await db.execute(
        select(Mensagem)
        .where(Mensagem.conversa_id == conversa.id)
        .order_by(Mensagem.criada_em)
    )
    historico = list(hist_q.scalars())
    historico_dict = [
        {"direcao": m.direcao.value, "conteudo": m.conteudo} for m in historico
    ]

    anuncio = await db.get(Anuncio, conversa.anuncio_id)
    contexto = {
        "modelo": anuncio.modelo if anuncio else None,
        "ano": anuncio.ano if anuncio else None,
        "preco": float(anuncio.preco) if anuncio and anuncio.preco else None,
    }

    # 8. Classificar via Groq
    groq = GroqClient()
    msg_inicial = next(
        (m.conteudo for m in historico if m.direcao == DirecaoMensagem.SAIDA), ""
    )
    classificacao = await groq.classificar_resposta(
        msg_inicial,
        [m.conteudo for m in historico[-5:]],
        conteudo,
        contexto,
    )

    msg_entrada.classificacao_ia = classificacao["categoria"]
    score = classificacao.get("score_interesse", 0)
    conversa.score_interesse = score

    categoria = classificacao["categoria"]
    proxima_resposta = None

    if categoria == "INTERESSADO":
        conversa.estado = EstadoConversa.QUALIFICADA
        if anuncio:
            anuncio.status_contato = StatusContato.RESPONDIDO
        lead_q = await db.execute(
            select(Lead).where(Lead.conversa_id == conversa.id)
        )
        if not lead_q.scalar_one_or_none():
            lead = Lead(
                conversa_id=conversa.id,
                anuncio_id=anuncio.id if anuncio else None,
                score_interesse=score,
                nome=classificacao.get("extrair_nome"),
                telefone=conversa.telefone,
                resumo_ia=classificacao.get("resumo"),
                sugestao_abordagem=classificacao.get("proxima_acao_sugerida"),
                status_funil=StatusFunil.NOVO,
            )
            db.add(lead)
        proxima_resposta = await groq.gerar_resposta_contextual(
            historico_dict, conteudo, contexto
        )
    elif categoria == "PEDIU_INFO":
        conversa.estado = EstadoConversa.EM_NEGOCIACAO
        proxima_resposta = await groq.gerar_resposta_contextual(
            historico_dict, conteudo, contexto
        )
    elif categoria == "TALVEZ":
        conversa.estado = EstadoConversa.EM_NEGOCIACAO
        proxima_resposta = await groq.gerar_resposta_contextual(
            historico_dict, conteudo, contexto
        )
    elif categoria == "RECUSOU":
        conversa.estado = EstadoConversa.ENCERRADA_NEGATIVA
        conversa.encerrada_em = datetime.now(timezone.utc)
        proxima_resposta = (
            "Sem problema! Obrigado pela atencao e boa sorte com a venda. "
            "Estamos por aqui se mudar de ideia."
        )
    elif categoria == "JA_VENDEU":
        conversa.estado = EstadoConversa.ENCERRADA_POSITIVA
        conversa.encerrada_em = datetime.now(timezone.utc)
        if anuncio:
            anuncio.status_contato = StatusContato.IGNORADO
        proxima_resposta = (
            "Que otima noticia! Parabens pela venda. Qualquer outro veiculo "
            "que pretender vender, pode contar com a gente."
        )
    elif categoria == "OPT_OUT":
        conversa.estado = EstadoConversa.OPT_OUT
        conversa.encerrada_em = datetime.now(timezone.utc)
        if anuncio:
            anuncio.status_contato = StatusContato.OPT_OUT
        existe = await db.get(OptOut, conversa.telefone)
        if not existe:
            db.add(OptOut(
                telefone=conversa.telefone,
                motivo="Opt-out via classificacao IA",
                origem="auto_ia",
            ))
    elif categoria == "IGNOROU":
        # Mensagem nao classificavel mas conteudo presente -> tenta retomar
        # via resposta contextual leve. Mantem estado atual da conversa.
        if conteudo and len(conteudo.strip()) > 0:
            proxima_resposta = await groq.gerar_resposta_contextual(
                historico_dict, conteudo, contexto
            )

    # 9. Persistir resposta como pendente. Loop-envios vai pegar e enviar.
    if proxima_resposta:
        db.add(Mensagem(
            conversa_id=conversa.id,
            direcao=DirecaoMensagem.SAIDA,
            conteudo=proxima_resposta,
        ))

    conversa.ultima_mensagem_em = datetime.now(timezone.utc)
    await db.commit()

    return {
        "status": "ok",
        "categoria": categoria,
        "score": score,
        "tem_resposta": bool(proxima_resposta),
        "conversa_id": conversa.id,
    }


@router.get("/zapi/health")
async def health():
    return {"ok": True, "endpoint": "/webhook/zapi"}
