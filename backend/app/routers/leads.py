from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .. import auditoria, servicos
from ..db import agora, get_db
from ..erros import ErroApi, invalido, nao_encontrado, proibido
from ..models import Anexo, Estagio, HistoricoEstagio, Interacao, Lead, Tarefa, Usuario
from ..schemas import (
    AtribuirEntrada,
    AtribuirLoteEntrada,
    LeadAtualizacao,
    LeadEntrada,
    MesclarEntrada,
    MudarEstagioEntrada,
)
from ..seguranca import escrita, gestao, ip_cliente, usuario_atual, ve_todos
from ..utils import normalizar_email, normalizar_telefone

router = APIRouter(prefix="/leads", tags=["Leads"])


def filtros_query(
    q: str | None = None,
    estagio_id: list[int] = Query(default=[]),
    origem_id: list[int] = Query(default=[]),
    responsavel_id: list[int] = Query(default=[]),
    etiqueta_id: list[int] = Query(default=[]),
    status: str | None = Query(default=None, pattern="^(aberto|ganho|perdido)$"),
    criado_de: date | None = None, criado_ate: date | None = None,
    contato_de: date | None = None, contato_ate: date | None = None,
    fechado_de: date | None = None, fechado_ate: date | None = None,
    valor_min: Decimal | None = None, valor_max: Decimal | None = None,
    parado: bool | None = None, sem_proxima_acao: bool | None = None, sem_contato: bool | None = None,
) -> servicos.FiltrosLead:
    return servicos.FiltrosLead(q=q, estagio_id=estagio_id, origem_id=origem_id, responsavel_id=responsavel_id,
                                etiqueta_id=etiqueta_id, status=status, criado_de=criado_de, criado_ate=criado_ate,
                                contato_de=contato_de, contato_ate=contato_ate, fechado_de=fechado_de,
                                fechado_ate=fechado_ate, valor_min=valor_min, valor_max=valor_max, parado=parado,
                                sem_proxima_acao=sem_proxima_acao, sem_contato=sem_contato)


@router.get("")
def listar(f: servicos.FiltrosLead = Depends(filtros_query), ordenar: str = "criado_em",
           direcao: str = Query("desc", pattern="^(asc|desc)$"), pagina: int = Query(1, ge=1),
           tamanho: int = Query(25, ge=1, le=200), u: Usuario = Depends(usuario_atual),
           db: Session = Depends(get_db)):
    base = servicos.aplicar_filtros(db, servicos.escopo_leads(u), f)
    total = db.scalar(select(func.count()).select_from(base.with_only_columns(Lead.id).subquery()))
    col = servicos.ORDENACOES.get(ordenar, Lead.criado_em)
    ordem = col.asc().nulls_last() if direcao == "asc" else col.desc().nulls_last()
    itens = list(db.scalars(base.order_by(ordem, Lead.id.desc()).offset((pagina - 1) * tamanho).limit(tamanho))
                 .unique())
    return {"itens": servicos.enriquecer(db, itens), "total": total, "pagina": pagina, "tamanho": tamanho}


@router.get("/kanban")
def kanban(f: servicos.FiltrosLead = Depends(filtros_query), limite: int = Query(50, ge=1, le=200),
           u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    """Colunas do quadro: estágios ativos na ordem, com total e os primeiros N leads de cada um."""
    estagios = list(db.scalars(select(Estagio).where(Estagio.ativo).order_by(Estagio.ordem)))
    colunas = []
    for e in estagios:
        base = servicos.aplicar_filtros(db, servicos.escopo_leads(u), f).where(Lead.estagio_id == e.id)
        total = db.scalar(select(func.count()).select_from(base.with_only_columns(Lead.id).subquery()))
        soma = db.scalar(select(func.coalesce(func.sum(base.with_only_columns(Lead.valor_estimado).subquery()
                                                       .c.valor_estimado), 0)))
        ordem = Lead.fechado_em.desc() if e.tipo != "aberto" else Lead.estagio_desde.asc()
        leads = list(db.scalars(base.order_by(ordem, Lead.id).limit(limite)).unique())
        colunas.append({"estagio": {"id": e.id, "nome": e.nome, "tipo": e.tipo, "ordem": e.ordem, "cor": e.cor},
                        "total": total, "valor": float(soma or 0), "leads": servicos.enriquecer(db, leads)})
    return {"colunas": colunas}


@router.get("/duplicados")
def verificar_duplicados(email: str | None = None, telefone: str | None = None, ignorar_id: int | None = None,
                         u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    """Checagem em tempo real enquanto o usuário preenche o formulário."""
    try:
        e = normalizar_email(email) if email else None
        t = normalizar_telefone(telefone) if telefone else None
    except ValueError:
        return {"duplicados": []}
    dup = servicos.buscar_duplicados(db, e, t, ignorar_id)
    return servicos.erro_duplicado(dup, u).detalhes if dup else {"duplicados": []}


@router.post("", status_code=201)
def criar(dados: LeadEntrada, request: Request, u: Usuario = Depends(escrita), db: Session = Depends(get_db)):
    lead = servicos.criar_lead(db, dados.model_dump(), u, ip_cliente(request))
    db.commit()
    return servicos.enriquecer(db, [lead])[0]


@router.get("/{lead_id}")
def obter(lead_id: int, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    return servicos.enriquecer(db, [servicos.obter_lead(db, lead_id, u)])[0]


@router.patch("/{lead_id}")
def atualizar(lead_id: int, dados: LeadAtualizacao, request: Request, u: Usuario = Depends(escrita),
              db: Session = Depends(get_db)):
    lead = servicos.obter_lead(db, lead_id, u, editar=True)
    if lead.anonimizado_em:
        raise ErroApi(400, "anonimizado", "Lead anonimizado não pode ser editado.")
    servicos.atualizar_lead(db, lead, dados.model_dump(exclude_unset=True), u, ip_cliente(request))
    db.commit()
    db.refresh(lead)
    return servicos.enriquecer(db, [lead])[0]


@router.delete("/{lead_id}")
def excluir(lead_id: int, request: Request, u: Usuario = Depends(gestao), db: Session = Depends(get_db)):
    """Exclusão lógica (o registro permanece para auditoria)."""
    lead = servicos.obter_lead(db, lead_id, u, editar=True)
    lead.excluido_em = agora()
    db.execute(update(Tarefa).where(Tarefa.lead_id == lead.id, Tarefa.status == "pendente")
               .values(status="cancelada"))
    auditoria.registrar(db, u, "lead", lead.id, "excluir", {"excluido_em": None},
                        {"excluido_em": lead.excluido_em.isoformat()}, request=request)
    db.commit()
    return {"ok": True}


@router.post("/{lead_id}/estagio")
def mudar_estagio(lead_id: int, dados: MudarEstagioEntrada, request: Request, u: Usuario = Depends(escrita),
                  db: Session = Depends(get_db)):
    lead = servicos.obter_lead(db, lead_id, u, editar=True)
    servicos.mudar_estagio(db, lead, dados.estagio_id, u, ip_cliente(request), dados.motivo_perda_id,
                           dados.detalhe_perda, dados.valor_fechado, dados.fechado_em)
    db.commit()
    db.refresh(lead)
    return servicos.enriquecer(db, [lead])[0]


@router.get("/{lead_id}/estagios")
def historico_estagios(lead_id: int, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    """Histórico de estágios com o tempo gasto em cada passagem."""
    servicos.obter_lead(db, lead_id, u)
    hist = list(db.scalars(select(HistoricoEstagio).where(HistoricoEstagio.lead_id == lead_id)
                           .order_by(HistoricoEstagio.data_hora, HistoricoEstagio.id)))
    nomes = {e.id: e.nome for e in db.scalars(select(Estagio))}
    usuarios = {x.id: x.nome for x in db.scalars(select(Usuario))}
    saida, total_por = [], {}
    for i, h in enumerate(hist):
        fim = hist[i + 1].data_hora if i + 1 < len(hist) else agora()
        seg = int((fim - h.data_hora).total_seconds())
        nome = nomes.get(h.para_estagio_id)
        total_por[nome] = total_por.get(nome, 0) + seg
        saida.append({"de": nomes.get(h.de_estagio_id), "para": nome, "data_hora": h.data_hora,
                      "usuario": usuarios.get(h.usuario_id), "segundos_no_estagio": seg,
                      "atual": i == len(hist) - 1})
    return {"passagens": saida, "tempo_por_estagio": total_por}


@router.post("/{lead_id}/atribuir")
def atribuir(lead_id: int, dados: AtribuirEntrada, request: Request, u: Usuario = Depends(gestao),
             db: Session = Depends(get_db)):
    lead = servicos.obter_lead(db, lead_id, u, editar=True)
    novo = _destino(db, dados.responsavel_id, dados.automatico, lead)
    servicos.atribuir(db, lead, novo, u, ip_cliente(request), "rodízio" if dados.automatico else "manual")
    db.commit()
    db.refresh(lead)
    return servicos.enriquecer(db, [lead])[0]


@router.post("/atribuir-lote")
def atribuir_lote(dados: AtribuirLoteEntrada, request: Request, u: Usuario = Depends(gestao),
                  db: Session = Depends(get_db)):
    ip = ip_cliente(request)
    feitos = 0
    for lid in dict.fromkeys(dados.lead_ids):
        lead = servicos.obter_lead(db, lid, u, editar=True)
        novo = _destino(db, dados.responsavel_id, dados.automatico, lead)
        servicos.atribuir(db, lead, novo, u, ip, "lote, rodízio" if dados.automatico else "lote")
        feitos += 1
    db.commit()
    return {"ok": True, "atualizados": feitos}


def _destino(db: Session, responsavel_id: int | None, automatico: bool, lead: Lead) -> Usuario:
    if automatico:
        return servicos.escolher_responsavel(db, lead.origem_id, lead.uf)
    if not responsavel_id:
        raise invalido("Escolha o novo responsável.", {"responsavel_id": "Obrigatório."})
    return servicos._validar_responsavel(db, responsavel_id)


@router.post("/mesclar")
def mesclar(dados: MesclarEntrada, request: Request, u: Usuario = Depends(escrita), db: Session = Depends(get_db)):
    """Move histórico, tarefas, anexos e etiquetas do secundário para o principal e exclui o secundário."""
    if dados.principal_id == dados.secundario_id:
        raise invalido("Escolha dois leads diferentes.")
    p = servicos.obter_lead(db, dados.principal_id, u, editar=True)
    s = servicos.obter_lead(db, dados.secundario_id, u, editar=True)
    if not ve_todos(u) and (p.responsavel_id != u.id or s.responsavel_id != u.id):
        raise proibido()
    antes = auditoria.instantaneo(p)
    for campo in servicos.CAMPOS_LEAD + ("utm_source", "utm_medium", "utm_campaign"):
        if getattr(p, campo) in (None, "") and getattr(s, campo) not in (None, ""):
            setattr(p, campo, getattr(s, campo))
    obs = [x for x in (p.observacoes, s.observacoes) if x]
    if len(obs) == 2 and obs[0] != obs[1]:
        p.observacoes = f"{obs[0]}\n\n[Mesclado de #{s.id}] {obs[1]}"
    p.etiquetas = list({e.id: e for e in [*p.etiquetas, *s.etiquetas]}.values())
    for modelo in (Interacao, Tarefa, Anexo, HistoricoEstagio):
        db.execute(update(modelo).where(modelo.lead_id == s.id).values(lead_id=p.id))
    for campo in ("ultimo_contato_em",):
        if getattr(s, campo) and (not getattr(p, campo) or getattr(s, campo) > getattr(p, campo)):
            setattr(p, campo, getattr(s, campo))
    if s.primeiro_contato_em and (not p.primeiro_contato_em or s.primeiro_contato_em < p.primeiro_contato_em):
        p.primeiro_contato_em = s.primeiro_contato_em
    s.excluido_em = agora()
    s.email, s.telefone = None, None
    servicos.evento_sistema(db, p, u, f"Lead #{s.id} ({s.nome}) mesclado neste registro.",
                            {"evento": "mesclagem", "secundario_id": s.id})
    db.flush()
    auditoria.registrar(db, u, "lead", p.id, "mesclar", antes, auditoria.instantaneo(p), request=request)
    auditoria.registrar(db, u, "lead", s.id, "excluir", None, {"mesclado_em": p.id}, request=request)
    db.commit()
    db.refresh(p)
    return servicos.enriquecer(db, [p])[0]


@router.post("/{lead_id}/restaurar")
def restaurar(lead_id: int, request: Request, u: Usuario = Depends(gestao), db: Session = Depends(get_db)):
    lead = db.get(Lead, lead_id)
    if not lead or lead.excluido_em is None:
        raise nao_encontrado()
    lead.excluido_em = None
    auditoria.registrar(db, u, "lead", lead.id, "restaurar", request=request)
    db.commit()
    return {"ok": True}
