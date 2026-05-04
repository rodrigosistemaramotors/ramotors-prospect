from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, nullsfirst
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta
from app.database import get_db, SessionLocal
from app.deps import usuario_atual, require_worker
from app.models import (
    Conversa, EstadoConversa, Mensagem, DirecaoMensagem,
    Anuncio, StatusContato, InstanciaWhatsapp, OptOut, Lead, StatusFunil,
)
from app.schemas.conversa import (
    ConversaRead, MensagemRead, MensagemRecebidaInput,
    ProximaPendenteOutput, IntervencaoInput, EncerramentoInput,
)
from app.services.ia_groq import GroqClient
from app.utils.opt_out_detector import eh_opt_out

router = APIRouter(prefix="/conversas", tags=["conversas"])

@router.get("", response_model=list[ConversaRead])
async def listar(
    estado: EstadoConversa | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _u = Depends(usuario_atual),
):
    q = select(Conversa).order_by(Conversa.iniciada_em.desc())
    if estado:
        q = q.where(Conversa.estado == estado)
    result = await db.execute(q.limit(limit))
    return list(result.scalars())

@router.get("/{conversa_id}", response_model=ConversaRead)
async def detalhe(
    conversa_id: int,
    db: AsyncSession = Depends(get_db),
    _u = Depends(usuario_atual),
):
    c = await db.get(Conversa, conversa_id)
    if not c:
        raise HTTPException(404)
    return c

@router.get("/{conversa_id}/mensagens", response_model=list[MensagemRead])
async def historico(
    conversa_id: int,
    db: AsyncSession = Depends(get_db),
    _u = Depends(usuario_atual),
):
    result = await db.execute(
        select(Mensagem)
        .where(Mensagem.conversa_id == conversa_id)
        .order_by(Mensagem.criada_em)
    )
    return list(result.scalars())

@router.post("/gerar-mensagens-pendentes")
async def gerar_mensagens_pendentes(
    limite: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    _w = Depends(require_worker),
):
    q = await db.execute(
        select(Anuncio)
        .where(Anuncio.status_contato == StatusContato.PENDENTE)
        .where(Anuncio.telefone.isnot(None))
        .order_by(Anuncio.capturado_em)
        .limit(limite)
        .with_for_update(skip_locked=True)
    )
    anuncios_locked = list(q.scalars())

    if not anuncios_locked:
        return {"geradas": 0, "falhas": 0}

    anuncios_dados = [
        {
            "id": a.id,
            "modelo": a.modelo,
            "ano": a.ano,
            "preco": float(a.preco) if a.preco else None,
            "cidade": a.cidade,
            "nome_vendedor": a.nome_vendedor,
            "titulo": a.titulo,
            "telefone": a.telefone,
        }
        for a in anuncios_locked
    ]

    for a in anuncios_locked:
        a.status_contato = StatusContato.MENSAGEM_GERADA
    await db.commit()

    groq = GroqClient()
    geradas = 0
    falhas = 0

    for dados in anuncios_dados:
        async with SessionLocal() as session:
            try:
                inst_q = await session.execute(
                    select(InstanciaWhatsapp)
                    .where(InstanciaWhatsapp.status == "ATIVA")
                    .where(
                        InstanciaWhatsapp.msgs_enviadas_hoje
                        < InstanciaWhatsapp.limite_diario
                    )
                    .order_by(
                        InstanciaWhatsapp.msgs_enviadas_hoje,
                        nullsfirst(InstanciaWhatsapp.ultima_msg_em.asc()),
                    )
                    .limit(1)
                )
                instancia = inst_q.scalar_one_or_none()
                if not instancia:
                    anuncio = await session.get(Anuncio, dados["id"])
                    if anuncio:
                        anuncio.status_contato = StatusContato.PENDENTE
                    await session.commit()
                    falhas += 1
                    continue

                msg = await groq.gerar_mensagem_inicial(dados)

                conversa = Conversa(
                    anuncio_id=dados["id"],
                    instancia_id=instancia.id,
                    telefone=dados["telefone"],
                    estado=EstadoConversa.INICIADA,
                )
                session.add(conversa)
                await session.flush()

                mensagem = Mensagem(
                    conversa_id=conversa.id,
                    direcao=DirecaoMensagem.SAIDA,
                    conteudo=msg,
                )
                session.add(mensagem)
                await session.commit()
                geradas += 1

            except Exception:
                await session.rollback()
                async with SessionLocal() as rollback_session:
                    anuncio = await rollback_session.get(Anuncio, dados["id"])
                    if anuncio:
                        anuncio.status_contato = StatusContato.PENDENTE
                    await rollback_session.commit()
                falhas += 1

    return {"geradas": geradas, "falhas": falhas}

@router.get("/proxima-pendente", response_model=ProximaPendenteOutput | None)
async def proxima_pendente(
    db: AsyncSession = Depends(get_db),
    _w = Depends(require_worker),
):
    timeout_envio = datetime.now(timezone.utc) - timedelta(minutes=10)

    q = await db.execute(
        select(Mensagem, Conversa, InstanciaWhatsapp)
        .join(Conversa, Mensagem.conversa_id == Conversa.id)
        .join(InstanciaWhatsapp, Conversa.instancia_id == InstanciaWhatsapp.id)
        .where(Mensagem.direcao == DirecaoMensagem.SAIDA)
        .where(Mensagem.enviada_em.is_(None))
        .where(
            (Mensagem.entregue_para_envio_em.is_(None))
            | (Mensagem.entregue_para_envio_em < timeout_envio)
        )
        .where(Conversa.estado.in_([
            EstadoConversa.INICIADA,
            EstadoConversa.AGUARDANDO_RESPOSTA,
            EstadoConversa.EM_NEGOCIACAO,
            EstadoConversa.QUALIFICADA,
        ]))
        .where(InstanciaWhatsapp.status == "ATIVA")
        .order_by(Mensagem.criada_em)
        .limit(1)
        .with_for_update(of=Mensagem, skip_locked=True)
    )
    row = q.first()
    if not row:
        return None

    mensagem, conversa, instancia = row
    mensagem.entregue_para_envio_em = datetime.now(timezone.utc)
    await db.commit()

    return ProximaPendenteOutput(
        conversa_id=conversa.id,
        mensagem_id=mensagem.id,
        instancia_id=instancia.id,
        instancia_evolution_id=instancia.evolution_instance_id,
        telefone_destino=conversa.telefone,
        mensagem=mensagem.conteudo,
    )

@router.post("/mensagens/{mensagem_id}/marcar-enviada")
async def marcar_enviada(
    mensagem_id: int,
    db: AsyncSession = Depends(get_db),
    _w = Depends(require_worker),
):
    mensagem = await db.get(Mensagem, mensagem_id)
    if not mensagem:
        raise HTTPException(404)
    if mensagem.enviada_em:
        return {"ok": True, "ja_enviada": True}

    mensagem.enviada_em = datetime.now(timezone.utc)

    conversa = await db.get(Conversa, mensagem.conversa_id)
    conversa.estado = EstadoConversa.AGUARDANDO_RESPOSTA
    conversa.ultima_mensagem_em = datetime.now(timezone.utc)

    anuncio = await db.get(Anuncio, conversa.anuncio_id)
    anuncio.status_contato = StatusContato.ENVIADO

    instancia = await db.get(InstanciaWhatsapp, conversa.instancia_id)
    instancia.msgs_enviadas_hoje += 1
    instancia.msgs_enviadas_total += 1
    instancia.ultima_msg_em = datetime.now(timezone.utc)

    await db.commit()
    return {"ok": True}

@router.post("/mensagens/{mensagem_id}/marcar-falha")
async def marcar_falha(
    mensagem_id: int,
    db: AsyncSession = Depends(get_db),
    _w = Depends(require_worker),
):
    mensagem = await db.get(Mensagem, mensagem_id)
    if not mensagem:
        raise HTTPException(404)
    conversa = await db.get(Conversa, mensagem.conversa_id)
    anuncio = await db.get(Anuncio, conversa.anuncio_id)
    anuncio.status_contato = StatusContato.FALHOU
    conversa.estado = EstadoConversa.ENCERRADA_NEGATIVA
    conversa.encerrada_em = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True}

@router.post("/mensagem-recebida")
async def mensagem_recebida(
    payload: MensagemRecebidaInput,
    db: AsyncSession = Depends(get_db),
    _w = Depends(require_worker),
):
    q = await db.execute(
        select(Conversa)
        .where(Conversa.telefone == payload.telefone_remetente)
        .where(Conversa.estado.notin_([
            EstadoConversa.ENCERRADA_NEGATIVA,
            EstadoConversa.ENCERRADA_POSITIVA,
            EstadoConversa.OPT_OUT,
        ]))
        .order_by(Conversa.iniciada_em.desc())
        .limit(1)
    )
    conversa = q.scalar_one_or_none()
    if not conversa:
        return {"ignorado": "conversa_nao_encontrada"}

    msg_entrada = Mensagem(
        conversa_id=conversa.id,
        direcao=DirecaoMensagem.ENTRADA,
        conteudo=payload.conteudo,
        dados_extras={
            "whatsapp_timestamp": (
                payload.timestamp_whatsapp.isoformat()
                if payload.timestamp_whatsapp else None
            ),
        },
    )
    db.add(msg_entrada)

    if eh_opt_out(payload.conteudo):
        conversa.estado = EstadoConversa.OPT_OUT
        conversa.encerrada_em = datetime.now(timezone.utc)
        anuncio = await db.get(Anuncio, conversa.anuncio_id)
        anuncio.status_contato = StatusContato.OPT_OUT
        existe = await db.get(OptOut, conversa.telefone)
        if not existe:
            db.add(OptOut(
                telefone=conversa.telefone,
                motivo="Opt-out automatico por regex",
                origem="auto_regex",
            ))
        await db.commit()
        return {"acao": "opt_out", "conversa_id": conversa.id}

    hist_q = await db.execute(
        select(Mensagem)
        .where(Mensagem.conversa_id == conversa.id)
        .order_by(Mensagem.criada_em)
    )
    historico = list(hist_q.scalars())
    historico_dict = [
        {"direcao": m.direcao.value, "conteudo": m.conteudo} for m in historico
    ]

    anuncio = await db.get(Anuncio, conversa.anuncio_id)
    contexto = {
        "modelo": anuncio.modelo,
        "ano": anuncio.ano,
        "preco": float(anuncio.preco) if anuncio.preco else None,
    }

    groq = GroqClient()
    msg_inicial = next(
        (m.conteudo for m in historico if m.direcao == DirecaoMensagem.SAIDA), ""
    )
    classificacao = await groq.classificar_resposta(
        msg_inicial,
        [m.conteudo for m in historico[-5:]],
        payload.conteudo,
        contexto,
    )

    msg_entrada.classificacao_ia = classificacao["categoria"]
    score = classificacao.get("score_interesse", 0)
    conversa.score_interesse = score

    categoria = classificacao["categoria"]
    proxima_resposta = None

    if categoria == "INTERESSADO":
        conversa.estado = EstadoConversa.QUALIFICADA
        anuncio.status_contato = StatusContato.RESPONDIDO
        lead_q = await db.execute(
            select(Lead).where(Lead.conversa_id == conversa.id)
        )
        if not lead_q.scalar_one_or_none():
            lead = Lead(
                conversa_id=conversa.id,
                anuncio_id=anuncio.id,
                score_interesse=score,
                nome=classificacao.get("extrair_nome"),
                telefone=conversa.telefone,
                resumo_ia=classificacao.get("resumo"),
                sugestao_abordagem=classificacao.get("proxima_acao_sugerida"),
                status_funil=StatusFunil.NOVO,
            )
            db.add(lead)
        proxima_resposta = await groq.gerar_resposta_contextual(
            historico_dict, payload.conteudo, contexto
        )
    elif categoria == "PEDIU_INFO":
        conversa.estado = EstadoConversa.EM_NEGOCIACAO
        proxima_resposta = await groq.gerar_resposta_contextual(
            historico_dict, payload.conteudo, contexto
        )
    elif categoria == "TALVEZ":
        conversa.estado = EstadoConversa.EM_NEGOCIACAO
        proxima_resposta = await groq.gerar_resposta_contextual(
            historico_dict, payload.conteudo, contexto
        )
    elif categoria == "RECUSOU":
        conversa.estado = EstadoConversa.ENCERRADA_NEGATIVA
        conversa.encerrada_em = datetime.now(timezone.utc)
        proxima_resposta = (
            "Sem problema! Obrigado pela atencao e boa sorte com a venda. "
            "Estamos por aqui se mudar de ideia."
        )
    elif categoria == "JA_VENDEU":
        conversa.estado = EstadoConversa.ENCERRADA_POSITIVA
        conversa.encerrada_em = datetime.now(timezone.utc)
        anuncio.status_contato = StatusContato.IGNORADO
        proxima_resposta = (
            "Que otima noticia! Parabens pela venda. Qualquer outro veiculo "
            "que pretender vender, pode contar com a gente."
        )
    elif categoria == "OPT_OUT":
        conversa.estado = EstadoConversa.OPT_OUT
        conversa.encerrada_em = datetime.now(timezone.utc)
        anuncio.status_contato = StatusContato.OPT_OUT
        existe = await db.get(OptOut, conversa.telefone)
        if not existe:
            db.add(OptOut(
                telefone=conversa.telefone,
                motivo="Opt-out via classificacao IA",
                origem="auto_ia",
            ))

    if proxima_resposta:
        db.add(Mensagem(
            conversa_id=conversa.id,
            direcao=DirecaoMensagem.SAIDA,
            conteudo=proxima_resposta,
        ))

    conversa.ultima_mensagem_em = datetime.now(timezone.utc)
    await db.commit()

    return {
        "categoria": categoria,
        "score": score,
        "proxima_resposta": proxima_resposta,
        "conversa_id": conversa.id,
    }

@router.post("/{conversa_id}/intervir")
async def intervir(
    conversa_id: int,
    payload: IntervencaoInput,
    db: AsyncSession = Depends(get_db),
    _u = Depends(usuario_atual),
):
    conversa = await db.get(Conversa, conversa_id)
    if not conversa:
        raise HTTPException(404)
    db.add(Mensagem(
        conversa_id=conversa.id,
        direcao=DirecaoMensagem.SAIDA,
        conteudo=payload.mensagem,
    ))
    conversa.estado = EstadoConversa.EM_NEGOCIACAO
    await db.commit()
    return {"ok": True}

@router.post("/{conversa_id}/encerrar")
async def encerrar(
    conversa_id: int,
    payload: EncerramentoInput,
    db: AsyncSession = Depends(get_db),
    _u = Depends(usuario_atual),
):
    conversa = await db.get(Conversa, conversa_id)
    if not conversa:
        raise HTTPException(404)
    conversa.estado = EstadoConversa.ENCERRADA_NEGATIVA
    conversa.encerrada_em = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True, "motivo": payload.motivo}
