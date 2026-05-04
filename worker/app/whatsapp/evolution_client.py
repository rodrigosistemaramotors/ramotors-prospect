import httpx
from loguru import logger
from app.config import settings

class EvolutionClient:
    def __init__(self):
        self.base = settings.evolution_url.rstrip("/")
        self.headers = {"apikey": settings.evolution_key}

    def enviar_texto(self, instance_id: str, telefone: str, texto: str) -> bool:
        numero_limpo = telefone.replace("+", "").replace(" ", "").replace("-", "")
        try:
            with httpx.Client(timeout=30.0) as c:
                r = c.post(
                    f"{self.base}/message/sendText/{instance_id}",
                    headers=self.headers,
                    json={
                        "number": numero_limpo,
                        "text": texto,
                        "delay": 1200,
                    },
                )
                r.raise_for_status()
                return True
        except httpx.HTTPError as e:
            logger.error(f"Falha envio Evolution: {e}")
            return False
