"""Hash de senha (argon2), tokens de sessão e dependências de autorização."""
import hashlib
import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import agora, get_db
from .erros import ErroApi, proibido
from .models import Sessao, Usuario

_ph = PasswordHasher()


def hash_senha(senha: str) -> str:
    return _ph.hash(senha)


def verificar_senha(senha: str, hash_: str) -> bool:
    try:
        return _ph.verify(hash_, senha)
    except (VerifyMismatchError, InvalidHashError):
        return False


def validar_forca_senha(senha: str) -> None:
    if len(senha) < 8 or not any(c.isdigit() for c in senha) or not any(c.isalpha() for c in senha):
        raise ErroApi(422, "senha_fraca", "A senha deve ter ao menos 8 caracteres, com letras e números.")


def sha256(valor: str) -> str:
    return hashlib.sha256(valor.encode()).hexdigest()


def gerar_token() -> str:
    return secrets.token_urlsafe(32)


def criar_sessao(db: Session, usuario: Usuario, ip: str | None) -> str:
    token = gerar_token()
    db.add(Sessao(token_hash=sha256(token), usuario_id=usuario.id, ip=ip,
                  expira_em=agora() + timedelta(hours=get_settings().sessao_horas)))
    return token


def ip_cliente(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def usuario_atual(request: Request, db: Session = Depends(get_db)) -> Usuario:
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if not token:
        raise ErroApi(401, "nao_autenticado", "Faça login para continuar.")
    sessao = db.scalar(select(Sessao).where(Sessao.token_hash == sha256(token)))
    if not sessao or sessao.expira_em < agora() or not sessao.usuario.ativo:
        raise ErroApi(401, "sessao_expirada", "Sua sessão expirou. Entre novamente.")
    request.state.usuario = sessao.usuario
    request.state.sessao_id = sessao.id
    return sessao.usuario


def exigir(*perfis: str):
    def _dep(usuario: Usuario = Depends(usuario_atual)) -> Usuario:
        if usuario.perfil not in perfis:
            raise proibido()
        return usuario
    return _dep


admin = exigir("admin")
gestao = exigir("admin", "gestor")
escrita = exigir("admin", "gestor", "vendedor")


def ve_todos(u: Usuario) -> bool:
    return u.perfil in ("admin", "gestor", "leitura")
