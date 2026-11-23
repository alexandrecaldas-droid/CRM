"""Fase 3: importação, webhook, e-mail recebido, painel/relatórios, exportação, auditoria e LGPD."""
import io
from datetime import UTC, datetime

from openpyxl import Workbook, load_workbook

from app import emailer, worker
from app.models import Auditoria


def _csv(linhas):
    return ("\n".join(linhas)).encode("utf-8")


def test_importacao_csv_conclui_validas_e_relata_rejeitadas(vera, ids, novo_lead, db):
    novo_lead(vera, email="existente@x.com")
    conteudo = _csv([
        "Nome;E-mail;Celular;Empresa;Valor",
        "Maria;maria@x.com;(11) 91111-2222;Acme;1.500,00",
        ";semnome@x.com;;;",
        "João;joao@x.com;;;abc",
        "Sem contato;;;;",
        "Existente;existente@x.com;;;",
        "Maria de novo;MARIA@x.com;;;",
        "Pedro;pedro@x.com;;Beta;",
    ])
    r = vera.post("/importacoes", files={"arquivo": ("leads.csv", conteudo, "text/csv")})
    assert r.status_code == 201, r.text
    imp = r.json()
    assert imp["mapeamento"]["E-mail"] == "email" and imp["mapeamento"]["Celular"] == "telefone"
    assert len(imp["amostra"]) == 7
    r = vera.post(f"/importacoes/{imp['id']}/processar", json={
        "mapeamento": {**imp["mapeamento"], "Valor": "valor_estimado"},
        "origem_id": ids["origem"]["Evento"], "duplicados": "ignorar"})
    assert r.status_code == 200, r.text
    worker.processar_fila(db)
    res = vera.get(f"/importacoes/{imp['id']}").json()
    assert res["status"] == "concluida"
    assert res["importados"] == 2 and res["rejeitados"] == 3 and res["ignorados"] == 2
    linhas_erro = {e["linha"]: e["mensagem"] for e in res["erros"]}
    assert set(linhas_erro) == {3, 4, 5, 6, 7}
    assert linhas_erro[3] == "Nome em branco."
    assert "numérico" in linhas_erro[4]
    assert "contato" in linhas_erro[5]
    csv_erros = vera.get(f"/importacoes/{imp['id']}/erros.csv").content.decode("utf-8-sig")
    assert "linha;situacao;motivo" in csv_erros
    lead = vera.get("/leads", params={"q": "maria@x.com"}).json()["itens"][0]
    assert float(lead["valor_estimado"]) == 1500.0 and lead["telefone"] == "+5511911112222"


def test_importacao_xlsx_com_origem_por_coluna(gestor, ids, db):
    wb = Workbook()
    ws = wb.active
    ws.append(["nome", "email", "origem", "tags"])
    ws.append(["Ana", "ana@x.com", "Evento", "VIP, feira"])
    ws.append(["Bia", "bia@x.com", "Origem Inexistente", ""])
    buf = io.BytesIO()
    wb.save(buf)
    imp = gestor.post("/importacoes", files={"arquivo": ("l.xlsx", buf.getvalue(), "application/vnd.ms-excel")}).json()
    gestor.post(f"/importacoes/{imp['id']}/processar", json={"mapeamento": {"nome": "nome", "email": "email",
                "origem": "origem", "tags": "etiquetas"}, "duplicados": "ignorar"})
    worker.processar_fila(db)
    res = gestor.get(f"/importacoes/{imp['id']}").json()
    assert res["importados"] == 1 and res["rejeitados"] == 1
    lead = gestor.get("/leads", params={"q": "ana@x.com"}).json()["itens"][0]
    assert {e["nome"] for e in lead["etiquetas"]} == {"VIP", "feira"}


def test_importacao_exige_mapeamento_minimo(vera):
    imp = vera.post("/importacoes", files={"arquivo": ("a.csv", _csv(["x;y", "1;2"]), "text/csv")}).json()
    r = vera.post(f"/importacoes/{imp['id']}/processar", json={"mapeamento": {"x": "nome"}, "origem_id": 1})
    assert r.status_code == 422


def _chave(admin, ids):
    return admin.post("/chaves-api", json={"nome": "Site", "origem_id": ids["origem"]["Formulário do site"]}).json()


def test_webhook_cria_lead_com_utm(client, admin, gestor, ids):
    chave = _chave(admin, ids)["chave"]
    r = client.post("/api/public/leads?utm_source=google&utm_medium=cpc", headers={"X-API-Key": chave},
                    json={"nome": "Visitante", "email": "visit@x.com", "utm_campaign": "black-friday"})
    assert r.status_code == 201, r.text
    lead = gestor.get(f"/leads/{r.json()['id']}").json()
    assert (lead["utm_source"], lead["utm_medium"], lead["utm_campaign"]) == ("google", "cpc", "black-friday")
    assert lead["origem"]["nome"] == "Formulário do site"
    assert lead["responsavel"]["nome"] in ("Vera", "Vitor")


def test_webhook_formulario_html_e_duplicado(client, admin, gestor, ids):
    chave = _chave(admin, ids)["chave"]
    dados = {"chave": chave, "nome": "Form", "telefone": "11 95555-4444"}
    assert client.post("/api/public/leads", data=dados).status_code == 201
    r = client.post("/api/public/leads", data=dados)
    assert r.json()["duplicado"] is True
    assert gestor.get("/leads").json()["total"] == 1


def test_webhook_chave_invalida_revogada_e_limite(client, admin, ids):
    assert client.post("/api/public/leads", json={"nome": "x", "email": "a@a.com"}).status_code == 401
    assert client.post("/api/public/leads", headers={"X-API-Key": "lk_errada"},
                       json={"nome": "x", "email": "a@a.com"}).status_code == 401
    c = _chave(admin, ids)
    codigos = [client.post("/api/public/leads", headers={"X-API-Key": c["chave"]},
                           json={"nome": "x", "email": f"r{i}@a.com"}).status_code for i in range(6)]
    assert codigos[:5] == [201] * 5 and codigos[5] == 429
    admin.post(f"/chaves-api/{c['id']}/revogar")
    assert client.post("/api/public/leads", headers={"X-API-Key": c["chave"]},
                       json={"nome": "x", "email": "z@a.com"}).status_code == 401


def test_webhook_valida_dados(client, admin, ids):
    chave = _chave(admin, ids)["chave"]
    r = client.post("/api/public/leads", headers={"X-API-Key": chave}, json={"nome": "Sem contato"})
    assert r.status_code == 422


def test_email_recebido_de_lead_vira_interacao_e_de_novo_vira_lead(vera, gestor, db, novo_lead):
    lead = novo_lead(vera, email="cliente@x.com")
    msg = emailer.MensagemRecebida("cliente@x.com", "Cliente", "Dúvida", "Olá", datetime.now(UTC), "<m1@x>")
    assert worker.processar_email_recebido(db, msg) == ("interacao", lead["id"])
    assert worker.processar_email_recebido(db, msg)[0] == "ignorado"  # mesma mensagem não duplica
    linha = vera.get(f"/leads/{lead['id']}/interacoes").json()
    assert any(i["tipo"] == "email" and i["dados"]["direcao"] == "entrada" for i in linha)
    novo = emailer.MensagemRecebida("novo@x.com", "Fulano Novo", "Orçamento", "Quero", None, "<m2@x>")
    status, lid = worker.processar_email_recebido(db, novo)
    assert status == "lead_criado"
    l2 = gestor.get(f"/leads/{lid}").json()
    assert l2["origem"]["nome"] == "E-mail" and l2["nome"] == "Fulano Novo"


def test_interpretar_email_bruto():
    bruto = (b"From: =?utf-8?q?Jos=C3=A9?= <Jose@X.com>\r\nSubject: Ol\xc3\xa1\r\n"
             b"Content-Type: text/plain; charset=utf-8\r\n\r\nCorpo")
    m = emailer.interpretar(bruto)
    assert m.remetente == "jose@x.com" and m.nome == "José" and m.corpo == "Corpo"


def test_painel_bate_com_lista_filtrada(gestor, vera, vitor, ids, novo_lead, db):
    from datetime import timedelta

    from app.models import Lead
    a = novo_lead(vera, valor_estimado="1000")
    novo_lead(vitor, valor_estimado="2000")
    c = novo_lead(vera, valor_estimado="3000")
    vera.post(f"/leads/{a['id']}/estagio", json={"estagio_id": ids["estagio"]["Ganho"], "valor_fechado": "900"})
    vera.post(f"/leads/{c['id']}/estagio", json={"estagio_id": ids["estagio"]["Contatado"]})
    vera.post(f"/leads/{c['id']}/interacoes", json={"tipo": "ligacao", "resumo": "oi"})
    velho = db.get(Lead, novo_lead(vitor)["id"])
    velho.criado_em = datetime.now(UTC) - timedelta(days=10)
    db.commit()
    p = gestor.get("/relatorios/painel").json()

    def lista(filtros):
        return gestor.get("/leads", params=filtros).json()

    assert p["novos"]["total"] == lista(p["novos"]["filtros"])["total"] == 4
    for e in p["por_estagio"]:
        assert e["total"] == lista(e["filtros"])["total"]
    assert p["parados"]["total"] == lista(p["parados"]["filtros"])["total"] == 1
    assert p["sem_proxima_acao"]["total"] == lista(p["sem_proxima_acao"]["filtros"])["total"] == 3
    vf = lista(p["valor_funil"]["filtros"])
    assert p["valor_funil"]["quantidade"] == vf["total"] == 3
    assert p["valor_funil"]["total"] == sum(float(i["valor_estimado"] or 0) for i in vf["itens"]) == 5000
    assert p["valor_ganho"]["total"] == 900 and lista(p["valor_ganho"]["filtros"])["total"] == 1
    assert p["conversao"]["geral"] == 25.0
    contatado = next(x for x in p["conversao"]["por_estagio"] if x["nome"] == "Contatado")
    assert contatado["chegaram"] == 2


def test_painel_do_vendedor_so_conta_os_proprios(vera, vitor, novo_lead):
    novo_lead(vera)
    novo_lead(vitor)
    assert vera.get("/relatorios/painel").json()["novos"]["total"] == 1


def test_relatorios_por_origem_vendedor_motivo(gestor, vera, ids, novo_lead):
    a = novo_lead(vera, origem_id=ids["origem"]["Evento"])
    novo_lead(vera, origem_id=ids["origem"]["Evento"])
    vera.post(f"/leads/{a['id']}/estagio", json={"estagio_id": ids["estagio"]["Perdido"],
                                                 "motivo_perda_id": ids["motivo"]["Preço"]})
    o = gestor.get("/relatorios/origens").json()["linhas"]
    ev = next(x for x in o if x["nome"] == "Evento")
    assert ev["total"] == 2 and ev["perdidos"] == 1
    v = gestor.get("/relatorios/vendedores").json()["linhas"]
    assert v[0]["nome"] == "Vera" and v[0]["total"] == 2
    m = gestor.get("/relatorios/motivos-perda").json()
    assert m["linhas"][0]["nome"] == "Preço" and m["total"] == 1
    f = gestor.get("/relatorios/funil").json()["linhas"]
    assert f[0]["nome"] == "Novo"


def test_exportacao_respeita_perfil_e_e_auditada(gestor, vera, leitura, novo_lead, db):
    novo_lead(vera, nome="Exportável")
    assert vera.get("/exportacoes", params={"tipo": "leads"}).status_code == 403
    assert leitura.get("/exportacoes", params={"tipo": "leads"}).status_code == 403
    r = gestor.get("/exportacoes", params={"tipo": "leads", "formato": "xlsx"})
    assert r.status_code == 200
    ws = load_workbook(io.BytesIO(r.content)).active
    assert ws["B2"].value == "Exportável"
    r = gestor.get("/exportacoes", params={"tipo": "origens", "formato": "csv"})
    assert r.content.decode("utf-8-sig").startswith("Origem;Leads")
    assert db.query(Auditoria).filter(Auditoria.acao == "exportar").count() == 2


def test_auditoria_registra_criacao_edicao_exclusao(admin, gestor, vera, novo_lead):
    lead = novo_lead(vera)
    vera.patch(f"/leads/{lead['id']}", json={"empresa": "X"})
    gestor.delete(f"/leads/{lead['id']}")
    itens = admin.get("/auditoria", params={"entidade": "lead", "entidade_id": str(lead["id"])}).json()["itens"]
    assert {i["acao"] for i in itens} >= {"criar", "editar", "excluir"}
    edicao = next(i for i in itens if i["acao"] == "editar")
    assert edicao["depois"]["empresa"] == "X" and edicao["usuario"] == "Vera"
    assert gestor.get("/auditoria").status_code == 403


def test_auditoria_nao_tem_rota_de_alteracao(admin):
    assert admin.delete("/auditoria/1").status_code in (404, 405)
    assert admin.patch("/auditoria/1", json={}).status_code in (404, 405)


def test_lgpd_exportar_e_anonimizar(admin, gestor, vera, novo_lead):
    lead = novo_lead(vera, nome="Titular Real", telefone="11 93333-2222")
    vera.post(f"/leads/{lead['id']}/interacoes", json={"tipo": "ligacao", "resumo": "Dado pessoal"})
    assert gestor.get(f"/lgpd/leads/{lead['id']}/exportar").status_code == 403
    dados = admin.get(f"/lgpd/leads/{lead['id']}/exportar").json()
    assert dados["titular"]["nome"] == "Titular Real" and len(dados["interacoes"]) >= 1
    assert len(admin.get("/lgpd/titular", params={"telefone": "11933332222"}).json()) == 1
    assert admin.post(f"/lgpd/leads/{lead['id']}/anonimizar").status_code == 200
    l2 = admin.get(f"/leads/{lead['id']}").json()
    assert l2["email"] is None and l2["telefone"] is None and "anonimizado" in l2["nome"].lower()
    linha = admin.get(f"/leads/{lead['id']}/interacoes").json()
    assert not any("Dado pessoal" in i["resumo"] for i in linha)
    assert vera.patch(f"/leads/{lead['id']}", json={"nome": "x"}).status_code == 400
