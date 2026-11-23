"""Captura externa: webhook/formulário incorporado com chave de API e registro de UTM."""
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import auditoria, servicos
from ..config import get_settings
from ..db import agora, get_db
from ..erros import ErroApi, invalido, traduzir
from ..models import ChaveApi, Origem
from ..schemas import LeadEntrada
from ..seguranca import ip_cliente, sha256

router = APIRouter(prefix="/public", tags=["Captura externa"])

_janelas: dict[int, deque] = defaultdict(deque)
CAMPOS = ("nome", "email", "telefone", "empresa", "cargo", "cidade", "uf", "interesse", "observacoes",
          "valor_estimado")


def _limitar(chave_id: int) -> None:
    """Limite por chave (janela deslizante de 60 s, em memória do processo)."""
    limite = get_settings().public_rate_limit_min
    janela = _janelas[chave_id]
    t = time.monotonic()
    while janela and t - janela[0] > 60:
        janela.popleft()
    if len(janela) >= limite:
        raise ErroApi(429, "limite_excedido", "Limite de requisições por minuto excedido para esta chave.")
    janela.append(t)


async def _corpo(request: Request) -> dict:
    tipo = request.headers.get("content-type", "")
    if "application/json" in tipo:
        try:
            dados = await request.json()
        except ValueError as e:
            raise invalido("JSON inválido.") from e
        if not isinstance(dados, dict):
            raise invalido("Envie um objeto JSON.")
        return dados
    form = await request.form()
    return {k: v for k, v in form.items() if isinstance(v, str)}


@router.post("/leads", status_code=201)
async def capturar(request: Request, db: Session = Depends(get_db)):
    dados = await _corpo(request)
    bruta = request.headers.get("x-api-key") or request.query_params.get("chave") or dados.pop("chave", None)
    if not bruta:
        raise ErroApi(401, "chave_ausente", "Informe a chave de API (cabeçalho X-API-Key).")
    chave = db.scalar(select(ChaveApi).where(ChaveApi.chave_hash == sha256(str(bruta)), ChaveApi.ativa))
    if not chave:
        raise ErroApi(401, "chave_invalida", "Chave de API inválida ou revogada.")
    _limitar(chave.id)
    if dados.get("website"):  # honeypot anti-robô dos formulários incorporados
        return {"ok": True}
    origem_id = chave.origem_id
    if dados.get("origem"):
        o = db.scalar(select(Origem).where(Origem.nome == str(dados["origem"]), Origem.ativa))
        if o:
            origem_id = o.id
    entrada = {k: (str(dados[k]) if dados.get(k) not in (None, "") else None) for k in CAMPOS}
    entrada["consentimento"] = str(dados.get("consentimento", "")).lower() in ("1", "true", "on", "sim")
    try:
        lead_in = LeadEntrada(origem_id=origem_id, **entrada)
    except ValidationError as e:
        raise invalido("Dados inválidos.", {".".join(map(str, x["loc"])) or "geral": traduzir(x)
                                            for x in e.errors()}) from e
    payload = lead_in.model_dump()
    for utm in ("utm_source", "utm_medium", "utm_campaign"):
        v = dados.get(utm) or request.query_params.get(utm)
        payload[utm] = str(v)[:150] if v else None
    ip = ip_cliente(request)
    chave.ultimo_uso_em = agora()
    duplicados = servicos.buscar_duplicados(db, payload.get("email"), payload.get("telefone"))
    if duplicados:
        # Sem usuário para confirmar: não cria duplicado; registra o novo contato no lead existente.
        lead = duplicados[0]
        servicos.evento_sistema(db, lead, None, f"Novo envio de formulário ({chave.nome}) com contato já cadastrado.",
                                {"evento": "captura_duplicada", "dados": {k: v for k, v in payload.items()
                                 if k in CAMPOS or k.startswith("utm_")}})
        servicos.notificar(db, lead.responsavel_id, "lead_retorno", f"{lead.nome} enviou o formulário novamente.",
                           lead.id)
        auditoria.registrar(db, None, "lead", lead.id, "captura_duplicada", ip=ip)
        db.commit()
        resultado = {"ok": True, "id": lead.id, "duplicado": True}
    else:
        lead = servicos.criar_lead(db, payload, None, ip, canal=f"webhook: {chave.nome}", verificar_duplicado=False)
        db.commit()
        resultado = {"ok": True, "id": lead.id, "duplicado": False}
    redirecionar = dados.get("redirecionar") or dados.get("_next")
    if redirecionar and str(redirecionar).startswith(("https://", "http://")):
        return RedirectResponse(str(redirecionar), status_code=303)
    if "application/json" not in request.headers.get("content-type", "") and \
            "text/html" in request.headers.get("accept", ""):
        return HTMLResponse("<!doctype html><meta charset=utf-8><title>Recebido</title>"
                            "<p style='font-family:sans-serif'>Obrigado! Recebemos seus dados e entraremos em "
                            "contato em breve.</p>", status_code=201)
    return resultado
