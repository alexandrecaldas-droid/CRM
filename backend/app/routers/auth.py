from datetime import timedelta

import pyotp
from fastapi import APIRouter, Depends, Request
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .. import auditoria, emailer
from ..config import get_settings
from ..db import agora, get_db
from ..erros import ErroApi
from ..models import ResetSenha, Sessao, TentativaLogin, Usuario
from ..schemas import (
    CodigoEntrada,
    LoginEntrada,
    RecuperarSenhaEntrada,
    RedefinirSenhaEntrada,
    TrocarSenhaEntrada,
    UsuarioSaida,
)
from ..seguranca import (
    criar_sessao,
    gerar_token,
    hash_senha,
    ip_cliente,
    sha256,
    usuario_atual,
    validar_forca_senha,
    verificar_senha,
)

router = APIRouter(prefix="/auth", tags=["Autenticação"])


def _bloqueado(db: Session, email: str, ip: str | None) -> bool:
    s = get_settings()
    desde = agora() - timedelta(minutes=s.login_janela_min)
    falhas = db.scalar(select(func.count()).select_from(TentativaLogin).where(
        TentativaLogin.email == email, TentativaLogin.sucesso.is_(False), TentativaLogin.data_hora >= desde))
    return falhas >= s.login_max_tentativas


@router.post("/login")
def login(dados: LoginEntrada, request: Request, db: Session = Depends(get_db)):
    email = dados.email.strip().lower()
    ip = ip_cliente(request)
    if _bloqueado(db, email, ip):
        raise ErroApi(429, "login_bloqueado",
                      "Muitas tentativas sem sucesso. Aguarde alguns minutos e tente novamente.")
    u = db.scalar(select(Usuario).where(Usuario.email == email))
    if not u or not u.ativo or not verificar_senha(dados.senha, u.senha_hash):
        db.add(TentativaLogin(email=email, ip=ip, sucesso=False))
        auditoria.registrar(db, u, "sessao", None, "login_falhou", depois={"email": email}, ip=ip)
        db.commit()
        raise ErroApi(401, "credenciais_invalidas", "E-mail ou senha incorretos.")
    if u.totp_ativo:
        if not dados.codigo_2fa:
            raise ErroApi(401, "2fa_requerido", "Informe o código do aplicativo autenticador.")
        if not pyotp.TOTP(u.totp_secret).verify(dados.codigo_2fa.strip(), valid_window=1):
            db.add(TentativaLogin(email=email, ip=ip, sucesso=False))
            db.commit()
            raise ErroApi(401, "2fa_invalido", "Código de verificação inválido.")
    token = criar_sessao(db, u, ip)
    u.ultimo_login_em = agora()
    db.add(TentativaLogin(email=email, ip=ip, sucesso=True))
    auditoria.registrar(db, u, "sessao", u.id, "login", ip=ip)
    db.commit()
    return {"token": token, "usuario": UsuarioSaida.model_validate(u)}


@router.post("/logout")
def logout(request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    db.execute(delete(Sessao).where(Sessao.id == request.state.sessao_id))
    auditoria.registrar(db, u, "sessao", u.id, "logout", request=request)
    db.commit()
    return {"ok": True}


@router.get("/me", response_model=UsuarioSaida)
def me(u: Usuario = Depends(usuario_atual)):
    return u


@router.post("/recuperar-senha")
def recuperar_senha(dados: RecuperarSenhaEntrada, request: Request, db: Session = Depends(get_db)):
    """Resposta sempre igual, exista ou não o e-mail (evita enumeração de usuários)."""
    u = db.scalar(select(Usuario).where(Usuario.email == dados.email.strip().lower(), Usuario.ativo))
    if u:
        token = gerar_token()
        db.add(ResetSenha(usuario_id=u.id, token_hash=sha256(token), expira_em=agora() + timedelta(hours=1)))
        link = f"{get_settings().app_url}/redefinir-senha?token={token}"
        emailer.enviar(u.email, "Redefinição de senha — Sistema de Leads",
                       f"Olá, {u.nome}.\n\nPara criar uma nova senha, acesse o link abaixo (válido por 1 hora):\n"
                       f"{link}\n\nSe você não pediu, ignore esta mensagem.")
        auditoria.registrar(db, u, "usuario", u.id, "recuperar_senha", request=request)
        db.commit()
    return {"ok": True, "mensagem": "Se o e-mail estiver cadastrado, você receberá um link para redefinir a senha."}


@router.post("/redefinir-senha")
def redefinir_senha(dados: RedefinirSenhaEntrada, request: Request, db: Session = Depends(get_db)):
    r = db.scalar(select(ResetSenha).where(ResetSenha.token_hash == sha256(dados.token)))
    if not r or r.usado_em or r.expira_em < agora():
        raise ErroApi(400, "token_invalido", "Link inválido ou expirado. Solicite um novo.")
    validar_forca_senha(dados.nova_senha)
    u = db.get(Usuario, r.usuario_id)
    u.senha_hash = hash_senha(dados.nova_senha)
    r.usado_em = agora()
    db.execute(delete(Sessao).where(Sessao.usuario_id == u.id))
    auditoria.registrar(db, u, "usuario", u.id, "redefinir_senha", request=request)
    db.commit()
    return {"ok": True}


@router.post("/trocar-senha")
def trocar_senha(dados: TrocarSenhaEntrada, request: Request, u: Usuario = Depends(usuario_atual),
                 db: Session = Depends(get_db)):
    if not verificar_senha(dados.senha_atual, u.senha_hash):
        raise ErroApi(400, "senha_incorreta", "Senha atual incorreta.", {"senha_atual": "Senha incorreta."})
    validar_forca_senha(dados.nova_senha)
    u.senha_hash = hash_senha(dados.nova_senha)
    auditoria.registrar(db, u, "usuario", u.id, "trocar_senha", request=request)
    db.commit()
    return {"ok": True}


@router.post("/2fa/configurar")
def configurar_2fa(u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    if u.totp_ativo:
        raise ErroApi(400, "2fa_ativo", "A verificação em duas etapas já está ativa.")
    u.totp_secret = pyotp.random_base32()
    db.commit()
    uri = pyotp.TOTP(u.totp_secret).provisioning_uri(name=u.email, issuer_name="Sistema de Leads")
    return {"segredo": u.totp_secret, "uri": uri}


@router.post("/2fa/ativar")
def ativar_2fa(dados: CodigoEntrada, request: Request, u: Usuario = Depends(usuario_atual),
               db: Session = Depends(get_db)):
    if not u.totp_secret or not pyotp.TOTP(u.totp_secret).verify(dados.codigo.strip(), valid_window=1):
        raise ErroApi(400, "2fa_invalido", "Código inválido. Confira o horário do celular e tente de novo.")
    u.totp_ativo = True
    auditoria.registrar(db, u, "usuario", u.id, "ativar_2fa", request=request)
    db.commit()
    return {"ok": True}


@router.post("/2fa/desativar")
def desativar_2fa(dados: CodigoEntrada, request: Request, u: Usuario = Depends(usuario_atual),
                  db: Session = Depends(get_db)):
    if not u.totp_ativo or not pyotp.TOTP(u.totp_secret).verify(dados.codigo.strip(), valid_window=1):
        raise ErroApi(400, "2fa_invalido", "Código inválido.")
    u.totp_ativo = False
    u.totp_secret = None
    auditoria.registrar(db, u, "usuario", u.id, "desativar_2fa", request=request)
    db.commit()
    return {"ok": True}
