from datetime import timedelta

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from .. import auditoria, servicos
from ..db import agora, get_db
from ..erros import nao_encontrado, proibido
from ..models import Lead, Notificacao, Tarefa, Usuario, VisaoSalva
from ..schemas import TarefaAtualizacao, TarefaEntrada, TarefaSaida, VisaoEntrada, VisaoSaida
from ..seguranca import escrita, ip_cliente, usuario_atual, ve_todos

router = APIRouter(tags=["Tarefas"])


def _escopo(u: Usuario):
    q = select(Tarefa).join(Lead, Tarefa.lead_id == Lead.id).where(Lead.excluido_em.is_(None))
    if not ve_todos(u):
        q = q.where(or_(Tarefa.responsavel_id == u.id, Lead.responsavel_id == u.id))
    return q


@router.get("/tarefas")
def listar(situacao: str | None = Query(None, pattern="^(atrasadas|hoje|proximas|pendentes|concluidas)$"),
           lead_id: int | None = None, responsavel_id: int | None = None, minhas: bool = False,
           pagina: int = Query(1, ge=1), tamanho: int = Query(50, ge=1, le=200),
           u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    q = _escopo(u)
    hoje = servicos.hoje_local()
    ini, fim, momento = servicos.inicio_dia(hoje), servicos.fim_dia(hoje), agora()
    if situacao == "atrasadas":
        q = q.where(Tarefa.status == "pendente", Tarefa.vencimento < momento)
    elif situacao == "hoje":
        q = q.where(Tarefa.status == "pendente", Tarefa.vencimento >= ini, Tarefa.vencimento < fim)
    elif situacao == "proximas":
        q = q.where(Tarefa.status == "pendente", Tarefa.vencimento >= fim)
    elif situacao == "pendentes":
        q = q.where(Tarefa.status == "pendente")
    elif situacao == "concluidas":
        q = q.where(Tarefa.status == "concluida")
    if lead_id:
        q = q.where(Tarefa.lead_id == lead_id)
    if minhas:
        q = q.where(Tarefa.responsavel_id == u.id)
    elif responsavel_id:
        q = q.where(Tarefa.responsavel_id == responsavel_id)
    total = db.scalar(select(func.count()).select_from(q.with_only_columns(Tarefa.id).subquery()))
    ordem = Tarefa.concluida_em.desc() if situacao == "concluidas" else Tarefa.vencimento.asc()
    itens = db.scalars(q.order_by(ordem, Tarefa.id).offset((pagina - 1) * tamanho).limit(tamanho)).unique()
    return {"itens": [TarefaSaida.model_validate(t) for t in itens], "total": total, "pagina": pagina,
            "tamanho": tamanho}


@router.get("/tarefas/resumo")
def resumo(u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    hoje = servicos.hoje_local()
    base = _escopo(u).where(Tarefa.status == "pendente", Tarefa.responsavel_id == u.id)

    def contar(q):
        return db.scalar(select(func.count()).select_from(q.with_only_columns(Tarefa.id).subquery()))
    return {"atrasadas": contar(base.where(Tarefa.vencimento < agora())),
            "hoje": contar(base.where(Tarefa.vencimento >= agora(), Tarefa.vencimento < servicos.fim_dia(hoje)))}


@router.post("/tarefas", response_model=TarefaSaida, status_code=201)
def criar(dados: TarefaEntrada, request: Request, u: Usuario = Depends(escrita), db: Session = Depends(get_db)):
    lead = servicos.obter_lead(db, dados.lead_id, u, editar=True)
    resp_id = dados.responsavel_id or lead.responsavel_id
    if u.perfil == "vendedor" and resp_id != u.id:
        raise proibido("Vendedores só criam tarefas para si mesmos.")
    resp = servicos._validar_responsavel(db, resp_id)
    t = Tarefa(lead_id=lead.id, responsavel_id=resp.id, titulo=dados.titulo.strip(), descricao=dados.descricao,
               vencimento=dados.vencimento, criado_por_id=u.id)
    db.add(t)
    db.flush()
    servicos.evento_sistema(db, lead, u, f"Tarefa criada: “{t.titulo}” para {resp.nome}.",
                            {"evento": "tarefa", "tarefa_id": t.id})
    auditoria.registrar(db, u, "tarefa", t.id, "criar", depois=auditoria.instantaneo(t), request=request)
    if resp.id != u.id:
        servicos.notificar(db, resp.id, "tarefa_atribuida", f"Nova tarefa para você: {t.titulo} ({lead.nome})",
                           lead.id, t.id)
    db.commit()
    db.refresh(t)
    return t


@router.patch("/tarefas/{tarefa_id}", response_model=TarefaSaida)
def atualizar(tarefa_id: int, dados: TarefaAtualizacao, request: Request, u: Usuario = Depends(escrita),
              db: Session = Depends(get_db)):
    t = db.scalar(_escopo(u).where(Tarefa.id == tarefa_id))
    if not t:
        raise nao_encontrado("Tarefa não encontrada.")
    antes = auditoria.instantaneo(t)
    valores = dados.model_dump(exclude_unset=True)
    if "responsavel_id" in valores and valores["responsavel_id"] != t.responsavel_id:
        if u.perfil == "vendedor":
            raise proibido("Somente gestor pode transferir tarefas.")
        t.responsavel_id = servicos._validar_responsavel(db, valores["responsavel_id"]).id
    for k in ("titulo", "descricao", "vencimento"):
        if k in valores and valores[k] is not None:
            setattr(t, k, valores[k])
    if "status" in valores and valores["status"] != t.status:
        t.status = valores["status"]
        t.concluida_em = agora() if t.status == "concluida" else None
        rot = {"concluida": "concluída", "cancelada": "cancelada", "pendente": "reaberta"}[t.status]
        servicos.evento_sistema(db, t.lead, u, f"Tarefa {rot}: “{t.titulo}”.", {"evento": "tarefa", "tarefa_id": t.id})
    db.flush()
    auditoria.registrar(db, u, "tarefa", t.id, "editar", antes, auditoria.instantaneo(t), ip=ip_cliente(request))
    db.commit()
    db.refresh(t)
    return t


# ---------------------------------------------------------------- notificações
@router.get("/notificacoes", tags=["Notificações"])
def notificacoes(apenas_nao_lidas: bool = False, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    q = select(Notificacao).where(Notificacao.usuario_id == u.id)
    if apenas_nao_lidas:
        q = q.where(Notificacao.lida.is_(False))
    itens = db.scalars(q.order_by(Notificacao.criado_em.desc()).limit(50))
    nao_lidas = db.scalar(select(func.count()).select_from(Notificacao)
                          .where(Notificacao.usuario_id == u.id, Notificacao.lida.is_(False)))
    return {"nao_lidas": nao_lidas, "itens": [
        {"id": n.id, "tipo": n.tipo, "mensagem": n.mensagem, "lead_id": n.lead_id, "lida": n.lida,
         "criado_em": n.criado_em} for n in itens]}


@router.post("/notificacoes/{nid}/lida", tags=["Notificações"])
def marcar_lida(nid: int, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    db.execute(update(Notificacao).where(Notificacao.id == nid, Notificacao.usuario_id == u.id).values(lida=True))
    db.commit()
    return {"ok": True}


@router.post("/notificacoes/lidas", tags=["Notificações"])
def marcar_todas(u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    db.execute(update(Notificacao).where(Notificacao.usuario_id == u.id).values(lida=True))
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- visões salvas
@router.get("/visoes", response_model=list[VisaoSaida], tags=["Visões salvas"])
def visoes(u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    return list(db.scalars(select(VisaoSalva).where(VisaoSalva.usuario_id == u.id).order_by(VisaoSalva.nome)))


@router.post("/visoes", response_model=VisaoSaida, status_code=201, tags=["Visões salvas"])
def criar_visao(dados: VisaoEntrada, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    v = VisaoSalva(usuario_id=u.id, nome=dados.nome.strip(), filtros=dados.filtros)
    db.add(v)
    db.commit()
    return v


@router.delete("/visoes/{vid}", tags=["Visões salvas"])
def excluir_visao(vid: int, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    v = db.get(VisaoSalva, vid)
    if not v or v.usuario_id != u.id:
        raise nao_encontrado()
    db.delete(v)
    db.commit()
    return {"ok": True}


def tarefas_para_lembrete(db: Session):
    """Usado pelo worker: pendentes que vencem hoje ou já venceram."""
    hoje = servicos.hoje_local()
    fim = servicos.fim_dia(hoje)
    return db.scalars(select(Tarefa).join(Lead, Tarefa.lead_id == Lead.id)
                      .where(Tarefa.status == "pendente", Tarefa.vencimento < fim, Lead.excluido_em.is_(None),
                             Tarefa.vencimento > agora() - timedelta(days=60))).unique()
