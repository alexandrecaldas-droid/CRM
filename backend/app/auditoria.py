from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import Request
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from .models import Auditoria, Usuario

_IGNORAR = {"senha_hash", "totp_secret", "chave_hash", "token_hash"}


def _json(v: Any) -> Any:
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def instantaneo(obj) -> dict:
    """Retrato das colunas de um objeto ORM (sem segredos), para antes/depois."""
    return {c.key: _json(getattr(obj, c.key)) for c in inspect(obj).mapper.column_attrs
            if c.key not in _IGNORAR}


def registrar(db: Session, usuario: Usuario | None, entidade: str, entidade_id: Any,
              acao: str, antes: dict | None = None, depois: dict | None = None,
              request: Request | None = None, ip: str | None = None) -> None:
    if request is not None and ip is None:
        from .seguranca import ip_cliente
        ip = ip_cliente(request)
    if antes and depois:  # guarda só o que mudou
        mudou = {k for k in set(antes) | set(depois) if antes.get(k) != depois.get(k)}
        antes = {k: antes.get(k) for k in mudou}
        depois = {k: depois.get(k) for k in mudou}
    db.add(Auditoria(usuario_id=usuario.id if usuario else None, entidade=entidade,
                     entidade_id=str(entidade_id) if entidade_id is not None else None,
                     acao=acao, antes=antes, depois=depois, ip=ip))
