"""
Compat shim - aliasa ZAPIClient como EvolutionClient.
Mantido por compatibilidade com imports existentes em tasks.py e loop_envios_runner.py.
A migracao para Z-API foi feita em zapi_client.py.
"""
from app.whatsapp.zapi_client import ZAPIClient as EvolutionClient

__all__ = ["EvolutionClient"]
