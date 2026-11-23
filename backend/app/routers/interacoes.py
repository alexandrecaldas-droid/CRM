import os
import re
import uuid

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import auditoria, emailer, servicos
from ..config import get_settings
from ..db import agora, get_db
from ..erros import ErroApi, invalido, nao_encontrado
from ..models import Anexo, Interacao, ModeloEmail, Usuario
from ..schemas import EnviarEmailEntrada, InteracaoEntrada, InteracaoSaida, ModeloEmailSaida
from ..seguranca import escrita, ip_cliente, usuario_atual

router = APIRouter(tags=["Interações"])

TIPOS_BLOQUEADOS = (".exe", ".bat", ".cmd", ".sh", ".js", ".msi", ".com", ".scr", ".ps1", ".html", ".htm", ".svg")


@router.get("/leads/{lead_id}/interacoes", response_model=list[InteracaoSaida])
def listar(lead_id: int, tipo: str | None = None, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    servicos.obter_lead(db, lead_id, u)
    q = select(Interacao).where(Interacao.lead_id == lead_id)
    if tipo:
        q = q.where(Interacao.tipo == tipo)
    return list(db.scalars(q.order_by(Interacao.data_hora.desc(), Interacao.id.desc())).unique())


@router.post("/leads/{lead_id}/interacoes", response_model=InteracaoSaida, status_code=201)
def criar(lead_id: int, dados: InteracaoEntrada, request: Request, u: Usuario = Depends(escrita),
          db: Session = Depends(get_db)):
    lead = servicos.obter_lead(db, lead_id, u, editar=True)
    quando = dados.data_hora or agora()
    if quando > agora():
        raise invalido("A data da interação não pode ser futura. Para algo futuro, crie uma tarefa.",
                       {"data_hora": "Data futura."})
    i = Interacao(lead_id=lead.id, usuario_id=u.id, tipo=dados.tipo, data_hora=quando,
                  resumo=dados.resumo.strip(), resultado=(dados.resultado or "").strip() or None)
    db.add(i)
    if dados.tipo != "nota":
        servicos.registrar_contato(lead, quando)
    db.flush()
    auditoria.registrar(db, u, "interacao", i.id, "criar", depois={"lead_id": lead.id, "tipo": i.tipo},
                        request=request)
    db.commit()
    db.refresh(i)
    return i


def _nome_seguro(nome: str) -> str:
    nome = os.path.basename(nome or "arquivo")
    return re.sub(r"[^\w.\- ()À-ú]", "_", nome)[:200] or "arquivo"


@router.post("/leads/{lead_id}/anexos", status_code=201)
async def enviar_anexo(lead_id: int, request: Request, arquivo: UploadFile = File(...),
                       interacao_id: int | None = None, u: Usuario = Depends(escrita), db: Session = Depends(get_db)):
    lead = servicos.obter_lead(db, lead_id, u, editar=True)
    s = get_settings()
    limite = s.max_upload_mb * 1024 * 1024
    nome = _nome_seguro(arquivo.filename)
    if nome.lower().endswith(TIPOS_BLOQUEADOS):
        raise invalido("Tipo de arquivo não permitido.", {"arquivo": "Tipo de arquivo não permitido."})
    if interacao_id:
        it = db.get(Interacao, interacao_id)
        if not it or it.lead_id != lead.id:
            raise nao_encontrado("Interação não encontrada.")
    conteudo = await arquivo.read(limite + 1)
    if len(conteudo) > limite:
        raise ErroApi(413, "arquivo_grande", f"O arquivo excede o limite de {s.max_upload_mb} MB.")
    if not conteudo:
        raise invalido("Arquivo vazio.", {"arquivo": "Arquivo vazio."})
    pasta = os.path.join(s.upload_dir, str(lead.id))
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, f"{uuid.uuid4().hex}_{nome}")
    with open(caminho, "wb") as fh:
        fh.write(conteudo)
    a = Anexo(lead_id=lead.id, interacao_id=interacao_id, nome=nome, caminho=caminho, tamanho=len(conteudo),
              tipo_mime=arquivo.content_type, enviado_por_id=u.id)
    db.add(a)
    db.flush()
    servicos.evento_sistema(db, lead, u, f"Anexo adicionado: {nome}.", {"evento": "anexo", "anexo_id": a.id})
    auditoria.registrar(db, u, "anexo", a.id, "criar", depois={"lead_id": lead.id, "nome": nome}, request=request)
    db.commit()
    return {"id": a.id, "nome": a.nome, "tamanho": a.tamanho, "tipo_mime": a.tipo_mime, "criado_em": a.criado_em}


@router.get("/leads/{lead_id}/anexos")
def listar_anexos(lead_id: int, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    servicos.obter_lead(db, lead_id, u)
    return [{"id": a.id, "nome": a.nome, "tamanho": a.tamanho, "tipo_mime": a.tipo_mime, "criado_em": a.criado_em,
             "interacao_id": a.interacao_id}
            for a in db.scalars(select(Anexo).where(Anexo.lead_id == lead_id).order_by(Anexo.criado_em.desc()))]


@router.get("/anexos/{anexo_id}")
def baixar_anexo(anexo_id: int, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    a = db.get(Anexo, anexo_id)
    if not a:
        raise nao_encontrado()
    servicos.obter_lead(db, a.lead_id, u)
    if not os.path.exists(a.caminho):
        raise nao_encontrado("Arquivo não está mais disponível.")
    return FileResponse(a.caminho, filename=a.nome, media_type="application/octet-stream")


# ---------------------------------------------------------------- e-mail pelo lead
def _render(texto: str, lead, usuario: Usuario) -> str:
    valores = {"nome": lead.nome, "primeiro_nome": lead.nome.split()[0], "empresa": lead.empresa or "",
               "vendedor": usuario.nome, "interesse": lead.interesse or ""}
    return re.sub(r"\{\{\s*(\w+)\s*\}\}", lambda m: valores.get(m.group(1), m.group(0)), texto)


@router.get("/modelos-email/ativos", response_model=list[ModeloEmailSaida])
def modelos_ativos(u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    return list(db.scalars(select(ModeloEmail).where(ModeloEmail.ativo).order_by(ModeloEmail.nome)))


@router.get("/leads/{lead_id}/email/previa")
def previa_email(lead_id: int, modelo_id: int, u: Usuario = Depends(escrita), db: Session = Depends(get_db)):
    lead = servicos.obter_lead(db, lead_id, u, editar=True)
    m = db.get(ModeloEmail, modelo_id)
    if not m:
        raise nao_encontrado("Modelo não encontrado.")
    return {"assunto": _render(m.assunto, lead, u), "corpo": _render(m.corpo, lead, u)}


@router.post("/leads/{lead_id}/email", response_model=InteracaoSaida, status_code=201)
def enviar_email(lead_id: int, dados: EnviarEmailEntrada, request: Request, u: Usuario = Depends(escrita),
                 db: Session = Depends(get_db)):
    lead = servicos.obter_lead(db, lead_id, u, editar=True)
    if not lead.email:
        raise invalido("Este lead não tem e-mail cadastrado.")
    try:
        message_id = emailer.enviar(lead.email, dados.assunto, dados.corpo, responder_para=None)
    except Exception as e:  # noqa: BLE001
        raise ErroApi(502, "falha_email", f"Não foi possível enviar o e-mail: {e}") from e
    momento = agora()
    i = Interacao(lead_id=lead.id, usuario_id=u.id, tipo="email", data_hora=momento,
                  resumo=f"E-mail enviado: {dados.assunto}", resultado=None,
                  dados={"direcao": "saida", "para": lead.email, "assunto": dados.assunto, "corpo": dados.corpo,
                         "message_id": message_id})
    db.add(i)
    servicos.registrar_contato(lead, momento)
    db.flush()
    auditoria.registrar(db, u, "interacao", i.id, "enviar_email", depois={"lead_id": lead.id,
                        "assunto": dados.assunto}, ip=ip_cliente(request))
    db.commit()
    db.refresh(i)
    return i
