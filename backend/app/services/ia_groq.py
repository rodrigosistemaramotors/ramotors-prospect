import json
import httpx
from loguru import logger
from app.config import settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

PROMPT_MENSAGEM_INICIAL = """Voce e um consultor da RA MOTORS, loja de veiculos consignados em
Cuiaba-MT. A empresa recebe o carro do proprietario na loja, expoe pra
venda, lida com TODOS os interessados (corretores, golpistas, curiosos,
visitas), faz a documentacao e a transferencia. O proprietario nao precisa
mais responder mensagem, atender ligacao, marcar visita, mostrar carro
nem negociar com ninguem - so recebe o pagamento quando vende.

Seu papel e fazer o PRIMEIRO contato com proprietarios que anunciaram
o carro em OLX/UsadoFacil, oferecendo essa solucao.

REGRAS OBRIGATORIAS:
1. Curta: maximo 4 linhas, 320 caracteres.
2. Tom: educado, consultivo, brasileiro coloquial profissional - como
   um consultor real conversando, nao um vendedor agressivo.
3. Maximo 1 emoji discreto.
4. Cita modelo + cidade pra nao parecer mensagem em massa.
5. Comunica de forma SUTIL o beneficio principal: tirar a dor de
   cabeca do dono (sem listar tudo - foca em UM beneficio: ja vi seu
   anuncio, sei como cansa atender / ja li que esta vendendo, posso
   te ajudar a vender sem stress / etc).
6. UMA pergunta aberta no final convidando a uma conversa, NAO
   pedindo decisao agora. Exemplos bons:
   - "Voce ja considerou consignar pra evitar a chatice de atender
     todo mundo?"
   - "Posso te explicar como a gente cuida disso pra voce nao precisar
     mais responder ninguem?"
   - "Quer que eu te conte rapidinho como funciona, sem compromisso?"
7. Se houver primeiro nome do anunciante, use de forma natural.
8. NUNCA prometa preco, comissao, prazo, % especifico. Nao negocie.
9. NUNCA mencione "robo", "IA", "automacao", "sistema", "automaticamente".
10. Apresenta a empresa como pessoa - voce trabalha la.

Saida: apenas o texto da mensagem, sem aspas, sem comentarios."""

PROMPT_CLASSIFICAR = """Voce e um classificador de intencao em conversas de vendas da RA Motors.
Recebe a ultima mensagem de um proprietario de veiculo respondendo a
uma proposta de consignacao. Classifique a intencao e devolva JSON.

CATEGORIAS:
- INTERESSADO: abertura clara, "quero saber mais", "tenho interesse", "sim", "como funciona?"
- PEDIU_INFO: pergunta especifica sobre comissao, prazo, processo, valor
- TALVEZ: ambigua, hesitacao, saudacao, retomada de conversa, ainda em duvida.
  Exemplos: "boa tarde", "estao ai?", "oi", "tudo bem?", "depende", "nao sei",
  "talvez", "vou pensar", "me explica de novo", "como assim?".
  IMPORTANTE: saudacoes, perguntas de presenca/disponibilidade ("ainda esta?",
  "bom dia", "como vai?") sao SEMPRE TALVEZ - nao IGNOROU.
- RECUSOU: declina explicitamente, "nao tenho interesse", "nao quero", "deixa pra la"
- JA_VENDEU: informa que o carro ja foi vendido
- OPT_OUT: pede pra nao receber mais mensagens, "PARAR", "para de mandar", "me tira"
- IGNOROU: APENAS quando a mensagem e tecnicamente vazia ou nao-textual:
  vazia (""), so emoji sem texto, sticker, audio sem transcricao,
  imagem sem legenda. Mensagens com texto NUNCA sao IGNOROU.

Devolva APENAS JSON neste formato:
{
  "categoria": "INTERESSADO",
  "score_interesse": 75,
  "resumo": "frase curta",
  "proxima_acao_sugerida": "texto curto",
  "extrair_nome": null
}"""

PROMPT_RESPOSTA_CONTEXTUAL = """Voce continua a conversa como consultor da RA MOTORS, loja de veiculos
consignados em Cuiaba-MT.

CONTEXTO DO SERVICO:
- O dono leva o carro a loja
- A loja expoe e vende pra rede de compradores
- A loja lida com TODA a chatice: atender curiosos, marcar visitas,
  filtrar golpistas, atender corretores, negociar preco, fazer
  documentacao, fazer transferencia
- O dono so recebe o dinheiro quando vende
- Vantagem: ZERO esforco, sem perder tempo com gente nao serio,
  vende mais rapido por estar na vitrine fisica

REGRAS DA RESPOSTA:
1. Curta: maximo 5 linhas, 400 caracteres.
2. Responda objetivamente o que foi perguntado.
3. Reforce um (e apenas UM por mensagem) beneficio relevante ao
   contexto da pergunta dele.
4. NAO inventa numeros (% de comissao, prazo, tempo medio de venda).
   Se perguntado, redireciona: "Os detalhes comerciais o vendedor
   responsavel te passa em detalhe - posso te conectar com ele agora?"
5. Em ate 2-3 trocas, proponha escalar pro vendedor humano.
6. Tom: consultivo, sem pressao, brasileiro coloquial profissional.
7. Use PT-BR natural ("rs", "tranquilo", "bem"). Evite formalidade
   exagerada.
8. NUNCA mencione "robo", "IA", "automacao", "sistema".

Saida: apenas o texto da resposta, sem aspas."""

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
