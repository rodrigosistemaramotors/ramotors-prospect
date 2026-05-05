"""
Cliente Z-API (https://z-api.io) - substituto da Evolution API.
Mantem a mesma interface (enviar_texto) para compatibilidade com o codigo
existente em tasks.py e loop_envios_runner.py.
"""
import httpx
from loguru import logger
from app.config import settings


class ZAPIClient:
    def __init__(self):
        self.instance_id = settings.zapi_instance_id
        self.token = settings.zapi_token
        self.client_token = settings.zapi_client_token  # opcional
        self.base = (
            f"https://api.z-api.io/instances/{self.instance_id}/token/{self.token}"
        )

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.client_token:
            h["Client-Token"] = self.client_token
        return h

    def _normalizar_numero(self, telefone: str) -> str:
        return telefone.replace("+", "").replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

    def enviar_texto(self, instance_id: str, telefone: str, texto: str) -> bool:
        """
        Envia mensagem de texto via Z-API.

        Args:
            instance_id: ignorado na Z-API single-instance (mantido para compat).
            telefone: numero destino, com ou sem +DDI.
            texto: conteudo da mensagem.

        Returns:
            True se enviada com sucesso, False caso contrario.
        """
        numero = self._normalizar_numero(telefone)
        try:
            with httpx.Client(timeout=30.0) as c:
                r = c.post(
                    f"{self.base}/send-text",
                    headers=self._headers(),
                    json={
                        "phone": numero,
                        "message": texto,
                        "delayMessage": 2,
                    },
                )
                r.raise_for_status()
                data = r.json()
                if data.get("id") or data.get("zaapId") or data.get("messageId"):
                    return True
                logger.warning(f"Z-API resposta sem id de mensagem: {data}")
                return True  # alguns endpoints retornam 200 sem id
        except httpx.HTTPStatusError as e:
            try:
                detalhes = e.response.json()
            except Exception:
                detalhes = e.response.text
            logger.error(f"Z-API HTTP {e.response.status_code}: {detalhes}")
            return False
        except httpx.HTTPError as e:
            logger.error(f"Falha envio Z-API: {e}")
            return False

    def status(self) -> dict:
        """Consulta estado da instancia (debug)."""
        try:
            with httpx.Client(timeout=10.0) as c:
                r = c.get(f"{self.base}/status", headers=self._headers())
                r.raise_for_status()
                return r.json()
        except httpx.HTTPError as e:
            logger.error(f"Z-API status falhou: {e}")
            return {"connected": False, "erro": str(e)}
