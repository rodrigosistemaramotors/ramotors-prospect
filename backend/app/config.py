from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_access_expires_minutes: int = 60 * 8
    jwt_refresh_expires_minutes: int = 60 * 24 * 7

    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"

    empresa_nome: str = "RA Motors"
    empresa_cidade: str = "Cuiaba-MT"
    janela_h_inicio: int = 7
    janela_h_fim: int = 20
    bloqueio_telefone_dias: int = 180

    worker_api_key: str

    # Z-API webhook security: o secret e enviado pela Z-API via query string
    # ?secret=... configurado no painel Z-API.
    zapi_webhook_secret: str = "trocar-pra-string-aleatoria-de-32-chars"

    # Z-API credenciais pro backend mandar resposta direta (bypass loop-envios)
    # Reduz latencia de ~25s pra ~3-5s.
    zapi_instance_id: str = ""
    zapi_token: str = ""
    zapi_client_token: str = ""

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalizar_database_url(cls, v: str) -> str:
        if not v:
            return v
        if v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        v = v.replace("sslmode=require", "ssl=require")
        v = v.replace("sslmode=verify-full", "ssl=require")
        import re
        v = re.sub(r"[&?]channel_binding=\w+", "", v)
        v = v.rstrip("?&")
        return v

settings = Settings()
