import asyncio
import random
import time
from loguru import logger
from app.celery_app import celery_app
from app.api_client import BackendClient
from app.whatsapp.evolution_client import EvolutionClient
from app.scrapers.olx import OLXScraper
from app.config import settings

@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    time_limit=900,
    soft_time_limit=840,
)
def executar_coleta_completa(self):
    logger.info("Iniciando coleta completa OLX")
    try:
        anuncios = asyncio.run(_coletar_olx())
        if not anuncios:
            logger.info("Nenhum anuncio coletado")
            return
        backend = BackendClient()
        resultado = backend.enviar_lote_anuncios(anuncios)
        logger.success(f"Coleta finalizada: {resultado}")
    except Exception as e:
        logger.exception(f"Erro coleta: {e}")
        raise self.retry(exc=e)

async def _coletar_olx() -> list[dict]:
    scraper = OLXScraper()
    return await scraper.coletar()

@celery_app.task(time_limit=300, soft_time_limit=240)
def gerar_mensagens_pendentes():
    try:
        backend = BackendClient()
        resultado = backend.gerar_mensagens_pendentes(limite=5)
        if resultado.get("geradas", 0) > 0:
            logger.info(f"Geracao: {resultado}")
    except Exception as e:
        logger.exception(f"Erro geracao: {e}")

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    time_limit=180,
    soft_time_limit=150,
)
def processar_resposta_recebida(self, payload: dict):
    backend = BackendClient()
    evolution = EvolutionClient()
    try:
        resultado = backend.reportar_resposta(payload)
        logger.info(f"Resposta processada: categoria={resultado.get('categoria')}")
        proxima = resultado.get("proxima_resposta")
        if proxima and payload.get("instancia_evolution_id"):
            delay = random.uniform(
                settings.delay_resposta_min,
                settings.delay_resposta_max,
            )
            logger.info(f"Respondendo em {delay:.0f}s")
            time.sleep(delay)
            evolution.enviar_texto(
                instance_id=payload["instancia_evolution_id"],
                telefone=payload["telefone_remetente"],
                texto=proxima,
            )
            logger.success(f"Resposta enviada para {payload['telefone_remetente']}")
    except Exception as e:
        logger.exception(f"Erro processar resposta: {e}")
        raise self.retry(exc=e)

@celery_app.task
def processar_chip_desconectado(instance_evolution_id: str):
    try:
        backend = BackendClient()
        backend.pausar_instancia_por_evolution_id(instance_evolution_id)
        logger.warning(f"Chip {instance_evolution_id} pausado no backend")
    except Exception as e:
        logger.exception(f"Falha ao pausar chip {instance_evolution_id}: {e}")

@celery_app.task
def manutencao_diaria():
    logger.info("Manutencao diaria - placeholder")
