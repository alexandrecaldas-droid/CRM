"""Painel, relatórios e exportações. Todos os números usam o mesmo filtro da lista de leads,
para que o painel bata com a lista filtrada equivalente."""
import csv
import io
from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from .. import auditoria, servicos
from ..db import agora, get_db
from ..erros import invalido
from ..models import Estagio, HistoricoEstagio, Lead, MotivoPerda, Origem, Tarefa, Usuario
from ..seguranca import gestao, usuario_atual, ve_todos
from ..servicos import FiltrosLead, aplicar_filtros, escopo_leads
from .leads import filtros_query

router = APIRouter(tags=["Relatórios"])


def _periodo(de: date | None, ate: date | None) -> tuple[date, date]:
    ate = ate or servicos.hoje_local()
    de = de or (ate - timedelta(days=29))
    if de > ate:
        raise invalido("A data inicial deve ser anterior à final.")
    return de, ate


def _contar(db, q) -> int:
    return db.scalar(select(func.count()).select_from(q.with_only_columns(Lead.id).subquery())) or 0


def _somar(db, q, col) -> float:
    sub = q.with_only_columns(col.label("v")).subquery()
    return float(db.scalar(select(func.coalesce(func.sum(sub.c.v), 0))) or 0)


def _base(u: Usuario, responsavel_id: int | None):
    q = escopo_leads(u)
    if responsavel_id and ve_todos(u):
        q = q.where(Lead.responsavel_id == responsavel_id)
    return q


def _f(**kw) -> FiltrosLead:
    return FiltrosLead(**kw)


def _link(**kw) -> dict:
    return {k: (v.isoformat() if isinstance(v, date) else v) for k, v in kw.items() if v not in (None, [], False)}


@router.get("/relatorios/painel")
def painel(de: date | None = None, ate: date | None = None, responsavel_id: int | None = None,
           u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    de, ate = _periodo(de, ate)
    base = _base(u, responsavel_id)
    extra = {"responsavel_id": [responsavel_id]} if responsavel_id and ve_todos(u) else {}
    cohort = aplicar_filtros(db, base, _f(criado_de=de, criado_ate=ate))
    novos = _contar(db, cohort)

    estagios = list(db.scalars(select(Estagio).where(Estagio.ativo).order_by(Estagio.ordem)))
    por_estagio = [{"id": e.id, "nome": e.nome, "tipo": e.tipo, "cor": e.cor,
                    "total": _contar(db, aplicar_filtros(db, base, _f(estagio_id=[e.id]))),
                    "valor": _somar(db, aplicar_filtros(db, base, _f(estagio_id=[e.id])), Lead.valor_estimado),
                    "filtros": _link(estagio_id=[e.id], **extra)} for e in estagios]

    conversao = _conversao(db, cohort, estagios)
    ganhos_cohort = _contar(db, aplicar_filtros(db, base, _f(criado_de=de, criado_ate=ate, status="ganho")))
    perdidos_cohort = _contar(db, aplicar_filtros(db, base, _f(criado_de=de, criado_ate=ate, status="perdido")))

    pares = db.execute(cohort.with_only_columns(Lead.criado_em, Lead.primeiro_contato_em)).all()
    tempos = [(p - c).total_seconds() / 3600 for c, p in pares if p is not None and p >= c]
    sem_contato = sum(1 for _, p in pares if p is None)

    tarefas_q = select(func.count(Tarefa.id)).join(Lead, Tarefa.lead_id == Lead.id).where(
        Tarefa.status == "pendente", Tarefa.vencimento < agora(), Lead.excluido_em.is_(None))
    if not ve_todos(u):
        tarefas_q = tarefas_q.where(Tarefa.responsavel_id == u.id)
    elif responsavel_id:
        tarefas_q = tarefas_q.where(Tarefa.responsavel_id == responsavel_id)

    ganho_periodo = aplicar_filtros(db, base, _f(status="ganho", fechado_de=de, fechado_ate=ate))
    abertos = aplicar_filtros(db, base, _f(status="aberto"))
    return {
        "periodo": {"de": de, "ate": ate},
        "novos": {"total": novos, "filtros": _link(criado_de=de, criado_ate=ate, **extra)},
        "por_estagio": por_estagio,
        "conversao": {"por_estagio": conversao,
                      "geral": round(ganhos_cohort / novos * 100, 1) if novos else 0.0,
                      "ganhos": ganhos_cohort, "perdidos": perdidos_cohort, "base": novos},
        "primeiro_contato": {"media_horas": round(sum(tempos) / len(tempos), 1) if tempos else None,
                             "com_contato": len(tempos), "sem_contato": sem_contato,
                             "filtros_sem_contato": _link(criado_de=de, criado_ate=ate, sem_contato=True, **extra)},
        "tarefas_atrasadas": db.scalar(tarefas_q) or 0,
        "parados": {"total": _contar(db, aplicar_filtros(db, base, _f(parado=True))),
                    "filtros": _link(parado=True, **extra)},
        "sem_proxima_acao": {"total": _contar(db, aplicar_filtros(db, base, _f(sem_proxima_acao=True))),
                             "filtros": _link(sem_proxima_acao=True, **extra)},
        "valor_funil": {"total": _somar(db, abertos, Lead.valor_estimado), "quantidade": _contar(db, abertos),
                        "filtros": _link(status="aberto", **extra)},
        "valor_ganho": {"total": _somar(db, ganho_periodo, Lead.valor_fechado),
                        "quantidade": _contar(db, ganho_periodo),
                        "filtros": _link(status="ganho", fechado_de=de, fechado_ate=ate, **extra)},
    }


def _conversao(db: Session, cohort, estagios: list[Estagio]) -> list[dict]:
    """Para cada estágio (exceto perdido): quantos leads do período chegaram até ele ou além."""
    ids = cohort.with_only_columns(Lead.id).subquery()
    maximos = db.execute(select(HistoricoEstagio.lead_id, func.max(Estagio.ordem))
                         .join(Estagio, HistoricoEstagio.para_estagio_id == Estagio.id)
                         .where(HistoricoEstagio.lead_id.in_(select(ids.c.id)), Estagio.tipo != "perdido")
                         .group_by(HistoricoEstagio.lead_id)).all()
    ordens = [m for _, m in maximos]
    saida, anterior = [], None
    for e in [e for e in estagios if e.tipo != "perdido"]:
        chegaram = sum(1 for o in ordens if o >= e.ordem)
        taxa = round(chegaram / anterior * 100, 1) if anterior else (100.0 if chegaram else 0.0)
        saida.append({"id": e.id, "nome": e.nome, "chegaram": chegaram, "taxa_etapa": taxa})
        anterior = chegaram
    return saida


def _agrupar(db: Session, q, chave, nomes: dict) -> list[dict]:
    sub = q.with_only_columns(chave.label("k"), Estagio.tipo.label("tipo"), Lead.valor_fechado.label("vf"),
                              Lead.valor_estimado.label("ve")).subquery()
    linhas = db.execute(select(
        sub.c.k, func.count(),
        func.sum(case((sub.c.tipo == "aberto", 1), else_=0)),
        func.sum(case((sub.c.tipo == "ganho", 1), else_=0)),
        func.sum(case((sub.c.tipo == "perdido", 1), else_=0)),
        func.coalesce(func.sum(case((sub.c.tipo == "ganho", sub.c.vf), else_=0)), 0),
        func.coalesce(func.sum(case((sub.c.tipo == "aberto", sub.c.ve), else_=0)), 0),
    ).group_by(sub.c.k)).all()
    out = []
    for k, total, ab, ga, pe, vg, va in linhas:
        fechados = (ga or 0) + (pe or 0)
        out.append({"id": k, "nome": nomes.get(k, "—"), "total": total, "abertos": ab or 0, "ganhos": ga or 0,
                    "perdidos": pe or 0, "valor_ganho": float(vg or 0), "valor_aberto": float(va or 0),
                    "conversao": round((ga or 0) / total * 100, 1) if total else 0.0,
                    "taxa_ganho_fechados": round((ga or 0) / fechados * 100, 1) if fechados else None})
    return sorted(out, key=lambda x: -x["total"])


@router.get("/relatorios/origens")
def por_origem(de: date | None = None, ate: date | None = None, u: Usuario = Depends(usuario_atual),
               db: Session = Depends(get_db)):
    de, ate = _periodo(de, ate)
    q = aplicar_filtros(db, escopo_leads(u), _f(criado_de=de, criado_ate=ate))
    nomes = {o.id: o.nome for o in db.scalars(select(Origem))}
    linhas = _agrupar(db, q, Lead.origem_id, nomes)
    for r in linhas:
        r["filtros"] = _link(origem_id=[r["id"]], criado_de=de, criado_ate=ate)
    return {"periodo": {"de": de, "ate": ate}, "linhas": linhas}


@router.get("/relatorios/vendedores")
def por_vendedor(de: date | None = None, ate: date | None = None, u: Usuario = Depends(usuario_atual),
                 db: Session = Depends(get_db)):
    de, ate = _periodo(de, ate)
    q = aplicar_filtros(db, escopo_leads(u), _f(criado_de=de, criado_ate=ate))
    nomes = {x.id: x.nome for x in db.scalars(select(Usuario))}
    linhas = _agrupar(db, q, Lead.responsavel_id, nomes)
    tempos = defaultdict(list)
    for rid, c, p in db.execute(q.with_only_columns(Lead.responsavel_id, Lead.criado_em, Lead.primeiro_contato_em)):
        if p is not None and p >= c:
            tempos[rid].append((p - c).total_seconds() / 3600)
    atrasadas = dict(db.execute(select(Tarefa.responsavel_id, func.count()).join(Lead, Tarefa.lead_id == Lead.id)
                                .where(Tarefa.status == "pendente", Tarefa.vencimento < agora(),
                                       Lead.excluido_em.is_(None)).group_by(Tarefa.responsavel_id)).all())
    for r in linhas:
        t = tempos.get(r["id"])
        r["primeiro_contato_horas"] = round(sum(t) / len(t), 1) if t else None
        r["tarefas_atrasadas"] = atrasadas.get(r["id"], 0)
        r["filtros"] = _link(responsavel_id=[r["id"]], criado_de=de, criado_ate=ate)
    return {"periodo": {"de": de, "ate": ate}, "linhas": linhas}


@router.get("/relatorios/motivos-perda")
def por_motivo(de: date | None = None, ate: date | None = None, u: Usuario = Depends(usuario_atual),
               db: Session = Depends(get_db)):
    de, ate = _periodo(de, ate)
    q = aplicar_filtros(db, escopo_leads(u), _f(status="perdido", fechado_de=de, fechado_ate=ate))
    sub = q.with_only_columns(Lead.motivo_perda_id.label("m"), Lead.valor_estimado.label("v")).subquery()
    nomes = {m.id: m.nome for m in db.scalars(select(MotivoPerda))}
    linhas = db.execute(select(sub.c.m, func.count(), func.coalesce(func.sum(sub.c.v), 0)).group_by(sub.c.m)).all()
    total = sum(c for _, c, _ in linhas)
    return {"periodo": {"de": de, "ate": ate}, "total": total, "linhas": sorted([
        {"id": m, "nome": nomes.get(m, "Sem motivo"), "total": c, "valor_estimado": float(v or 0),
         "percentual": round(c / total * 100, 1) if total else 0} for m, c, v in linhas], key=lambda x: -x["total"])}


@router.get("/relatorios/funil")
def funil(de: date | None = None, ate: date | None = None, u: Usuario = Depends(usuario_atual),
          db: Session = Depends(get_db)):
    """Situação atual por estágio + tempo médio de permanência (passagens iniciadas no período)."""
    de, ate = _periodo(de, ate)
    estagios = list(db.scalars(select(Estagio).where(Estagio.ativo).order_by(Estagio.ordem)))
    base = escopo_leads(u)
    ids = base.with_only_columns(Lead.id).subquery()
    hist = db.execute(select(HistoricoEstagio.lead_id, HistoricoEstagio.para_estagio_id, HistoricoEstagio.data_hora)
                      .where(HistoricoEstagio.lead_id.in_(select(ids.c.id)))
                      .order_by(HistoricoEstagio.lead_id, HistoricoEstagio.data_hora, HistoricoEstagio.id)).all()
    duracoes = defaultdict(list)
    ini, fim = servicos.inicio_dia(de), servicos.fim_dia(ate)
    for i, (lid, est, quando) in enumerate(hist):
        if not (ini <= quando < fim):
            continue
        prox = hist[i + 1] if i + 1 < len(hist) and hist[i + 1][0] == lid else None
        if prox:
            duracoes[est].append((prox[2] - quando).total_seconds() / 86400)
    conv = _conversao(db, aplicar_filtros(db, base, _f(criado_de=de, criado_ate=ate)), estagios)
    conv_por = {c["id"]: c for c in conv}
    linhas = []
    for e in estagios:
        q = aplicar_filtros(db, base, _f(estagio_id=[e.id]))
        d = duracoes.get(e.id, [])
        linhas.append({"id": e.id, "nome": e.nome, "tipo": e.tipo, "cor": e.cor, "total": _contar(db, q),
                       "valor": _somar(db, q, Lead.valor_estimado),
                       "dias_medios": round(sum(d) / len(d), 1) if d else None,
                       "chegaram": conv_por.get(e.id, {}).get("chegaram"),
                       "taxa_etapa": conv_por.get(e.id, {}).get("taxa_etapa"),
                       "filtros": _link(estagio_id=[e.id])})
    return {"periodo": {"de": de, "ate": ate}, "linhas": linhas}


# ---------------------------------------------------------------- exportação
COLUNAS_LEAD = [
    ("id", "ID"), ("nome", "Nome"), ("email", "E-mail"), ("telefone", "Telefone"), ("empresa", "Empresa"),
    ("cargo", "Cargo"), ("cidade", "Cidade"), ("uf", "UF"), ("interesse", "Interesse"),
    ("valor_estimado", "Valor estimado"), ("origem", "Origem"), ("estagio", "Estágio"),
    ("responsavel", "Responsável"), ("motivo_perda", "Motivo da perda"), ("valor_fechado", "Valor fechado"),
    ("fechado_em", "Fechado em"), ("etiquetas", "Etiquetas"), ("utm_source", "UTM source"),
    ("utm_medium", "UTM medium"), ("utm_campaign", "UTM campaign"), ("criado_em", "Criado em"),
    ("ultimo_contato_em", "Último contato"), ("base_legal", "Base legal LGPD"),
]


def _fmt_data(d):
    return d.astimezone(servicos.TZ).strftime("%d/%m/%Y %H:%M") if d else ""


def _linhas_leads(db: Session, q) -> tuple[list[str], list[list]]:
    linhas = []
    for lead in db.scalars(q.order_by(Lead.criado_em.desc()).limit(100000)).unique():
        linhas.append([lead.id, lead.nome, lead.email or "", lead.telefone or "", lead.empresa or "",
                       lead.cargo or "", lead.cidade or "", lead.uf or "", lead.interesse or "",
                       float(lead.valor_estimado) if lead.valor_estimado is not None else "", lead.origem.nome,
                       lead.estagio.nome, lead.responsavel.nome, lead.motivo_perda.nome if lead.motivo_perda else "",
                       float(lead.valor_fechado) if lead.valor_fechado is not None else "", _fmt_data(lead.fechado_em),
                       ", ".join(e.nome for e in lead.etiquetas), lead.utm_source or "", lead.utm_medium or "",
                       lead.utm_campaign or "", _fmt_data(lead.criado_em), _fmt_data(lead.ultimo_contato_em),
                       lead.base_legal or ""])
    return [c[1] for c in COLUNAS_LEAD], linhas


def _tabela(relatorio: dict, colunas: list[tuple[str, str]]) -> tuple[list[str], list[list]]:
    return [c[1] for c in colunas], [[r.get(c[0], "") if r.get(c[0]) is not None else "" for c in colunas]
                                     for r in relatorio["linhas"]]


def arquivo(cab: list[str], linhas: list[list], formato: str, nome: str) -> Response:
    if formato == "xlsx":
        wb = Workbook()
        ws = wb.active
        ws.title = nome[:31]
        ws.append(cab)
        for c in ws[1]:
            c.font = Font(bold=True)
        for linha in linhas:
            ws.append(linha)
        ws.freeze_panes = "A2"
        buf = io.BytesIO()
        wb.save(buf)
        return Response(buf.getvalue(), headers={"Content-Disposition": f"attachment; filename={nome}.xlsx"},
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(cab)
    for linha in linhas:
        w.writerow([str(x).replace(".", ",") if isinstance(x, float) else x for x in linha])
    return Response(("﻿" + buf.getvalue()).encode(), media_type="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={nome}.csv"})


@router.get("/exportacoes")
def exportar(request: Request, tipo: str = Query("leads", pattern="^(leads|origens|vendedores|motivos|funil)$"),
             formato: str = Query("xlsx", pattern="^(csv|xlsx)$"), de: date | None = None, ate: date | None = None,
             f: servicos.FiltrosLead = Depends(filtros_query), u: Usuario = Depends(gestao),
             db: Session = Depends(get_db)):
    """Somente administrador e gestor exportam. Cada exportação fica registrada na auditoria."""
    if tipo == "leads":
        cab, linhas = _linhas_leads(db, aplicar_filtros(db, escopo_leads(u), f))
    elif tipo == "origens":
        cab, linhas = _tabela(por_origem(de, ate, u, db), [("nome", "Origem"), ("total", "Leads"),
                              ("abertos", "Abertos"),
                              ("ganhos", "Ganhos"), ("perdidos", "Perdidos"), ("conversao", "Conversão %"),
                              ("valor_ganho", "Valor ganho"), ("valor_aberto", "Valor em aberto")])
    elif tipo == "vendedores":
        cab, linhas = _tabela(por_vendedor(de, ate, u, db), [("nome", "Vendedor"), ("total", "Leads"),
                              ("abertos", "Abertos"), ("ganhos", "Ganhos"), ("perdidos", "Perdidos"),
                              ("conversao", "Conversão %"), ("valor_ganho", "Valor ganho"),
                              ("primeiro_contato_horas", "Horas até 1º contato"),
                              ("tarefas_atrasadas", "Tarefas atrasadas")])
    elif tipo == "motivos":
        cab, linhas = _tabela(por_motivo(de, ate, u, db), [("nome", "Motivo"), ("total", "Leads"),
                              ("percentual", "%"), ("valor_estimado", "Valor estimado perdido")])
    else:
        cab, linhas = _tabela(funil(de, ate, u, db), [("nome", "Estágio"), ("total", "Leads"), ("valor", "Valor"),
                              ("dias_medios", "Dias médios no estágio"), ("chegaram", "Chegaram (período)"),
                              ("taxa_etapa", "Conversão da etapa %")])
    auditoria.registrar(db, u, "exportacao", None, "exportar",
                        depois={"tipo": tipo, "formato": formato, "linhas": len(linhas),
                                "filtros": {k: str(v) for k, v in request.query_params.items()}}, request=request)
    db.commit()
    return arquivo(cab, linhas, formato, f"{tipo}_{servicos.hoje_local().isoformat()}")
