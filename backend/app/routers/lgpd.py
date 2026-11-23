"""Direitos do titular (LGPD): exportação dos dados e anonimização. Encarregado: administrador."""
import os

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .. import auditoria, servicos
from ..db import agora, get_db
from ..erros import ErroApi, nao_encontrado
from ..models import Anexo, Interacao, Lead, Tarefa, Usuario
from ..seguranca import admin

router = APIRouter(prefix="/lgpd", tags=["LGPD"])


def _lead(db: Session, lead_id: int) -> Lead:
    lead = db.get(Lead, lead_id)
    if not lead:
        raise nao_encontrado("Lead não encontrado.")
    return lead


@router.get("/titular")
def localizar_titular(email: str | None = None, telefone: str | None = None, u: Usuario = Depends(admin),
                      db: Session = Depends(get_db)):
    """Localiza todos os registros (inclusive excluídos) de um titular por e-mail/telefone."""
    from ..utils import normalizar_email, normalizar_telefone
    try:
        e = normalizar_email(email) if email else None
        t = normalizar_telefone(telefone) if telefone else None
    except ValueError as err:
        raise ErroApi(422, "validacao", str(err)) from err
    conds = []
    if e:
        conds.append(Lead.email == e)
    if t:
        conds.append(Lead.telefone == t)
    if not conds:
        return []
    from sqlalchemy import or_
    return [{"id": x.id, "nome": x.nome, "email": x.email, "telefone": x.telefone, "excluido": bool(x.excluido_em),
             "criado_em": x.criado_em} for x in db.scalars(select(Lead).where(or_(*conds)))]


@router.get("/leads/{lead_id}/exportar")
def exportar_titular(lead_id: int, request: Request, u: Usuario = Depends(admin), db: Session = Depends(get_db)):
    lead = _lead(db, lead_id)
    dados = auditoria.instantaneo(lead)
    dados.update({"origem": lead.origem.nome, "estagio": lead.estagio.nome, "responsavel": lead.responsavel.nome,
                  "etiquetas": [e.nome for e in lead.etiquetas]})
    interacoes = [{"tipo": i.tipo, "data_hora": i.data_hora.isoformat(), "resumo": i.resumo,
                   "resultado": i.resultado} for i in db.scalars(select(Interacao).where(Interacao.lead_id == lead.id)
                                                                  .order_by(Interacao.data_hora)).unique()]
    tarefas = [{"titulo": t.titulo, "vencimento": t.vencimento.isoformat(), "status": t.status}
               for t in db.scalars(select(Tarefa).where(Tarefa.lead_id == lead.id)).unique()]
    anexos = [{"nome": a.nome, "tamanho": a.tamanho} for a in db.scalars(select(Anexo).where(Anexo.lead_id == lead.id))]
    auditoria.registrar(db, u, "lead", lead.id, "lgpd_exportar", request=request)
    db.commit()
    return {"gerado_em": agora().isoformat(), "controlador": "Tenti", "titular": dados, "interacoes": interacoes,
            "tarefas": tarefas, "anexos": anexos}


@router.post("/leads/{lead_id}/anonimizar")
def anonimizar(lead_id: int, request: Request, u: Usuario = Depends(admin), db: Session = Depends(get_db)):
    """Remove dados pessoais de forma irreversível, mantendo números agregados (estágio, valores, datas)."""
    lead = _lead(db, lead_id)
    if lead.anonimizado_em:
        raise ErroApi(400, "ja_anonimizado", "Este lead já foi anonimizado.")
    for campo in ("email", "telefone", "empresa", "cargo", "cidade", "observacoes", "detalhe_perda",
                  "utm_source", "utm_medium", "utm_campaign", "interesse"):
        setattr(lead, campo, None)
    lead.nome = f"Titular anonimizado #{lead.id}"
    lead.anonimizado_em = agora()
    lead.etiquetas = []
    db.execute(update(Interacao).where(Interacao.lead_id == lead.id)
               .values(resumo="[conteúdo removido — LGPD]", resultado=None, dados=None))
    db.execute(update(Tarefa).where(Tarefa.lead_id == lead.id).values(titulo="[removido — LGPD]", descricao=None))
    for a in db.scalars(select(Anexo).where(Anexo.lead_id == lead.id)):
        try:
            os.remove(a.caminho)
        except OSError:
            pass
        db.delete(a)
    servicos.evento_sistema(db, lead, u, "Dados pessoais anonimizados a pedido do titular (LGPD).",
                            {"evento": "lgpd_anonimizar"})
    # Auditoria registra o fato, sem repetir os dados pessoais removidos.
    auditoria.registrar(db, u, "lead", lead.id, "lgpd_anonimizar", request=request)
    db.commit()
    return {"ok": True}
