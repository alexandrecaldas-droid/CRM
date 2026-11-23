"""Fase 1: cadastro, duplicidade, funil, histórico e permissões."""


def test_cadastro_exige_nome_contato_e_origem(vera, ids):
    r = vera.post("/leads", json={"nome": "Sem contato", "origem_id": ids["origem"]["Indicação"]})
    assert r.status_code == 422
    assert "contato" in str(r.json()["erro"]["detalhes"]).lower()
    r = vera.post("/leads", json={"nome": "Sem origem", "email": "a@b.com"})
    assert r.status_code == 422
    assert "origem_id" in r.json()["erro"]["detalhes"]


def test_normalizacao_email_telefone(vera, novo_lead):
    lead = novo_lead(vera, email="  Fulano@Exemplo.COM ", telefone="(11) 98765-4321")
    assert lead["email"] == "fulano@exemplo.com"
    assert lead["telefone"] == "+5511987654321"


def test_telefone_invalido(vera, ids):
    r = vera.post("/leads", json={"nome": "X", "telefone": "123", "origem_id": ids["origem"]["Indicação"]})
    assert r.status_code == 422


def test_lead_criado_por_vendedor_fica_com_ele_no_estagio_novo(vera, novo_lead):
    lead = novo_lead(vera)
    assert lead["responsavel"]["nome"] == "Vera"
    assert lead["estagio"]["nome"] == "Novo"
    assert lead["sem_proxima_acao"] is True


def test_duplicidade_por_email_e_telefone_normalizados(vera, ids, novo_lead):
    original = novo_lead(vera, email="dup@x.com", telefone="11 98888-7777")
    r = vera.post("/leads", json={"nome": "Outro", "telefone": "+55 (11) 988887777",
                                  "origem_id": ids["origem"]["Evento"]})
    assert r.status_code == 409
    dup = r.json()["erro"]["detalhes"]["duplicados"][0]
    assert dup["id"] == original["id"] and dup["acessivel"] is True
    r = vera.post("/leads", json={"nome": "Outro", "email": "DUP@x.com", "origem_id": ids["origem"]["Evento"],
                                  "forcar_duplicado": True})
    assert r.status_code == 201


def test_duplicado_de_outro_vendedor_nao_revela_dados(vera, vitor, ids, novo_lead):
    novo_lead(vera, email="segredo@x.com")
    r = vitor.post("/leads", json={"nome": "Y", "email": "segredo@x.com", "origem_id": ids["origem"]["Evento"]})
    assert r.status_code == 409
    dup = r.json()["erro"]["detalhes"]["duplicados"][0]
    assert dup["acessivel"] is False and dup["id"] is None and dup["email"] is None


def test_verificacao_de_duplicado_em_tempo_real(vera, novo_lead):
    novo_lead(vera, email="rt@x.com")
    r = vera.get("/leads/duplicados", params={"email": "RT@x.com"})
    assert len(r.json()["duplicados"]) == 1


def test_vendedor_nao_acessa_lead_de_outro_nem_por_url_nem_api(vera, vitor, novo_lead):
    lead = novo_lead(vera)
    assert vitor.get(f"/leads/{lead['id']}").status_code == 404
    assert vitor.patch(f"/leads/{lead['id']}", json={"nome": "hack"}).status_code == 404
    assert vitor.get(f"/leads/{lead['id']}/interacoes").status_code == 404
    assert vitor.post(f"/leads/{lead['id']}/interacoes", json={"tipo": "nota", "resumo": "x"}).status_code == 404
    assert vitor.post(f"/leads/{lead['id']}/estagio", json={"estagio_id": 2}).status_code == 404
    assert vitor.get("/leads").json()["total"] == 0
    assert all(c["total"] == 0 for c in vitor.get("/leads/kanban").json()["colunas"])


def test_gestor_e_leitura_veem_todos_leitura_nao_edita(vera, gestor, leitura, novo_lead):
    lead = novo_lead(vera)
    assert gestor.get(f"/leads/{lead['id']}").status_code == 200
    assert leitura.get(f"/leads/{lead['id']}").status_code == 200
    assert leitura.patch(f"/leads/{lead['id']}", json={"nome": "x"}).status_code == 403
    assert leitura.post("/leads", json={"nome": "x", "email": "l@x.com", "origem_id": 1}).status_code == 403


def test_funil_completo_ate_ganho_com_historico(vera, ids, novo_lead):
    lead = novo_lead(vera)
    for nome in ["Contatado", "Qualificado", "Proposta enviada", "Negociação"]:
        r = vera.post(f"/leads/{lead['id']}/estagio", json={"estagio_id": ids["estagio"][nome]})
        assert r.status_code == 200, r.text
    r = vera.post(f"/leads/{lead['id']}/estagio", json={"estagio_id": ids["estagio"]["Ganho"]})
    assert r.status_code == 422 and "valor_fechado" in r.json()["erro"]["detalhes"]
    r = vera.post(f"/leads/{lead['id']}/estagio", json={"estagio_id": ids["estagio"]["Ganho"],
                                                        "valor_fechado": "12500.50"})
    assert r.status_code == 200
    assert r.json()["estagio"]["tipo"] == "ganho" and float(r.json()["valor_fechado"]) == 12500.5
    assert r.json()["fechado_em"]
    hist = vera.get(f"/leads/{lead['id']}/estagios").json()
    assert [p["para"] for p in hist["passagens"]] == ["Novo", "Contatado", "Qualificado", "Proposta enviada",
                                                       "Negociação", "Ganho"]
    assert all(p["usuario"] for p in hist["passagens"][1:])
    assert "Novo" in hist["tempo_por_estagio"]
    linha = vera.get(f"/leads/{lead['id']}/interacoes").json()
    estagios = [i for i in linha if i["tipo"] == "sistema" and i["dados"]["evento"] == "estagio"]
    assert len(estagios) == 5 and all(i["usuario"]["nome"] == "Vera" for i in estagios)


def test_perdido_exige_motivo(vera, ids, novo_lead):
    lead = novo_lead(vera)
    r = vera.post(f"/leads/{lead['id']}/estagio", json={"estagio_id": ids["estagio"]["Perdido"]})
    assert r.status_code == 422 and "motivo_perda_id" in r.json()["erro"]["detalhes"]
    r = vera.post(f"/leads/{lead['id']}/estagio", json={"estagio_id": ids["estagio"]["Perdido"],
                                                        "motivo_perda_id": ids["motivo"]["Preço"]})
    assert r.status_code == 200 and r.json()["motivo_perda"]["nome"] == "Preço"


def test_reabrir_somente_gestor_ou_admin(vera, gestor, ids, novo_lead):
    lead = novo_lead(vera)
    vera.post(f"/leads/{lead['id']}/estagio", json={"estagio_id": ids["estagio"]["Perdido"],
                                                    "motivo_perda_id": ids["motivo"]["Preço"]})
    r = vera.post(f"/leads/{lead['id']}/estagio", json={"estagio_id": ids["estagio"]["Qualificado"]})
    assert r.status_code == 403
    r = gestor.post(f"/leads/{lead['id']}/estagio", json={"estagio_id": ids["estagio"]["Qualificado"]})
    assert r.status_code == 200 and r.json()["motivo_perda"] is None
    linha = gestor.get(f"/leads/{lead['id']}/interacoes").json()
    assert any(i["dados"] and i["dados"].get("reabertura") for i in linha)
    aud = gestor.get("/leads").json()
    assert aud["total"] == 1


def test_edicao_aparece_na_linha_do_tempo_com_autor(vera, novo_lead):
    lead = novo_lead(vera)
    vera.patch(f"/leads/{lead['id']}", json={"empresa": "Nova Empresa", "valor_estimado": "1000"})
    linha = vera.get(f"/leads/{lead['id']}/interacoes").json()
    ed = next(i for i in linha if i["dados"] and i["dados"].get("evento") == "edicao")
    assert "empresa" in ed["dados"]["mudancas"] and ed["usuario"]["nome"] == "Vera"


def test_edicao_nao_pode_remover_todos_os_contatos(vera, novo_lead):
    lead = novo_lead(vera)
    r = vera.patch(f"/leads/{lead['id']}", json={"email": None})
    assert r.status_code == 422


def test_lista_busca_filtros_e_paginacao(vera, gestor, ids, novo_lead):
    novo_lead(vera, nome="Ana Souza", empresa="Padaria Pão Bom", telefone="11 91234-5678")
    novo_lead(vera, nome="Bruno", origem_id=ids["origem"]["Evento"], valor_estimado="50000")
    for _ in range(3):
        novo_lead(vera)
    assert gestor.get("/leads", params={"q": "padaria"}).json()["total"] == 1
    assert gestor.get("/leads", params={"q": "1234-5678"}).json()["total"] == 1
    assert gestor.get("/leads", params={"origem_id": ids["origem"]["Evento"]}).json()["total"] == 1
    assert gestor.get("/leads", params={"valor_min": 10000}).json()["total"] == 1
    p = gestor.get("/leads", params={"tamanho": 2, "pagina": 2, "ordenar": "nome", "direcao": "asc"}).json()
    assert p["total"] == 5 and len(p["itens"]) == 2


def test_kanban_colunas_na_ordem_do_funil(vera, novo_lead):
    novo_lead(vera)
    cols = vera.get("/leads/kanban").json()["colunas"]
    assert [c["estagio"]["nome"] for c in cols][:3] == ["Novo", "Contatado", "Qualificado"]
    assert cols[0]["total"] == 1


def test_exclusao_logica_somente_gestao(vera, gestor, novo_lead, db):
    from app.models import Lead
    lead = novo_lead(vera)
    assert vera.delete(f"/leads/{lead['id']}").status_code == 403
    assert gestor.delete(f"/leads/{lead['id']}").status_code == 200
    assert gestor.get(f"/leads/{lead['id']}").status_code == 404
    assert db.get(Lead, lead["id"]).excluido_em is not None


def test_mesclar_leads(gestor, vera, novo_lead):
    a = novo_lead(vera, email="a@m.com")
    b = novo_lead(vera, email="b@m.com", telefone="11 97777-1111", empresa="Empresa B")
    vera.post(f"/leads/{b['id']}/interacoes", json={"tipo": "ligacao", "resumo": "ligou"})
    r = vera.post("/leads/mesclar", json={"principal_id": a["id"], "secundario_id": b["id"]})
    assert r.status_code == 200
    assert r.json()["telefone"] == "+5511977771111" and r.json()["empresa"] == "Empresa B"
    linha = vera.get(f"/leads/{a['id']}/interacoes").json()
    assert any(i["resumo"] == "ligou" for i in linha)
    assert vera.get(f"/leads/{b['id']}").status_code == 404


def test_estagio_e_origem_em_uso_nao_podem_ser_excluidos(admin, vera, ids, novo_lead):
    novo_lead(vera)
    assert admin.delete(f"/origens/{ids['origem']['Indicação']}").status_code == 409
    assert admin.delete(f"/estagios/{ids['estagio']['Novo']}").status_code == 409
    r = admin.put(f"/origens/{ids['origem']['Indicação']}", json={"nome": "Indicação", "ativa": False})
    assert r.status_code == 200 and r.json()["ativa"] is False


def test_funil_configuravel(admin, ids):
    r = admin.post("/estagios", json={"nome": "Demonstração", "ordem": 4, "tipo": "aberto"})
    assert r.status_code == 201
    r = admin.put(f"/estagios/{ids['estagio']['Ganho']}", json={"nome": "Ganho", "ordem": 6, "tipo": "aberto"})
    assert r.status_code == 422  # funil precisa de um estágio de ganho
