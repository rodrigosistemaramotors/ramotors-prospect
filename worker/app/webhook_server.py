"""
Servidor HTTP que recebe webhooks da Evolution API e enfileira processamento.
"""
from fastapi import FastAPI, Request, HTTPException, Header
from loguru import logger
from datetime import datetime, timezone
from app.celery_app import celery_app
from app.config import settings

app = FastAPI(title="RA Motors Webhook Receiver", version="2.1.0")

_eventos_processados: set[str] = set()
_MAX_DEDUP_SET = 10_000


def _normalizar_telefone_evolution(remote_jid: str) -> str:
    numero = remote_jid.split("@")[0]
    if not numero.startswith("+"):
        numero = "+" + numero
    return numero


def _registrar_evento(message_id: str) -> bool:
    if message_id in _eventos_processados:
        return False
    _eventos_processados.add(message_id)
    if len(_eventos_processados) > _MAX_DEDUP_SET:
        for _ in range(1000):
            try:
                _eventos_processados.pop()
            except KeyError:
                break
    return True


@app.get("/")
async def root():
    return {"sistema": "RA Motors Webhook Receiver", "status": "online"}

@app.get("/health")
async def health():
    return {"ok": True, "eventos_em_cache": len(_eventos_processados)}

@app.post("/webhook/evolution")
async def receber_evolution_webhook(
    request: Request,
    x_evolution_apikey: str | None = Header(None, alias="apikey"),
):
    if x_evolution_apikey and x_evolution_apikey != settings.evolution_key:
        logger.warning("Webhook recebido com apikey invalida")
        raise HTTPException(401, "API key invalida")

    try:
        body = await request.json()
    except Exception:
        logger.error("Webhook com body invalido")
        raise HTTPException(400, "Body invalido")

    evento = body.get("event") or body.get("type")
    instance = body.get("instance")
    data = body.get("data", {})

    logger.debug(f"Webhook: evento={evento} instance={instance}")

    if evento in ("messages.upsert", "MESSAGES_UPSERT"):
        return await _processar_messages_upsert(data, instance)
    if evento in ("messages.update", "MESSAGES_UPDATE"):
        return {"status": "ok"}
    if evento in ("connection.update", "CONNECTION_UPDATE"):
        return await _processar_connection_update(data, instance)

    return {"status": "evento_ignorado", "evento": evento}


async def _processar_messages_upsert(data: dict, instance: str) -> dict:
    key = data.get("key", {})
    message_id = key.get("id")
    from_me = key.get("fromMe", False)
    remote_jid = key.get("remoteJid", "")

    if not message_id:
        return {"status": "ignorado_sem_id"}

    if not _registrar_evento(message_id):
        return {"status": "duplicado"}

    if from_me:
        return {"status": "ignorado_outgoing"}

    if "@g.us" in remote_jid:
        return {"status": "ignorado_grupo"}

    message = data.get("message", {})
    conteudo = (
        message.get("conversation")
        or message.get("extendedTextMessage", {}).get("text")
        or ""
    )

    tipo_nao_suportado = None
    if message.get("audioMessage"):
        tipo_nao_suportado = "audio"
    elif message.get("imageMessage"):
        tipo_nao_suportado = "imagem"
    elif message.get("stickerMessage"):
        tipo_nao_suportado = "sticker"
    elif message.get("videoMessage"):
        tipo_nao_suportado = "video"

    if tipo_nao_suportado and not conteudo:
        conteudo = f"[mensagem de {tipo_nao_suportado} - nao suportada]"

    if not conteudo:
        return {"status": "ignorado_sem_conteudo"}

    telefone = _normalizar_telefone_evolution(remote_jid)
    timestamp_unix = data.get("messageTimestamp")
    timestamp = (
        datetime.fromtimestamp(timestamp_unix, tz=timezone.utc).isoformat()
        if timestamp_unix
        else datetime.now(timezone.utc).isoformat()
    )

    payload = {
        "telefone_remetente": telefone,
        "instancia_evolution_id": instance,
        "conteudo": conteudo.strip(),
        "timestamp_whatsapp": timestamp,
    }

    celery_app.send_task(
        "app.tasks.processar_resposta_recebida",
        args=[payload],
        queue="celery",
    )

    logger.info(f"Resposta enfileirada: {telefone}")
    return {"status": "enfileirado", "telefone": telefone}


async def _processar_connection_update(data: dict, instance: str) -> dict:
    estado = data.get("state") or data.get("status")
    logger.warning(f"Conexao chip {instance}: {estado}")

    if estado in ("close", "DISCONNECTED"):
        logger.error(f"Chip {instance} desconectou!")
        celery_app.send_task(
            "app.tasks.processar_chip_desconectado",
            args=[instance],
            queue="celery",
        )

    return {"status": "ok"}
