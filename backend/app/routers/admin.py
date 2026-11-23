"""Administração: usuários, origens, estágios, motivos, etiquetas, regras, chaves de API, parâmetros e auditoria."""
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import auditoria, parametros, servicos
from ..db import get_db
from ..erros import ErroApi, invalido, nao_encontrado
from ..models import (
    Auditoria,
    ChaveApi,
    Estagio,
    Etiqueta,
    HistoricoEstagio,
    Lead,
    ModeloEmail,
    MotivoPerda,
    Origem,
    RegraAtribuicao,
    Sessao,
    Usuario,
    lead_etiqueta,
)
from ..schemas import (
    ChaveApiEntrada,
    ChaveApiSaida,
    EstagioEntrada,
    EstagioSaida,
    EtiquetaEntrada,
    EtiquetaSaida,
    ModeloEmailEntrada,
    ModeloEmailSaida,
    MotivoEntrada,
    MotivoSaida,
    OrigemEntrada,
    OrigemSaida,
    ParametrosEntrada,
    RegraEntrada,
    RegraSaida,
    UsuarioAtualizacao,
    UsuarioEntrada,
    UsuarioSaida,
)
from ..seguranca import admin, gerar_token, hash_senha, sha256, usuario_atual, validar_forca_senha

router = APIRouter(tags=["Administração"])


def _commit(db: Session, msg: str = "Já existe um registro com este nome."):
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise ErroApi(409, "conflito", msg, {"nome": msg}) from e


# ---------------------------------------------------------------- usuários
@router.get("/usuarios", response_model=list[UsuarioSaida])
def usuarios(u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    """Todos os perfis podem listar (necessário para filtros e atribuição); e-mails são internos."""
    return list(db.scalars(select(Usuario).order_by(Usuario.ativo.desc(), Usuario.nome)))


@router.post("/usuarios", response_model=UsuarioSaida, status_code=201)
def criar_usuario(dados: UsuarioEntrada, request: Request, u: Usuario = Depends(admin), db: Session = Depends(get_db)):
    if not dados.senha:
        raise invalido("Defina uma senha inicial.", {"senha": "Obrigatória."})
    validar_forca_senha(dados.senha)
    novo = Usuario(nome=dados.nome.strip(), email=dados.email, perfil=dados.perfil, ativo=dados.ativo,
                   senha_hash=hash_senha(dados.senha), uf_regiao=dados.uf_regiao)
    db.add(novo)
    try:
        db.flush()
    except IntegrityError as e:
        db.rollback()
        raise ErroApi(409, "conflito", "Já existe usuário com este e-mail.", {"email": "E-mail já cadastrado."}) from e
    auditoria.registrar(db, u, "usuario", novo.id, "criar", depois=auditoria.instantaneo(novo), request=request)
    db.commit()
    return novo


@router.patch("/usuarios/{uid}", response_model=UsuarioSaida)
def atualizar_usuario(uid: int, dados: UsuarioAtualizacao, request: Request, u: Usuario = Depends(admin),
                      db: Session = Depends(get_db)):
    alvo = db.get(Usuario, uid)
    if not alvo:
        raise nao_encontrado()
    antes = auditoria.instantaneo(alvo)
    v = dados.model_dump(exclude_unset=True)
    if alvo.id == u.id and (v.get("ativo") is False or v.get("perfil", "admin") != "admin"):
        raise invalido("Você não pode desativar nem rebaixar a própria conta.")
    for k in ("nome", "email", "perfil", "ativo", "uf_regiao"):
        if k in v and v[k] is not None or k == "uf_regiao" and k in v:
            setattr(alvo, k, v[k])
    if v.get("senha"):
        validar_forca_senha(v["senha"])
        alvo.senha_hash = hash_senha(v["senha"])
    if v.get("desativar_2fa"):
        alvo.totp_ativo, alvo.totp_secret = False, None
    if alvo.ativo is False or v.get("senha"):
        db.query(Sessao).filter(Sessao.usuario_id == alvo.id).delete()
    try:
        db.flush()
    except IntegrityError as e:
        db.rollback()
        raise ErroApi(409, "conflito", "Já existe usuário com este e-mail.") from e
    auditoria.registrar(db, u, "usuario", alvo.id, "editar", antes, auditoria.instantaneo(alvo), request=request)
    db.commit()
    return alvo


# ---------------------------------------------------------------- cadastros simples
def _crud(caminho: str, modelo, entrada, saida, entidade: str, ordem, em_uso=None, pode_excluir=True):
    @router.get(f"/{caminho}", response_model=list[saida], name=f"listar_{entidade}")
    def listar(apenas_ativos: bool = False, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
        q = select(modelo).order_by(*ordem)
        campo_ativo = getattr(modelo, "ativo", None) or getattr(modelo, "ativa", None)
        if apenas_ativos and campo_ativo is not None:
            q = q.where(campo_ativo)
        return list(db.scalars(q))

    @router.post(f"/{caminho}", response_model=saida, status_code=201, name=f"criar_{entidade}")
    def criar(dados: entrada, request: Request, u: Usuario = Depends(admin), db: Session = Depends(get_db)):
        obj = modelo(**dados.model_dump())
        db.add(obj)
        try:
            db.flush()
        except IntegrityError as e:
            db.rollback()
            raise ErroApi(409, "conflito", "Já existe um registro com este nome.", {"nome": "Nome já usado."}) from e
        auditoria.registrar(db, u, entidade, obj.id, "criar", depois=auditoria.instantaneo(obj), request=request)
        _commit(db)
        return obj

    @router.put(f"/{caminho}/{{oid}}", response_model=saida, name=f"atualizar_{entidade}")
    def atualizar(oid: int, dados: entrada, request: Request, u: Usuario = Depends(admin),
                  db: Session = Depends(get_db)):
        obj = db.get(modelo, oid)
        if not obj:
            raise nao_encontrado()
        antes = auditoria.instantaneo(obj)
        for k, val in dados.model_dump().items():
            setattr(obj, k, val)
        if entidade == "estagio":
            _validar_funil(db)
        auditoria.registrar(db, u, entidade, obj.id, "editar", antes, auditoria.instantaneo(obj), request=request)
        _commit(db)
        return obj

    @router.delete(f"/{caminho}/{{oid}}", name=f"excluir_{entidade}")
    def excluir(oid: int, request: Request, u: Usuario = Depends(admin), db: Session = Depends(get_db)):
        obj = db.get(modelo, oid)
        if not obj:
            raise nao_encontrado()
        if em_uso is not None and db.scalar(select(exists().where(em_uso == oid))):
            raise ErroApi(409, "em_uso", "Este item está em uso e não pode ser excluído; desative-o.")
        if not pode_excluir:
            raise ErroApi(409, "em_uso", "Este item não pode ser excluído; desative-o.")
        auditoria.registrar(db, u, entidade, obj.id, "excluir", antes=auditoria.instantaneo(obj), request=request)
        db.delete(obj)
        if entidade == "estagio":
            _validar_funil(db)
        _commit(db, "Este item está em uso e não pode ser excluído; desative-o.")
        return {"ok": True}


def _validar_funil(db: Session):
    db.flush()
    tipos = {t for (t,) in db.execute(select(Estagio.tipo).where(Estagio.ativo))}
    if not {"aberto", "ganho", "perdido"} <= tipos:
        db.rollback()
        raise invalido("O funil precisa de ao menos um estágio ativo de cada tipo: aberto, ganho e perdido.")


_crud("origens", Origem, OrigemEntrada, OrigemSaida, "origem", (Origem.nome,), Lead.origem_id)
_crud("estagios", Estagio, EstagioEntrada, EstagioSaida, "estagio", (Estagio.ordem, Estagio.id),
      HistoricoEstagio.para_estagio_id)
_crud("motivos-perda", MotivoPerda, MotivoEntrada, MotivoSaida, "motivo_perda", (MotivoPerda.nome,),
      Lead.motivo_perda_id)
_crud("etiquetas", Etiqueta, EtiquetaEntrada, EtiquetaSaida, "etiqueta", (Etiqueta.nome,))
_crud("modelos-email", ModeloEmail, ModeloEmailEntrada, ModeloEmailSaida, "modelo_email", (ModeloEmail.nome,))
_crud("regras-atribuicao", RegraAtribuicao, RegraEntrada, RegraSaida, "regra_atribuicao",
      (RegraAtribuicao.prioridade, RegraAtribuicao.id))


@router.post("/estagios/reordenar")
def reordenar(ids: list[int], request: Request, u: Usuario = Depends(admin), db: Session = Depends(get_db)):
    for i, eid in enumerate(ids, start=1):
        e = db.get(Estagio, eid)
        if e:
            e.ordem = i
    auditoria.registrar(db, u, "estagio", None, "reordenar", depois={"ordem": ids}, request=request)
    db.commit()
    return {"ok": True}


@router.get("/etiquetas/uso")
def uso_etiquetas(u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    return dict(db.execute(select(lead_etiqueta.c.etiqueta_id, func.count()).group_by(lead_etiqueta.c.etiqueta_id))
                .all())


# ---------------------------------------------------------------- chaves de API (captura externa)
@router.get("/chaves-api", response_model=list[ChaveApiSaida])
def chaves(u: Usuario = Depends(admin), db: Session = Depends(get_db)):
    return list(db.scalars(select(ChaveApi).order_by(ChaveApi.criado_em.desc())))


@router.post("/chaves-api", status_code=201)
def criar_chave(dados: ChaveApiEntrada, request: Request, u: Usuario = Depends(admin), db: Session = Depends(get_db)):
    servicos._validar_origem(db, dados.origem_id)
    bruta = "lk_" + gerar_token()
    c = ChaveApi(nome=dados.nome.strip(), prefixo=bruta[:10], chave_hash=sha256(bruta), origem_id=dados.origem_id)
    db.add(c)
    db.flush()
    auditoria.registrar(db, u, "chave_api", c.id, "criar", depois={"nome": c.nome, "prefixo": c.prefixo},
                        request=request)
    db.commit()
    return {"id": c.id, "chave": bruta, "aviso": "Copie a chave agora; ela não será exibida novamente."}


@router.post("/chaves-api/{cid}/revogar")
def revogar_chave(cid: int, request: Request, u: Usuario = Depends(admin), db: Session = Depends(get_db)):
    c = db.get(ChaveApi, cid)
    if not c:
        raise nao_encontrado()
    c.ativa = False
    auditoria.registrar(db, u, "chave_api", c.id, "revogar", request=request)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- parâmetros
@router.get("/parametros")
def ler_parametros(u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    return parametros.todos(db)


@router.put("/parametros")
def salvar_parametros(dados: ParametrosEntrada, request: Request, u: Usuario = Depends(admin),
                      db: Session = Depends(get_db)):
    antes = parametros.todos(db)
    for k, v in dados.model_dump(exclude_none=True).items():
        parametros.definir(db, k, v)
    db.flush()
    auditoria.registrar(db, u, "parametros", None, "editar", antes, parametros.todos(db), request=request)
    db.commit()
    return parametros.todos(db)


# ---------------------------------------------------------------- auditoria (somente leitura)
@router.get("/auditoria")
def ler_auditoria(entidade: str | None = None, entidade_id: str | None = None, acao: str | None = None,
                  usuario_id: int | None = None, de: date | None = None, ate: date | None = None,
                  pagina: int = Query(1, ge=1), tamanho: int = Query(50, ge=1, le=200),
                  u: Usuario = Depends(admin), db: Session = Depends(get_db)):
    q = select(Auditoria)
    if entidade:
        q = q.where(Auditoria.entidade == entidade)
    if entidade_id:
        q = q.where(Auditoria.entidade_id == entidade_id)
    if acao:
        q = q.where(Auditoria.acao == acao)
    if usuario_id:
        q = q.where(Auditoria.usuario_id == usuario_id)
    if de:
        q = q.where(Auditoria.data_hora >= servicos.inicio_dia(de))
    if ate:
        q = q.where(Auditoria.data_hora < servicos.fim_dia(ate))
    total = db.scalar(select(func.count()).select_from(q.with_only_columns(Auditoria.id).subquery()))
    itens = db.scalars(q.order_by(Auditoria.data_hora.desc(), Auditoria.id.desc())
                       .offset((pagina - 1) * tamanho).limit(tamanho)).unique()
    return {"total": total, "pagina": pagina, "tamanho": tamanho, "itens": [
        {"id": a.id, "data_hora": a.data_hora, "usuario": a.usuario.nome if a.usuario else "Sistema",
         "entidade": a.entidade, "entidade_id": a.entidade_id, "acao": a.acao, "antes": a.antes,
         "depois": a.depois, "ip": a.ip} for a in itens]}
