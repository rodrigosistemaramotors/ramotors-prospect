"""
Cliente Z-API usado pelo backend pra mandar respostas diretas durante
o processamento de webhook (sem passar pelo loop-envios).
Reduz latencia de respostas de ~25s pra ~3-5s.
"""
import httpx
from loguru import logger
from app.config import settings


class BackendZAPIClient:
    def __init__(self):
        self.instance_id = settings.zapi_instance_id
        self.token = settings.zapi_token
        self.client_token = settings.zapi_client_token
        self.base = (
            f"https://api.z-api.io/instances/{self.instance_id}/token/{self.token}"
        )

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.client_token:
            h["Client-Token"] = self.client_token
        return h

    @staticmethod
    def _normalizar(telefone: str) -> str:
        n = telefone.replace("+", "").replace(" ", "").replace("-", "")
        return n.replace("(", "").replace(")", "")

    async def enviar_texto(self, telefone: str, texto: str) -> bool:
        if not self.instance_id or not self.token:
            logger.warning("Z-API nao configurada no backend - pulando envio direto")
            return False

        numero = self._normalizar(telefone)
        try:
            async with httpx.AsyncClient(timeout=15.0) as c:
                r = await c.post(
                    f"{self.base}/send-text",
                    headers=self._headers(),
                    json={
                        "phone": numero,
                        "message": texto,
                        "delayMessage": 1,
                    },
                )
                r.raise_for_status()
                data = r.json()
                if data.get("id") or data.get("zaapId") or data.get("messageId"):
                    return True
                logger.warning(f"Z-API resposta sem id: {data}")
                return True
        except httpx.HTTPStatusError as e:
            try:
                detalhes = e.response.json()
            except Exception:
                detalhes = e.response.text
            logger.error(f"Z-API HTTP {e.response.status_code}: {detalhes}")
            return False
        except httpx.HTTPError as e:
            logger.error(f"Falha envio direto Z-API: {e}")
            return False
