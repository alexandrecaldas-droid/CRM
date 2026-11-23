"""Parâmetros configuráveis pelo administrador (tabela configuracao)."""
from sqlalchemy.orm import Session

from .models import Configuracao

PADROES = {
    "dias_lead_parado": 7,
    "atribuicao_automatica": True,  # rodízio quando o lead chega sem responsável
    "rodizio_ultimo_usuario_id": None,
    "notificar_por_email": True,
}


def obter(db: Session, chave: str):
    c = db.get(Configuracao, chave)
    return c.valor if c is not None else PADROES.get(chave)


def definir(db: Session, chave: str, valor) -> None:
    c = db.get(Configuracao, chave)
    if c is None:
        db.add(Configuracao(chave=chave, valor=valor))
    else:
        c.valor = valor


def todos(db: Session) -> dict:
    return {k: obter(db, k) for k in PADROES if k != "rodizio_ultimo_usuario_id"}
