"""Fase 2: interações, tarefas, lembretes, atribuição, busca/visões, notificações e e-mail."""
from datetime import UTC, datetime, timedelta

from app import emailer, worker
from app.models import Lead


def _iso(dt):
    return dt.astimezone(UTC).isoformat()


def test_interacao_atualiza_ultimo_e_primeiro_contato(vera, novo_lead):
    lead = novo_lead(vera)
    r = vera.post(f"/leads/{lead['id']}/interacoes", json={"tipo": "ligacao", "resumo": "Conversamos",
                                                            "resultado": "Pediu proposta"})
    assert r.status_code == 201
    l2 = vera.get(f"/leads/{lead['id']}").json()
    assert l2["ultimo_contato_em"] and l2["primeiro_contato_em"]


def test_nota_interna_nao_conta_como_contato(vera, novo_lead):
    lead = novo_lead(vera)
    vera.post(f"/leads/{lead['id']}/interacoes", json={"tipo": "nota", "resumo": "lembrar"})
    assert vera.get(f"/leads/{lead['id']}").json()["ultimo_contato_em"] is None


def test_interacao_futura_rejeitada(vera, novo_lead):
    lead = novo_lead(vera)
    futuro = _iso(datetime.now(UTC) + timedelta(days=1))
    r = vera.post(f"/leads/{lead['id']}/interacoes", json={"tipo": "ligacao", "resumo": "x", "data_hora": futuro})
    assert r.status_code == 422


def test_sem_proxima_acao_some_ao_criar_tarefa(vera, novo_lead):
    lead = novo_lead(vera)
    assert vera.get("/leads", params={"sem_proxima_acao": True}).json()["total"] == 1
    venc = _iso(datetime.now(UTC) + timedelta(days=2))
    r = vera.post("/tarefas", json={"lead_id": lead["id"], "titulo": "Ligar", "vencimento": venc})
    assert r.status_code == 201
    assert vera.get("/leads", params={"sem_proxima_acao": True}).json()["total"] == 0
    l2 = vera.get(f"/leads/{lead['id']}").json()
    assert l2["sem_proxima_acao"] is False and l2["proxima_tarefa"]
    vera.patch(f"/tarefas/{r.json()['id']}", json={"status": "concluida"})
    assert vera.get(f"/leads/{lead['id']}").json()["sem_proxima_acao"] is True


def test_lead_ganho_nao_aparece_como_sem_proxima_acao(vera, ids, novo_lead):
    lead = novo_lead(vera)
    vera.post(f"/leads/{lead['id']}/estagio", json={"estagio_id": ids["estagio"]["Ganho"], "valor_fechado": 1})
    assert vera.get("/leads", params={"sem_proxima_acao": True}).json()["total"] == 0


def test_lead_parado_depois_de_n_dias(vera, admin, novo_lead, db):
    lead = novo_lead(vera)
    assert vera.get("/leads", params={"parado": True}).json()["total"] == 0
    obj = db.get(Lead, lead["id"])
    obj.criado_em = datetime.now(UTC) - timedelta(days=8)
    db.commit()
    assert vera.get("/leads", params={"parado": True}).json()["total"] == 1
    admin.put("/parametros", json={"dias_lead_parado": 10})
    assert vera.get("/leads", params={"parado": True}).json()["total"] == 0


def test_tarefas_atrasadas_hoje_e_permissoes(vera, vitor, novo_lead):
    lead = novo_lead(vera)
    vera.post("/tarefas", json={"lead_id": lead["id"], "titulo": "Atrasada",
                                "vencimento": _iso(datetime.now(UTC) - timedelta(hours=3))})
    assert vera.get("/tarefas", params={"situacao": "atrasadas"}).json()["total"] == 1
    assert vitor.get("/tarefas", params={"situacao": "atrasadas"}).json()["total"] == 0
    r = vitor.post("/tarefas", json={"lead_id": lead["id"], "titulo": "x", "vencimento": _iso(datetime.now(UTC))})
    assert r.status_code == 404


def test_lembretes_geram_notificacao_e_email_uma_vez(vera, novo_lead, db):
    lead = novo_lead(vera)
    vera.post("/tarefas", json={"lead_id": lead["id"], "titulo": "Atrasada",
                                "vencimento": _iso(datetime.now(UTC) - timedelta(hours=1))})
    assert worker.gerar_lembretes(db) == 1
    assert worker.gerar_lembretes(db) == 0
    n = vera.get("/notificacoes").json()
    assert n["nao_lidas"] == 1 and "atrasada" in n["itens"][0]["mensagem"].lower()
    worker.processar_fila(db)
    assert any("Tarefa atrasada" in m["Subject"] for m in emailer.ENVIADOS_TESTE)
    assert all(m["From"].endswith("<comercial@tenti.com.br>") for m in emailer.ENVIADOS_TESTE)


def test_rodizio_entre_vendedores_ativos(gestor, ids, novo_lead):
    r1 = novo_lead(gestor)
    r2 = novo_lead(gestor)
    r3 = novo_lead(gestor)
    nomes = [r["responsavel"]["nome"] for r in (r1, r2, r3)]
    assert set(nomes[:2]) == {"Vera", "Vitor"} and nomes[0] == nomes[2]


def test_regra_por_origem_tem_prioridade(admin, gestor, ids, novo_lead):
    admin.post("/regras-atribuicao", json={"origem_id": ids["origem"]["Evento"],
                                           "usuario_id": ids["usuario"]["vitor@t.com"]})
    for _ in range(3):
        assert novo_lead(gestor, origem_id=ids["origem"]["Evento"])["responsavel"]["nome"] == "Vitor"


def test_regra_por_regiao(admin, gestor, ids, novo_lead):
    admin.post("/regras-atribuicao", json={"uf": "RS", "usuario_id": ids["usuario"]["vera@t.com"]})
    for _ in range(2):
        assert novo_lead(gestor, uf="RS")["responsavel"]["nome"] == "Vera"


def test_atribuicao_notifica_e_fica_no_historico(gestor, vera, ids, novo_lead):
    lead = novo_lead(vera)
    r = gestor.post(f"/leads/{lead['id']}/atribuir", json={"responsavel_id": ids["usuario"]["vitor@t.com"]})
    assert r.status_code == 200 and r.json()["responsavel"]["nome"] == "Vitor"
    linha = gestor.get(f"/leads/{lead['id']}/interacoes").json()
    assert any(i["dados"] and i["dados"].get("evento") == "responsavel" for i in linha)
    assert vera.get(f"/leads/{lead['id']}").status_code == 404


def test_vendedor_nao_reatribui(vera, ids, novo_lead):
    lead = novo_lead(vera)
    r = vera.post(f"/leads/{lead['id']}/atribuir", json={"responsavel_id": ids["usuario"]["vitor@t.com"]})
    assert r.status_code == 403


def test_reatribuicao_em_lote(gestor, vera, ids, novo_lead):
    leads = [novo_lead(vera)["id"] for _ in range(3)]
    r = gestor.post("/leads/atribuir-lote", json={"lead_ids": leads, "responsavel_id": ids["usuario"]["vitor@t.com"]})
    assert r.json()["atualizados"] == 3
    assert gestor.get("/leads", params={"responsavel_id": ids["usuario"]["vitor@t.com"]}).json()["total"] == 3


def test_visoes_salvas_sao_por_usuario(vera, vitor):
    r = vera.post("/visoes", json={"nome": "Parados", "filtros": {"parado": True}})
    assert r.status_code == 201
    assert len(vera.get("/visoes").json()) == 1
    assert vitor.get("/visoes").json() == []
    assert vitor.delete(f"/visoes/{r.json()['id']}").status_code == 404


def test_enviar_email_pelo_lead_registra_na_linha_do_tempo(vera, novo_lead):
    lead = novo_lead(vera, nome="Carlos Lima", empresa="ACME")
    modelos = [m for m in vera.get("/modelos-email/ativos").json() if m["nome"] == "Primeiro contato"]
    previa = vera.get(f"/leads/{lead['id']}/email/previa", params={"modelo_id": modelos[0]["id"]}).json()
    assert "Carlos" in previa["assunto"] and "ACME" in previa["corpo"]
    r = vera.post(f"/leads/{lead['id']}/email", json=previa)
    assert r.status_code == 201 and r.json()["tipo"] == "email"
    assert emailer.ENVIADOS_TESTE[-1]["To"] == lead["email"]
    assert vera.get(f"/leads/{lead['id']}").json()["ultimo_contato_em"]


def test_anexo_ate_10mb(vera, vitor, novo_lead):
    lead = novo_lead(vera)
    r = vera.post(f"/leads/{lead['id']}/anexos", files={"arquivo": ("proposta.pdf", b"%PDF-1.4 teste",
                                                                    "application/pdf")})
    assert r.status_code == 201
    aid = r.json()["id"]
    assert vera.get(f"/anexos/{aid}").content == b"%PDF-1.4 teste"
    assert vitor.get(f"/anexos/{aid}").status_code == 404
    grande = b"0" * (10 * 1024 * 1024 + 1)
    r = vera.post(f"/leads/{lead['id']}/anexos", files={"arquivo": ("g.pdf", grande, "application/pdf")})
    assert r.status_code == 413
    r = vera.post(f"/leads/{lead['id']}/anexos", files={"arquivo": ("x.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 422


def test_notificacao_de_lead_atribuido(gestor, vera, novo_lead):
    novo_lead(gestor)  # rodízio → Vera (primeira)
    n = vera.get("/notificacoes").json()
    assert n["nao_lidas"] >= 1
    vera.post("/notificacoes/lidas")
    assert vera.get("/notificacoes").json()["nao_lidas"] == 0
