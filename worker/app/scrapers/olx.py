import re
import json
import hashlib
import asyncio
import random
from urllib.parse import urlparse, urlunparse
from playwright.async_api import async_playwright
from loguru import logger
from app.scrapers.base import BaseScraper
from app.config import settings

def normalizar_url(url: str) -> str:
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))

def normalizar_telefone(tel: str | None) -> str | None:
    if not tel:
        return None
    digitos = re.sub(r"\D", "", tel)
    if digitos.startswith("55") and len(digitos) >= 12:
        digitos = digitos[2:]
    if len(digitos) != 11:
        return None
    if digitos[2] != "9":
        return None
    try:
        ddd = int(digitos[:2])
        if ddd < 11 or ddd > 99:
            return None
    except ValueError:
        return None
    return "+55" + digitos

def calcular_hash(fonte: str, url: str, telefone: str | None) -> str:
    base = f"{fonte}:{normalizar_url(url)}:{telefone or ''}"
    return hashlib.sha256(base.encode()).hexdigest()

class OLXScraper(BaseScraper):
    fonte = "OLX"
    base_url = (
        "https://www.olx.com.br/autos-e-pecas/carros-vans-e-utilitarios/"
        "estado-mt/regiao-de-cuiaba-e-varzea-grande"
    )

    async def coletar(self) -> list[dict]:
        anuncios: list[dict] = []
        async with async_playwright() as p:
            ctx = await self._criar_contexto(p)
            try:
                page = await self._nova_pagina_stealth(ctx)
                await page.goto(f"{self.base_url}?sf=1", timeout=60000)
                await page.wait_for_selector(
                    '[data-testid="adcard"]', timeout=30000
                )
                cards = await page.locator('[data-testid="adcard"]').all()
                logger.info(f"OLX: {len(cards)} cards encontrados")

                urls_capturadas: list[str] = []
                for card in cards[:60]:
                    try:
                        link = await card.locator('a').first.get_attribute('href')
                        if link and link not in urls_capturadas:
                            urls_capturadas.append(link)
                    except Exception:
                        continue

                limite = settings.max_anuncios_por_coleta
                for url in urls_capturadas[:limite]:
                    try:
                        anuncio = await self._coletar_detalhe(ctx, url)
                        if anuncio:
                            anuncios.append(anuncio)
                        await asyncio.sleep(random.uniform(2.0, 5.0))
                    except Exception as e:
                        logger.warning(f"Erro detalhe {url}: {e}")
            except Exception as e:
                logger.error(f"Erro coleta OLX: {e}")
            finally:
                await ctx.close()
        return anuncios

    async def _coletar_detalhe(self, ctx, url: str) -> dict | None:
        page = await self._nova_pagina_stealth(ctx)
        try:
            await page.goto(url, timeout=45000, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(1.5, 3.5))

            try:
                if await page.locator('text="Loja"').count() > 0:
                    return None
            except Exception:
                pass

            json_ld_handles = await page.locator(
                'script[type="application/ld+json"]'
            ).all()
            dados_estruturados: dict = {}
            for h in json_ld_handles:
                try:
                    txt = await h.text_content()
                    if not txt:
                        continue
                    data = json.loads(txt)
                    if isinstance(data, dict) and data.get("@type") in (
                        "Product", "Vehicle", "Car"
                    ):
                        dados_estruturados = data
                        break
                except Exception:
                    pass

            titulo = dados_estruturados.get("name") or await page.title()

            preco = None
            offers = dados_estruturados.get("offers")
            if isinstance(offers, dict):
                preco = offers.get("price")
            elif isinstance(offers, list) and offers:
                preco = offers[0].get("price")

            telefone: str | None = None
            try:
                botoes_tel = page.locator('button:has-text("telefone")')
                if await botoes_tel.count() > 0:
                    await botoes_tel.first.click()
                    await asyncio.sleep(2)
                    page_text = await page.content()
                    match = re.search(
                        r"\(?(\d{2})\)?\s*9?\d{4}[\s-]?\d{4}", page_text
                    )
                    if match:
                        telefone = normalizar_telefone(match.group(0))
            except Exception:
                pass

            if not telefone:
                return None

            cidade = "Cuiaba"
            try:
                loc_loc = page.locator('[aria-label*="Localizacao"]').first
                if await loc_loc.count() > 0:
                    loc = await loc_loc.text_content()
                    if loc:
                        if "Varzea Grande" in loc or "VÃ¡rzea Grande" in loc:
                            cidade = "Varzea Grande"
                        elif "Cuiaba" in loc or "CuiabÃ¡" in loc:
                            cidade = "Cuiaba"
            except Exception:
                pass

            ano_match = re.search(r"\b(19|20)\d{2}\b", titulo or "")
            ano = int(ano_match.group(0)) if ano_match else None

            return {
                "fonte": "OLX",
                "url": url,
                "url_canonica": normalizar_url(url),
                "hash_unico": calcular_hash("OLX", url, telefone),
                "titulo": (titulo or "")[:500],
                "modelo": (titulo or "")[:120],
                "marca": None,
                "ano": ano,
                "preco": float(preco) if preco else None,
                "cidade": cidade,
                "telefone": telefone,
                "nome_vendedor": None,
                "vendedor_tipo": "PARTICULAR",
                "dados_extras": {
                    "json_ld_disponivel": bool(dados_estruturados),
                },
            }
        finally:
            await page.close()
