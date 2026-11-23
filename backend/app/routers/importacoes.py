import csv
import io
import os
import uuid

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import auditoria, importacao
from ..config import get_settings
from ..db import get_db
from ..erros import ErroApi, invalido, nao_encontrado
from ..models import Importacao, Job, Usuario
from ..seguranca import escrita, ve_todos

router = APIRouter(prefix="/importacoes", tags=["Importação"])


class ProcessarEntrada(BaseModel):
    mapeamento: dict[str, str | None]
    origem_id: int | None = None
    responsavel_id: int | None = None
    duplicados: str = "ignorar"


def _obter(db: Session, iid: int, u: Usuario) -> Importacao:
    imp = db.get(Importacao, iid)
    if not imp or (not ve_todos(u) and imp.usuario_id != u.id):
        raise nao_encontrado("Importação não encontrada.")
    return imp


def _saida(imp: Importacao, amostra: list | None = None) -> dict:
    d = {k: getattr(imp, k) for k in ("id", "nome_arquivo", "status", "colunas", "mapeamento", "opcoes", "total",
                                      "importados", "atualizados", "ignorados", "rejeitados", "criado_em",
                                      "concluido_em")}
    d["erros"] = imp.erros[:500] if imp.erros else []
    d["total_erros"] = len(imp.erros or [])
    if amostra is not None:
        d["amostra"] = amostra
    return d


@router.get("/campos")
def campos(u: Usuario = Depends(escrita)):
    return importacao.CAMPOS_DESTINO


@router.get("/modelo.csv")
def modelo_csv(u: Usuario = Depends(escrita)):
    cab = "nome;email;telefone;empresa;cargo;cidade;uf;interesse;valor_estimado;origem;etiquetas;observacoes\n"
    ex = "Maria Souza;maria@exemplo.com.br;(11) 98888-7777;Exemplo Ltda;Compras;São Paulo;SP;Consultoria;15000,00;" \
         "Evento;feira 2026;Conheceu no estande\n"
    return Response(("﻿" + cab + ex).encode(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=modelo_importacao_leads.csv"})


@router.get("")
def listar(u: Usuario = Depends(escrita), db: Session = Depends(get_db)):
    q = select(Importacao).order_by(Importacao.criado_em.desc()).limit(30)
    if not ve_todos(u):
        q = q.where(Importacao.usuario_id == u.id)
    return [{k: v for k, v in _saida(i).items() if k != "erros"} for i in db.scalars(q)]


@router.post("", status_code=201)
async def enviar(request: Request, arquivo: UploadFile = File(...), u: Usuario = Depends(escrita),
                 db: Session = Depends(get_db)):
    """Etapa 1: recebe o arquivo e devolve colunas, amostra e mapeamento sugerido (pré-visualização)."""
    nome = os.path.basename(arquivo.filename or "")
    if not nome.lower().endswith((".csv", ".xlsx", ".txt")):
        raise invalido("Envie um arquivo .csv ou .xlsx.", {"arquivo": "Formato não suportado."})
    s = get_settings()
    conteudo = await arquivo.read(20 * 1024 * 1024 + 1)
    if len(conteudo) > 20 * 1024 * 1024:
        raise ErroApi(413, "arquivo_grande", "A planilha excede 20 MB.")
    pasta = os.path.join(s.upload_dir, "_importacoes")
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, f"{uuid.uuid4().hex}_{nome}")
    with open(caminho, "wb") as fh:
        fh.write(conteudo)
    try:
        colunas, linhas = importacao.ler_planilha(caminho, nome)
    except Exception as e:  # noqa: BLE001
        os.remove(caminho)
        raise invalido("Não foi possível ler a planilha. Verifique o formato.") from e
    if not colunas or not linhas:
        os.remove(caminho)
        raise invalido("A planilha está vazia ou só tem cabeçalho.")
    imp = Importacao(usuario_id=u.id, nome_arquivo=nome, caminho=caminho, colunas=colunas,
                     mapeamento=importacao.sugerir_mapeamento(colunas), total=len(linhas))
    db.add(imp)
    db.commit()
    return _saida(imp, amostra=linhas[:10])


@router.post("/{iid}/processar")
def processar(iid: int, dados: ProcessarEntrada, request: Request, u: Usuario = Depends(escrita),
              db: Session = Depends(get_db)):
    """Etapa 2: confirma o mapeamento e envia para o worker."""
    imp = _obter(db, iid, u)
    if imp.status != "rascunho":
        raise invalido("Esta importação já foi enviada para processamento.")
    destinos = [f for f in dados.mapeamento.values() if f]
    invalidos = [f for f in destinos if f not in importacao.CAMPOS_DESTINO]
    if invalidos:
        raise invalido(f"Campo de destino inválido: {', '.join(invalidos)}.")
    if len(destinos) != len(set(destinos)):
        raise invalido("Cada campo do sistema só pode ser mapeado uma vez.")
    if "nome" not in destinos or not ({"email", "telefone"} & set(destinos)):
        raise invalido("Mapeie ao menos Nome e um contato (E-mail ou Telefone).")
    if "origem" not in destinos and not dados.origem_id:
        raise invalido("Escolha uma origem padrão ou mapeie a coluna de origem.", {"origem_id": "Obrigatória."})
    if dados.duplicados not in ("ignorar", "atualizar", "criar"):
        raise invalido("Opção de duplicados inválida.")
    if u.perfil == "vendedor" and dados.responsavel_id not in (None, u.id):
        raise invalido("Vendedores importam leads apenas para si mesmos.")
    imp.mapeamento = dados.mapeamento
    imp.opcoes = {"origem_id": dados.origem_id, "responsavel_id": dados.responsavel_id,
                  "duplicados": dados.duplicados}
    imp.status = "pendente"
    db.add(Job(tipo="importacao", payload={"importacao_id": imp.id}))
    auditoria.registrar(db, u, "importacao", imp.id, "criar", depois={"arquivo": imp.nome_arquivo,
                        "linhas": imp.total, **imp.opcoes}, request=request)
    db.commit()
    return _saida(imp)


@router.get("/{iid}")
def obter(iid: int, u: Usuario = Depends(escrita), db: Session = Depends(get_db)):
    return _saida(_obter(db, iid, u))


@router.get("/{iid}/erros.csv")
def erros_csv(iid: int, u: Usuario = Depends(escrita), db: Session = Depends(get_db)):
    imp = _obter(db, iid, u)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    cols = imp.colunas
    inverso = {f: c for c, f in (imp.mapeamento or {}).items() if f}
    w.writerow(["linha", "situacao", "motivo", *[inverso.get(f, f) for f in importacao.CAMPOS_DESTINO
                                                 if f in inverso]])
    for e in imp.erros or []:
        w.writerow([e["linha"], e["tipo"], e["mensagem"], *[e["dados"].get(f, "") for f in importacao.CAMPOS_DESTINO
                                                            if f in inverso]])
    del cols
    return Response(("﻿" + buf.getvalue()).encode(), media_type="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=importacao_{iid}_erros.csv"})
