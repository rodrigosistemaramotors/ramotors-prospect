import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.config import settings

RETRY_KWARGS = dict(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=2, max=20),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    reraise=True,
)

class BackendClient:
    def __init__(self):
        self.base = settings.backend_url.rstrip("/")
        self.headers = {"X-Worker-Key": settings.worker_api_key}
        self.timeout = 90.0

    @retry(**RETRY_KWARGS)
    def enviar_lote_anuncios(self, anuncios: list[dict]) -> dict:
        with httpx.Client(timeout=self.timeout) as c:
            r = c.post(
                f"{self.base}/anuncios/lote",
                json={"anuncios": anuncios},
                headers=self.headers,
            )
            r.raise_for_status()
            return r.json()

    @retry(**RETRY_KWARGS)
    def gerar_mensagens_pendentes(self, limite: int = 5) -> dict:
        with httpx.Client(timeout=self.timeout) as c:
            r = c.post(
                f"{self.base}/conversas/gerar-mensagens-pendentes",
                params={"limite": limite},
                headers=self.headers,
            )
            r.raise_for_status()
            return r.json()

    @retry(**RETRY_KWARGS)
    def proxima_pendente(self) -> dict | None:
        with httpx.Client(timeout=self.timeout) as c:
            r = c.get(
                f"{self.base}/conversas/proxima-pendente",
                headers=self.headers,
            )
            r.raise_for_status()
            data = r.json()
            return data if data else None

    @retry(**RETRY_KWARGS)
    def marcar_enviada(self, mensagem_id: int):
        with httpx.Client(timeout=self.timeout) as c:
            r = c.post(
                f"{self.base}/conversas/mensagens/{mensagem_id}/marcar-enviada",
                headers=self.headers,
            )
            r.raise_for_status()

    @retry(**RETRY_KWARGS)
    def marcar_falha(self, mensagem_id: int):
        with httpx.Client(timeout=self.timeout) as c:
            r = c.post(
                f"{self.base}/conversas/mensagens/{mensagem_id}/marcar-falha",
                headers=self.headers,
            )
            r.raise_for_status()

    @retry(**RETRY_KWARGS)
    def reportar_resposta(self, payload: dict) -> dict:
        with httpx.Client(timeout=self.timeout) as c:
            r = c.post(
                f"{self.base}/conversas/mensagem-recebida",
                json=payload,
                headers=self.headers,
            )
            r.raise_for_status()
            return r.json()

    @retry(**RETRY_KWARGS)
    def pausar_instancia_por_evolution_id(self, evolution_id: str):
        with httpx.Client(timeout=self.timeout) as c:
            r = c.post(
                f"{self.base}/instancias-whatsapp/por-evolution-id/{evolution_id}/pausar",
                headers=self.headers,
            )
            r.raise_for_status()
