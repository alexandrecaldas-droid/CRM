import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text

from . import erros
from .config import get_settings
from .db import SessionLocal
from .routers import admin, auth, importacoes, interacoes, leads, lgpd, publico, relatorios, tarefas

DESCRICAO = """API REST do Sistema de Cadastro, Controle e Acompanhamento de Leads.

Autenticação: `POST /api/auth/login` devolve um token; envie-o em `Authorization: Bearer <token>`.
Erros seguem o formato `{"erro": {"codigo", "mensagem", "detalhes"}}`.
Captura externa: `POST /api/public/leads` com o cabeçalho `X-API-Key`.
"""


def criar_app() -> FastAPI:
    s = get_settings()
    logging.basicConfig(level=logging.INFO)
    app = FastAPI(title="Sistema de Leads — API", version="1.0.0", description=DESCRICAO,
                  docs_url="/api/docs", redoc_url="/api/redoc", openapi_url="/api/openapi.json")
    erros.registrar(app)

    # CORS: o formulário público pode ser incorporado em qualquer site da empresa.
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origens or ["*"], allow_methods=["POST", "OPTIONS"],
                       allow_headers=["Content-Type", "X-API-Key"], allow_credentials=False)

    @app.middleware("http")
    async def cabecalhos_seguranca(request: Request, call_next):
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if not request.url.path.startswith("/api/public"):
            resp.headers.setdefault("X-Frame-Options", "DENY")
        if request.url.path.startswith("/api/docs"):
            return resp
        resp.headers.setdefault("Content-Security-Policy",
                                "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                                "frame-ancestors 'none'")
        return resp

    for r in (auth, leads, interacoes, tarefas, importacoes, publico, relatorios, admin, lgpd):
        app.include_router(r.router, prefix="/api")

    @app.get("/api/saude", tags=["Infra"])
    def saude():
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {"status": "ok"}

    @app.api_route("/api/{caminho:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
    def api_404(caminho: str):
        return JSONResponse(status_code=404, content={"erro": {"codigo": "nao_encontrado",
                                                               "mensagem": "Rota inexistente.", "detalhes": None}})

    # Interface (SPA) compilada, servida pela própria API em produção.
    pasta = s.frontend_dir
    if pasta and os.path.isdir(pasta):
        indice = os.path.join(pasta, "index.html")

        @app.get("/{caminho:path}", include_in_schema=False)
        def spa(caminho: str):
            alvo = os.path.realpath(os.path.join(pasta, caminho))
            if caminho and alvo.startswith(os.path.realpath(pasta)) and os.path.isfile(alvo):
                cache = "public, max-age=31536000, immutable" if "/assets/" in alvo else "no-cache"
                return FileResponse(alvo, headers={"Cache-Control": cache})
            return FileResponse(indice, headers={"Cache-Control": "no-cache"})
    return app


app = criar_app()
