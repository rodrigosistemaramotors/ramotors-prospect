from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery(
    "ramotors_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks"],
)

celery_app.conf.timezone = settings.timezone_str
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.broker_connection_retry_on_startup = True
celery_app.conf.task_default_queue = "celery"

celery_app.conf.beat_schedule = {
    "coleta-horaria": {
        "task": "app.tasks.executar_coleta_completa",
        "schedule": crontab(minute=0, hour="7-20"),
        "options": {"expires": 3000},
    },
    "gerar-mensagens": {
        "task": "app.tasks.gerar_mensagens_pendentes",
        "schedule": 120.0,
        "options": {"expires": 110},
    },
    "manutencao-diaria": {
        "task": "app.tasks.manutencao_diaria",
        "schedule": crontab(minute=5, hour=0),
        "options": {"expires": 3600},
    },
}
