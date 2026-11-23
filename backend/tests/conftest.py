import os
import tempfile

os.environ["MODO_TESTE"] = "1"
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="leads_up_")
os.environ["PUBLIC_RATE_LIMIT_MIN"] = "5"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app import db as dbmod  # noqa: E402
from app import emailer  # noqa: E402
from app.db import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Usuario  # noqa: E402
from app.routers import publico  # noqa: E402
from app.seed import essencial  # noqa: E402
from app.seguranca import hash_senha  # noqa: E402

SENHA = "Senha@123"


@pytest.fixture(autouse=True)
def banco():
    eng = dbmod.configurar(os.environ["DATABASE_URL"])
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    with dbmod.SessionLocal() as s:
        essencial(s)
        for nome, email, perfil in [("Gestor", "gestor@t.com", "gestor"), ("Vera", "vera@t.com", "vendedor"),
                                    ("Vitor", "vitor@t.com", "vendedor"), ("Leo Leitura", "leitura@t.com", "leitura")]:
            s.add(Usuario(nome=nome, email=email, perfil=perfil, senha_hash=hash_senha(SENHA)))
        admin = s.scalar(select(Usuario).where(Usuario.perfil == "admin"))
        admin.senha_hash = hash_senha(SENHA)
        admin.email = "admin@t.com"
        s.commit()
    emailer.ENVIADOS_TESTE.clear()
    publico._janelas.clear()
    yield
    Base.metadata.drop_all(eng)


@pytest.fixture
def db():
    s = dbmod.SessionLocal()
    yield s
    s.close()


@pytest.fixture
def client():
    return TestClient(app)


class Api:
    def __init__(self, client, token):
        self.c, self.h = client, {"Authorization": f"Bearer {token}"}

    def get(self, url, **kw):
        return self.c.get("/api" + url, headers=self.h, **kw)

    def post(self, url, **kw):
        return self.c.post("/api" + url, headers=self.h, **kw)

    def patch(self, url, **kw):
        return self.c.patch("/api" + url, headers=self.h, **kw)

    def put(self, url, **kw):
        return self.c.put("/api" + url, headers=self.h, **kw)

    def delete(self, url, **kw):
        return self.c.delete("/api" + url, headers=self.h, **kw)


def login(client, email):
    r = client.post("/api/auth/login", json={"email": email, "senha": SENHA})
    assert r.status_code == 200, r.text
    return Api(client, r.json()["token"])


@pytest.fixture
def admin(client):
    return login(client, "admin@t.com")


@pytest.fixture
def gestor(client):
    return login(client, "gestor@t.com")


@pytest.fixture
def vera(client):
    return login(client, "vera@t.com")


@pytest.fixture
def vitor(client):
    return login(client, "vitor@t.com")


@pytest.fixture
def leitura(client):
    return login(client, "leitura@t.com")


@pytest.fixture
def ids(admin):
    origens = {o["nome"]: o["id"] for o in admin.get("/origens").json()}
    estagios = {e["nome"]: e["id"] for e in admin.get("/estagios").json()}
    motivos = {m["nome"]: m["id"] for m in admin.get("/motivos-perda").json()}
    usuarios = {u["email"]: u["id"] for u in admin.get("/usuarios").json()}
    return {"origem": origens, "estagio": estagios, "motivo": motivos, "usuario": usuarios}


@pytest.fixture
def novo_lead(ids):
    contador = {"n": 0}

    def _criar(api, **kw):
        contador["n"] += 1
        n = contador["n"]
        dados = {"nome": f"Lead {n}", "email": f"lead{n}@exemplo.com", "origem_id": ids["origem"]["Indicação"]}
        dados.update(kw)
        r = api.post("/leads", json=dados)
        assert r.status_code == 201, r.text
        return r.json()
    return _criar
