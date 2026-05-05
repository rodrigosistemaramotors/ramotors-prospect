"""
Loop de envios - script standalone (nao-Celery).
Roda como processo Python em container dedicado.
"""
import time
import random
import signal
import sys
from loguru import logger
from app.api_client import BackendClient
from app.whatsapp.evolution_client import EvolutionClient
from app.config import settings

_running = True

def _shutdown_handler(signum, frame):
    global _running
    logger.info(f"Sinal {signum} recebido, parando apos proxima iteracao...")
    _running = False

signal.signal(signal.SIGTERM, _shutdown_handler)
signal.signal(signal.SIGINT, _shutdown_handler)


def main():
    backend = BackendClient()
    evolution = EvolutionClient()
    logger.info("Loop de envios iniciado (standalone)")

    while _running:
        try:
            pendente = backend.proxima_pendente()
            if not pendente:
                # Polling mais rapido: 15s (era 60s)
                for _ in range(15):
                    if not _running:
                        break
                    time.sleep(1)
                continue

            mensagem_id = pendente["mensagem_id"]
            conversa_id = pendente["conversa_id"]
            is_inicial = pendente.get("is_inicial", True)

            if is_inicial:
                delay = random.uniform(
                    settings.delay_envio_inicial_min,
                    settings.delay_envio_inicial_max,
                )
                tipo = "inicial"
            else:
                delay = random.uniform(
                    settings.delay_resposta_min,
                    settings.delay_resposta_max,
                )
                tipo = "resposta"
            logger.info(
                f"Enviando msg {mensagem_id} (conversa {conversa_id}, {tipo}) em {delay:.0f}s"
            )
            slept = 0.0
            while slept < delay and _running:
                step = min(1.0, delay - slept)
                time.sleep(step)
                slept += step
            if not _running:
                break

            sucesso = evolution.enviar_texto(
                instance_id=pendente["instancia_evolution_id"],
                telefone=pendente["telefone_destino"],
                texto=pendente["mensagem"],
            )
            if sucesso:
                backend.marcar_enviada(mensagem_id)
                logger.success(f"Msg {mensagem_id} enviada")
            else:
                backend.marcar_falha(mensagem_id)
                logger.error(f"Msg {mensagem_id} falhou")

        except Exception as e:
            logger.exception(f"Erro no loop de envio: {e}")
            for _ in range(30):
                if not _running:
                    break
                time.sleep(1)

    logger.info("Loop de envios encerrado")
    sys.exit(0)


if __name__ == "__main__":
    main()
