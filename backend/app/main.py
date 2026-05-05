from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from loguru import logger
from app.routers import auth, anuncios, conversas, leads, instancias, opt_outs, metricas, webhook_zapi
from app.redis_client import close_redis

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("RA Motors Prospect API iniciando")
    yield
    logger.info("Encerrando - fechando conexoes")
    await close_redis()

app = FastAPI(title="RA Motors Prospect", version="2.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(anuncios.router)
app.include_router(conversas.router)
app.include_router(leads.router)
app.include_router(instancias.router)
app.include_router(opt_outs.router)
app.include_router(metricas.router)
app.include_router(webhook_zapi.router)

@app.get("/")
async def root():
    return {"sistema": "RA Motors Prospect", "status": "online"}

@app.get("/health")
async def health():
    return {"ok": True}
