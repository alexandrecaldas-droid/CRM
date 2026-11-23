"""Formato padrão de erro: {"erro": {"codigo", "mensagem", "detalhes"}}."""
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErroApi(Exception):
    def __init__(self, status: int, codigo: str, mensagem: str, detalhes: Any = None):
        self.status, self.codigo, self.mensagem, self.detalhes = status, codigo, mensagem, detalhes


def nao_encontrado(msg: str = "Registro não encontrado.") -> ErroApi:
    return ErroApi(404, "nao_encontrado", msg)


def proibido(msg: str = "Você não tem permissão para esta ação.") -> ErroApi:
    return ErroApi(403, "proibido", msg)


def invalido(msg: str, detalhes: Any = None) -> ErroApi:
    return ErroApi(422, "validacao", msg, detalhes)


_CODIGOS = {400: "requisicao_invalida", 401: "nao_autenticado", 403: "proibido",
            404: "nao_encontrado", 405: "metodo_nao_permitido", 413: "arquivo_grande",
            429: "limite_excedido"}

_MSG_CAMPO = {
    "missing": "Campo obrigatório.",
    "string_type": "Preenchimento obrigatório.",
    "string_too_short": "Preenchimento obrigatório.",
    "string_too_long": "Texto muito longo.",
    "int_parsing": "Número inválido.",
    "int_type": "Número inválido.",
    "decimal_parsing": "Valor numérico inválido.",
    "decimal_type": "Valor numérico inválido.",
    "decimal_max_digits": "Valor muito alto.",
    "decimal_max_places": "Use no máximo 2 casas decimais.",
    "greater_than_equal": "Não pode ser negativo.",
    "less_than_equal": "Valor acima do permitido.",
    "literal_error": "Opção inválida.",
    "enum": "Opção inválida.",
    "bool_parsing": "Valor inválido.",
    "date_from_datetime_parsing": "Data inválida.",
    "date_parsing": "Data inválida.",
    "datetime_parsing": "Data/hora inválida.",
    "datetime_from_date_parsing": "Data/hora inválida.",
    "json_invalid": "JSON inválido.",
    "too_short": "Lista vazia.",
    "too_long": "Itens demais.",
}


def traduzir(erro: dict) -> str:
    """Mensagem em pt-BR para um item de ValidationError do Pydantic."""
    if erro.get("type") == "value_error":
        return str(erro.get("msg", "Valor inválido.")).replace("Value error, ", "")
    return _MSG_CAMPO.get(erro.get("type"), "Valor inválido.")


def registrar(app: FastAPI) -> None:
    @app.exception_handler(ErroApi)
    async def _erro_api(_: Request, exc: ErroApi):
        return JSONResponse(status_code=exc.status, content={"erro": {
            "codigo": exc.codigo, "mensagem": exc.mensagem, "detalhes": exc.detalhes}})

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        return JSONResponse(status_code=exc.status_code, content={"erro": {
            "codigo": _CODIGOS.get(exc.status_code, "erro"), "mensagem": str(exc.detail),
            "detalhes": None}}, headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def _validacao(_: Request, exc: RequestValidationError):
        campos = {}
        for e in exc.errors():
            loc = [str(p) for p in e.get("loc", []) if p not in ("body", "query", "path")]
            campos[".".join(loc) or "geral"] = traduzir(e)
        return JSONResponse(status_code=422, content={"erro": {
            "codigo": "validacao", "mensagem": "Verifique os campos destacados.",
            "detalhes": campos}})
