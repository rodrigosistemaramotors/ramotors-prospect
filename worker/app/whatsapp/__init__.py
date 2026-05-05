from app.whatsapp.zapi_client import ZAPIClient

# Alias de compatibilidade. tasks.py e loop_envios_runner.py importam
# EvolutionClient; manter o nome evita refactor desnecessario.
EvolutionClient = ZAPIClient

__all__ = ["ZAPIClient", "EvolutionClient"]
