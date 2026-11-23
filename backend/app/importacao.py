"""Importação em massa (CSV/XLSX): leitura, sugestão de mapeamento e processamento linha a linha."""
import csv
import io
from decimal import Decimal, InvalidOperation

from openpyxl import load_workbook
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import servicos
from .db import agora
from .erros import traduzir
from .models import Etiqueta, Importacao, Origem, Usuario
from .schemas import LeadEntrada
from .utils import sem_acento

CAMPOS_DESTINO = {
    "nome": "Nome", "email": "E-mail", "telefone": "Telefone", "empresa": "Empresa", "cargo": "Cargo",
    "cidade": "Cidade", "uf": "UF", "interesse": "Produto/serviço de interesse", "valor_estimado": "Valor estimado",
    "observacoes": "Observações", "origem": "Origem (nome)", "etiquetas": "Etiquetas (separadas por vírgula)",
    "utm_source": "UTM source", "utm_medium": "UTM medium", "utm_campaign": "UTM campaign",
}
SINONIMOS = {
    "nome": ["nome", "name", "nome completo", "contato", "cliente"],
    "email": ["email", "e-mail", "e mail", "mail", "correio"],
    "telefone": ["telefone", "fone", "celular", "whatsapp", "phone", "tel"],
    "empresa": ["empresa", "company", "organizacao", "razao social"],
    "cargo": ["cargo", "funcao", "titulo", "job title"],
    "cidade": ["cidade", "municipio", "city"],
    "uf": ["uf", "estado", "state"],
    "interesse": ["interesse", "produto", "servico", "produto ou servico"],
    "valor_estimado": ["valor", "valor estimado", "orcamento", "ticket"],
    "observacoes": ["observacoes", "obs", "notas", "comentarios"],
    "origem": ["origem", "canal", "fonte", "source"],
    "etiquetas": ["etiquetas", "tags", "etiqueta"],
    "utm_source": ["utm_source"], "utm_medium": ["utm_medium"], "utm_campaign": ["utm_campaign"],
}
MAX_LINHAS = 20000


def ler_planilha(caminho: str, nome: str) -> tuple[list[str], list[list[str]]]:
    if nome.lower().endswith((".xlsx", ".xlsm")):
        wb = load_workbook(caminho, read_only=True, data_only=True)
        ws = wb.worksheets[0]
        linhas = [["" if c is None else str(c).strip() for c in row] for row in ws.iter_rows(values_only=True)]
        wb.close()
    else:
        bruto = open(caminho, "rb").read()
        for cod in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                texto = bruto.decode(cod)
                break
            except UnicodeDecodeError:
                continue
        try:
            dialeto = csv.Sniffer().sniff(texto[:4096], delimiters=",;\t|")
        except csv.Error:
            dialeto = csv.excel
        linhas = [[c.strip() for c in row] for row in csv.reader(io.StringIO(texto), dialeto)]
    linhas = [r for r in linhas if any(c for c in r)]
    if not linhas:
        return [], []
    cab = [c or f"Coluna {i + 1}" for i, c in enumerate(linhas[0])]
    dados = [r + [""] * (len(cab) - len(r)) for r in linhas[1:MAX_LINHAS + 1]]
    return cab, dados


def sugerir_mapeamento(colunas: list[str]) -> dict[str, str]:
    mapa = {}
    for col in colunas:
        n = sem_acento(col).strip().replace("_", " ") if not col.lower().startswith("utm_") else col.lower()
        for campo, sins in SINONIMOS.items():
            if campo not in mapa.values() and (n in sins or sem_acento(col) in sins):
                mapa[col] = campo
                break
    return mapa


def _decimal(v: str) -> Decimal | None:
    v = v.replace("R$", "").replace(" ", "").strip()
    if not v:
        return None
    if "," in v:
        v = v.replace(".", "").replace(",", ".")
    try:
        return Decimal(v)
    except InvalidOperation as e:
        raise ValueError("Valor numérico inválido.") from e


def processar(db: Session, imp: Importacao) -> None:
    usuario = db.get(Usuario, imp.usuario_id)
    opcoes = imp.opcoes or {}
    modo_dup = opcoes.get("duplicados", "ignorar")  # ignorar | atualizar | criar
    origem_padrao = opcoes.get("origem_id")
    responsavel_id = opcoes.get("responsavel_id")
    mapa = {c: f for c, f in (imp.mapeamento or {}).items() if f}
    colunas, linhas = ler_planilha(imp.caminho, imp.nome_arquivo)
    idx = {c: i for i, c in enumerate(colunas)}
    origens = {sem_acento(o.nome): o.id for o in db.scalars(select(Origem).where(Origem.ativa))}
    etiquetas = {sem_acento(e.nome): e for e in db.scalars(select(Etiqueta))}
    erros, vistos = [], {}
    imp.total, imp.importados, imp.atualizados, imp.ignorados, imp.rejeitados = len(linhas), 0, 0, 0, 0
    for n, linha in enumerate(linhas, start=2):  # linha 1 é o cabeçalho
        bruto = {f: linha[idx[c]].strip() for c, f in mapa.items() if c in idx}
        try:
            with db.begin_nested():
                resultado = _linha(db, bruto, usuario, origens, etiquetas, origem_padrao, responsavel_id, modo_dup,
                                   vistos, n, imp.id)
            if resultado == "importado":
                imp.importados += 1
            elif resultado == "atualizado":
                imp.atualizados += 1
            else:
                imp.ignorados += 1
                erros.append({"linha": n, "tipo": "ignorado", "mensagem": resultado, "dados": bruto})
        except ValueError as e:
            imp.rejeitados += 1
            erros.append({"linha": n, "tipo": "rejeitado", "mensagem": str(e), "dados": bruto})
    imp.erros = erros
    imp.status = "concluida"
    imp.concluido_em = agora()


def _linha(db, bruto, usuario, origens, etiquetas, origem_padrao, responsavel_id, modo_dup, vistos, n, imp_id):
    origem_id = origem_padrao
    if bruto.get("origem"):
        origem_id = origens.get(sem_acento(bruto["origem"]))
        if not origem_id:
            raise ValueError(f"Origem “{bruto['origem']}” não cadastrada.")
    if not origem_id:
        raise ValueError("Origem não informada.")
    if not bruto.get("nome"):
        raise ValueError("Nome em branco.")
    dados = {k: bruto.get(k) or None for k in ("nome", "email", "telefone", "empresa", "cargo", "cidade", "uf",
                                               "interesse", "observacoes")}
    if bruto.get("valor_estimado"):
        dados["valor_estimado"] = _decimal(bruto["valor_estimado"])
    ids_etq = []
    for nome in (bruto.get("etiquetas") or "").split(","):
        nome = nome.strip()
        if nome:
            e = etiquetas.get(sem_acento(nome))
            if not e:
                e = Etiqueta(nome=nome[:60])
                db.add(e)
                db.flush()
                etiquetas[sem_acento(nome)] = e
            ids_etq.append(e.id)
    try:
        entrada = LeadEntrada(origem_id=origem_id, etiqueta_ids=ids_etq, responsavel_id=responsavel_id, **dados)
    except ValidationError as e:
        msgs = []
        for x in e.errors():
            campo = CAMPOS_DESTINO.get(".".join(map(str, x["loc"])), "")
            msgs.append(f"{campo + ': ' if campo else ''}{traduzir(x)}")
        raise ValueError("; ".join(msgs)) from e
    payload = entrada.model_dump()
    for utm in ("utm_source", "utm_medium", "utm_campaign"):
        payload[utm] = bruto.get(utm) or None
    for chave in (payload.get("email"), payload.get("telefone")):
        if chave and chave in vistos:
            return f"Duplicado dentro do arquivo (mesmo contato da linha {vistos[chave]})."
    for chave in (payload.get("email"), payload.get("telefone")):
        if chave:
            vistos[chave] = n
    dup = servicos.buscar_duplicados(db, payload.get("email"), payload.get("telefone"))
    if dup and modo_dup == "ignorar":
        return f"Já existe lead com este contato (#{dup[0].id} {dup[0].nome})."
    if dup and modo_dup == "atualizar":
        lead = dup[0]
        if usuario.perfil == "vendedor" and lead.responsavel_id != usuario.id:
            return "Contato já pertence a outro vendedor."
        novos = {k: v for k, v in payload.items() if k in servicos.CAMPOS_LEAD and v not in (None, "")
                 and getattr(lead, k) in (None, "") and k not in ("email", "telefone", "origem_id")}
        if ids_etq:
            novos["etiqueta_ids"] = list({e.id for e in lead.etiquetas} | set(ids_etq))
        if novos:
            servicos.atualizar_lead(db, lead, {**novos, "forcar_duplicado": True}, usuario, None)
        return "atualizado"
    payload["forcar_duplicado"] = True
    servicos.criar_lead(db, payload, usuario, None, canal=f"importação #{imp_id}", verificar_duplicado=False,
                        notificar_resp=False)
    return "importado"
