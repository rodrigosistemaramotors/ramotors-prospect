import json
import httpx
from loguru import logger
from app.config import settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

PROMPT_MENSAGEM_INICIAL = """Voce e um consultor da RA MOTORS, empresa de Cuiaba-MT especializada em
venda de veiculos por consignacao. Seu papel e fazer o primeiro contato
com proprietarios que anunciaram o carro em sites de classificados,
oferecendo nosso servico de consignacao como alternativa a venda direta.

REGRAS OBRIGATORIAS:
1. Mensagem curta: maximo 4 linhas, 320 caracteres.
2. Tom: educado, consultivo, brasileiro coloquial profissional.
3. Maximo 1 emoji discreto, opcional.
4. Mencione o modelo e cidade pra mostrar que nao e mensagem generica.
5. Faca UMA pergunta aberta no final.
6. NUNCA prometa preco, comissao ou prazo. Nao negocie nada.
7. NUNCA mencione "robo", "IA", "automacao", "sistema".
8. Apresente a empresa de forma humanizada - voce e uma pessoa.
9. Se houver primeiro nome do anunciante, use de forma natural.

Saida: apenas o texto da mensagem, sem aspas, sem comentarios."""

PROMPT_CLASSIFICAR = """Voce e um classificador de intencao em conversas de vendas da RA Motors.
Recebe a ultima mensagem de um proprietario de veiculo respondendo a
uma proposta de consignacao. Classifique a intencao e devolva JSON.

CATEGORIAS:
- INTERESSADO: clara abertura, faz pergunta sobre o servico
- TALVEZ: morna, ambigua, "depende", "nao sei", "talvez"
- PEDIU_INFO: pergunta especifica sobre comissao, prazo, processo
- RECUSOU: declina educadamente
- JA_VENDEU: informa que o carro ja foi vendido
- OPT_OUT: pede pra nao receber mais mensagens
- IGNOROU: vazia, sticker sem contexto, audio

Devolva APENAS JSON neste formato:
{
  "categoria": "INTERESSADO",
  "score_interesse": 75,
  "resumo": "frase curta",
  "proxima_acao_sugerida": "texto curto",
  "extrair_nome": null
}"""

PROMPT_RESPOSTA_CONTEXTUAL = """Voce continua a conversa como consultor da RA MOTORS. O proprietario
demonstrou interesse ou pediu informacao. Sua resposta deve:

1. Responder objetivamente o que foi perguntado.
2. Nao inventar dados (comissao, prazos) - se perguntado, dizer:
   "Os detalhes comerciais o vendedor responsavel vai te passar
    em detalhe - posso te conectar com ele agora?"
3. Conduzir para coleta de informacoes uteis ao vendedor humano.
4. Em ate 2-3 mensagens, propor escalar pro vendedor humano.
5. Tom: consultivo, sem pressao, sempre em PT-BR brasileiro.

Saida: apenas o texto da resposta. Sem aspas."""

class GroqClient:
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        }
        self.model = settings.groq_model

    @staticmethod
    def _extrair_json(raw: str) -> dict:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        inicio = raw.find("{")
        fim = raw.rfind("}")
        if inicio >= 0 and fim > inicio:
            try:
                return json.loads(raw[inicio:fim + 1])
            except json.JSONDecodeError:
                pass
        raise ValueError(f"JSON nao extraivel: {raw[:200]}")

    async def _chat(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.7,
        json_mode: bool = False,
    ) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(GROQ_URL, headers=self.headers, json=payload)
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"].strip()

    async def gerar_mensagem_inicial(self, anuncio: dict) -> str:
        user_prompt = f"""Anuncio captado:
- Modelo: {anuncio.get('modelo') or 'nao informado'}
- Ano: {anuncio.get('ano') or 'nao informado'}
- Preco anunciado: R$ {anuncio.get('preco') or 'nao informado'}
- Cidade: {anuncio.get('cidade') or 'Cuiaba'}
- Nome do anunciante: {anuncio.get('nome_vendedor') or 'nao informado'}
- Titulo original: {anuncio.get('titulo') or ''}

Gere a mensagem inicial."""
        return await self._chat(PROMPT_MENSAGEM_INICIAL, user_prompt, max_tokens=200)

    async def classificar_resposta(
        self,
        mensagem_inicial: str,
        historico: list[str],
        mensagem_recebida: str,
        contexto_veiculo: dict,
    ) -> dict:
        user_prompt = f"""Contexto:
- Veiculo: {contexto_veiculo.get('modelo')} {contexto_veiculo.get('ano')} - R$ {contexto_veiculo.get('preco')}
- Mensagem inicial enviada: "{mensagem_inicial}"
- Historico (ultimas 5): {historico}

Ultima resposta do proprietario:
"{mensagem_recebida}"

Classifique."""
        try:
            raw = await self._chat(
                PROMPT_CLASSIFICAR, user_prompt,
                max_tokens=300, temperature=0.2, json_mode=True,
            )
            return self._extrair_json(raw)
        except (ValueError, httpx.HTTPError) as e:
            logger.error(f"Falha classificacao Groq: {e}")
            return {
                "categoria": "TALVEZ",
                "score_interesse": 30,
                "resumo": "Resposta nao classificada por falha tecnica",
                "proxima_acao_sugerida": "Revisar manualmente",
                "extrair_nome": None,
            }

    async def gerar_resposta_contextual(
        self,
        historico: list[dict],
        mensagem_recebida: str,
        contexto_veiculo: dict,
    ) -> str:
        hist_str = "\n".join(
            f"{m['direcao']}: {m['conteudo']}" for m in historico[-5:]
        )
        user_prompt = f"""Veiculo: {contexto_veiculo.get('modelo')} {contexto_veiculo.get('ano')} - R$ {contexto_veiculo.get('preco')}

Historico:
{hist_str}

Nova mensagem do proprietario:
"{mensagem_recebida}"

Gere a proxima resposta."""
        return await self._chat(
            PROMPT_RESPOSTA_CONTEXTUAL, user_prompt, max_tokens=250
        )
