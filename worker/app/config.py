from pydantic_settings import BaseSettings, SettingsConfigDict

class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    redis_url: str
    backend_url: str
    worker_api_key: str

    # Z-API (https://z-api.io) - substitui Evolution API
    zapi_instance_id: str
    zapi_token: str
    zapi_client_token: str = ""  # opcional, vazio = sem header

    # Compat: deixados para nao quebrar leitura de .env antigo
    evolution_url: str = ""
    evolution_key: str = ""

    headless: bool = True
    rate_limit_segundos: int = 3
    max_anuncios_por_coleta: int = 30

    timezone_str: str = "America/Cuiaba"

    delay_envio_inicial_min: int = 30   # antes 60
    delay_envio_inicial_max: int = 90   # antes 180
    delay_resposta_min: int = 5         # antes 15
    delay_resposta_max: int = 15        # antes 45

settings = WorkerSettings()
