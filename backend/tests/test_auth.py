import pyotp

from app import emailer

from .conftest import SENHA, Api


def test_login_sucesso_e_me(client, admin):
    r = admin.get("/auth/me")
    assert r.status_code == 200
    assert r.json()["perfil"] == "admin"


def test_sem_token_retorna_401_no_formato_padrao(client):
    r = client.get("/api/leads")
    assert r.status_code == 401
    assert r.json()["erro"]["codigo"] == "nao_autenticado"


def test_senha_errada_e_bloqueio_por_tentativas(client):
    for _ in range(5):
        r = client.post("/api/auth/login", json={"email": "vera@t.com", "senha": "errada"})
        assert r.status_code == 401
        assert r.json()["erro"]["codigo"] == "credenciais_invalidas"
    r = client.post("/api/auth/login", json={"email": "vera@t.com", "senha": SENHA})
    assert r.status_code == 429


def test_logout_invalida_token(client, vera):
    assert vera.post("/auth/logout").status_code == 200
    assert vera.get("/auth/me").status_code == 401


def test_recuperar_e_redefinir_senha(client):
    r = client.post("/api/auth/recuperar-senha", json={"email": "vera@t.com"})
    assert r.status_code == 200
    corpo = emailer.ENVIADOS_TESTE[-1].get_content()
    token = corpo.split("token=")[1].split()[0]
    r = client.post("/api/auth/redefinir-senha", json={"token": token, "nova_senha": "fraca"})
    assert r.json()["erro"]["codigo"] == "senha_fraca"
    r = client.post("/api/auth/redefinir-senha", json={"token": token, "nova_senha": "NovaSenha123"})
    assert r.status_code == 200
    assert client.post("/api/auth/login", json={"email": "vera@t.com", "senha": "NovaSenha123"}).status_code == 200
    # token de uso único
    assert client.post("/api/auth/redefinir-senha", json={"token": token, "nova_senha": "Outra1234"}).status_code == 400


def test_recuperar_senha_nao_revela_email_inexistente(client):
    r = client.post("/api/auth/recuperar-senha", json={"email": "ninguem@t.com"})
    assert r.status_code == 200
    assert emailer.ENVIADOS_TESTE == []


def test_2fa_opcional(client, vera):
    seg = vera.post("/auth/2fa/configurar").json()["segredo"]
    assert vera.post("/auth/2fa/ativar", json={"codigo": "000000"}).status_code == 400
    assert vera.post("/auth/2fa/ativar", json={"codigo": pyotp.TOTP(seg).now()}).status_code == 200
    r = client.post("/api/auth/login", json={"email": "vera@t.com", "senha": SENHA})
    assert r.json()["erro"]["codigo"] == "2fa_requerido"
    r = client.post("/api/auth/login", json={"email": "vera@t.com", "senha": SENHA,
                                             "codigo_2fa": pyotp.TOTP(seg).now()})
    assert r.status_code == 200


def test_usuario_inativo_nao_entra(client, admin, ids):
    admin.patch(f"/usuarios/{ids['usuario']['vitor@t.com']}", json={"ativo": False})
    r = client.post("/api/auth/login", json={"email": "vitor@t.com", "senha": SENHA})
    assert r.status_code == 401


def test_somente_admin_gerencia_usuarios(gestor, vera):
    novo = {"nome": "Novo", "email": "novo@t.com", "perfil": "vendedor", "senha": "Senha1234"}
    assert gestor.post("/usuarios", json=novo).status_code == 403
    assert vera.put("/origens/1", json={"nome": "X"}).status_code == 403


def test_login_e_auditado(client, admin):
    itens = admin.get("/auditoria", params={"acao": "login"}).json()["itens"]
    assert any(i["entidade"] == "sessao" for i in itens)


def test_api_helper_isolado(client):
    assert isinstance(Api(client, "x"), Api)
