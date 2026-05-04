import yaml
import random
from pathlib import Path
from abc import ABC, abstractmethod
from playwright.async_api import async_playwright, BrowserContext, Page
from playwright_stealth import stealth_async
from app.config import settings

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

def carregar_seletores() -> dict:
    import os
    override = os.environ.get("SELECTORS_PATH")
    if override:
        path = Path(override)
    else:
        path = Path(__file__).resolve().parent.parent.parent / "selectors.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

class BaseScraper(ABC):
    fonte: str
    base_url: str

    def __init__(self):
        self.seletores = carregar_seletores().get(self.fonte.lower(), {})

    @abstractmethod
    async def coletar(self) -> list[dict]: ...

    async def _criar_contexto(self, p) -> BrowserContext:
        browser = await p.chromium.launch(headless=settings.headless)
        ctx = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={
                "width": 1280 + random.randint(-100, 100),
                "height": 800 + random.randint(-50, 50),
            },
            locale="pt-BR",
            timezone_id="America/Cuiaba",
        )
        return ctx

    async def _nova_pagina_stealth(self, ctx: BrowserContext) -> Page:
        page = await ctx.new_page()
        await stealth_async(page)
        return page
