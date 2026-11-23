"""Worker de tarefas em segundo plano: importações, envio de e-mails, lembretes e leitura IMAP.

Usa a própria tabela `job` como fila (sem Redis, adequado ao volume previsto).
Execução: python -m app.worker
"""
import logging
import time
from datetime import timedelta

from sqlalchemy import select, update

from . import emailer, importacao, servicos
from .config import get_settings
from .db import SessionLocal, agora
from .models import Importacao, Interacao, Job, Origem
from .routers.tarefas import tarefas_para_lembrete

log = logging.getLogger("worker")


def _pegar_job(db) -> Job | None:
    q = (select(Job).where(Job.status == "pendente", Job.executar_apos <= agora())
         .order_by(Job.id).limit(1))
    if db.bind.dialect.name == "postgresql":
        q = q.with_for_update(skip_locked=True)
    job = db.scalar(q)
    if job:
        job.status = "processando"
        job.tentativas += 1
        db.commit()
    return job


def executar_job(db, job: Job) -> None:
    if job.tipo == "email":
        p = job.payload
        emailer.enviar(p["para"], p["assunto"], p["corpo"])
    elif job.tipo == "importacao":
        imp = db.get(Importacao, job.payload["importacao_id"])
        imp.status = "processando"
        db.commit()
        importacao.processar(db, imp)
        servicos.notificar(db, imp.usuario_id, "importacao",
                           f"Importação “{imp.nome_arquivo}” concluída: {imp.importados} importados, "
                           f"{imp.atualizados} atualizados, {imp.ignorados} ignorados, {imp.rejeitados} rejeitados.")
    else:
        raise ValueError(f"Tipo de job desconhecido: {job.tipo}")


def processar_fila(db, maximo: int = 50) -> int:
    feitos = 0
    while feitos < maximo:
        job = _pegar_job(db)
        if not job:
            break
        try:
            executar_job(db, job)
            job.status = "concluido"
            job.concluido_em = agora()
            db.commit()
        except Exception as e:  # noqa: BLE001
            db.rollback()
            job = db.get(Job, job.id)
            log.exception("Falha no job %s", job.id)
            job.erro = str(e)[:2000]
            if job.tipo == "importacao":
                db.execute(update(Importacao).where(Importacao.id == job.payload["importacao_id"])
                           .values(status="erro"))
                job.status = "erro"
            elif job.tentativas >= 5:
                job.status = "erro"
            else:
                job.status = "pendente"
                job.executar_apos = agora() + timedelta(minutes=2 ** job.tentativas)
            db.commit()
        feitos += 1
    return feitos


def gerar_lembretes(db) -> int:
    """Notifica tarefas vencendo hoje e atrasadas (uma vez por tarefa e situação)."""
    n = 0
    hoje = servicos.hoje_local().isoformat()
    for t in tarefas_para_lembrete(db):
        venc_local = t.vencimento.astimezone(servicos.TZ).strftime("%d/%m %H:%M")
        if t.vencimento < agora():
            ok = servicos.notificar(db, t.responsavel_id, "tarefa_atrasada",
                                    f"Tarefa atrasada: {t.titulo} — {t.lead.nome} (venceu {venc_local})",
                                    t.lead_id, t.id, chave=f"atrasada:{t.id}:{t.vencimento.isoformat()}")
        else:
            ok = servicos.notificar(db, t.responsavel_id, "tarefa_hoje",
                                    f"Tarefa para hoje: {t.titulo} — {t.lead.nome} às {venc_local[-5:]}",
                                    t.lead_id, t.id, chave=f"hoje:{t.id}:{hoje}")
        n += int(ok)
    db.commit()
    return n


def processar_email_recebido(db, msg: emailer.MensagemRecebida) -> tuple[str, int | None]:
    """Remetente cadastrado → interação no lead; remetente novo → novo lead com origem “E-mail”."""
    remetente = msg.remetente
    if not remetente or remetente == get_settings().email_remetente.lower():
        return "ignorado", None
    if msg.message_id and db.scalar(select(Interacao.id).where(Interacao.tipo == "email",
                                                                 Interacao.dados["message_id"].as_string()
                                                                 == msg.message_id)):
        return "ignorado", None
    quando = msg.data or agora()
    if quando > agora():
        quando = agora()
    dados = {"direcao": "entrada", "de": remetente, "assunto": msg.assunto, "corpo": msg.corpo,
             "message_id": msg.message_id}
    existentes = servicos.buscar_duplicados(db, remetente, None)
    if existentes:
        lead = existentes[0]
        db.add(Interacao(lead_id=lead.id, usuario_id=None, tipo="email", data_hora=quando,
                         resumo=f"E-mail recebido: {msg.assunto or '(sem assunto)'}", dados=dados))
        servicos.registrar_contato(lead, quando)
        servicos.notificar(db, lead.responsavel_id, "email_recebido", f"Novo e-mail de {lead.nome}: {msg.assunto}",
                           lead.id)
        db.commit()
        return "interacao", lead.id
    origem = db.scalar(select(Origem).where(Origem.nome == "E-mail"))
    if not origem:
        origem = Origem(nome="E-mail", ativa=True)
        db.add(origem)
        db.flush()
    nome = msg.nome.strip() or remetente.split("@")[0]
    lead = servicos.criar_lead(db, {"nome": nome[:200], "email": remetente, "origem_id": origem.id,
                                    "observacoes": f"Assunto do primeiro e-mail: {msg.assunto}"},
                               None, None, canal="e-mail recebido", verificar_duplicado=False)
    db.add(Interacao(lead_id=lead.id, usuario_id=None, tipo="email", data_hora=quando,
                     resumo=f"E-mail recebido: {msg.assunto or '(sem assunto)'}", dados=dados))
    db.commit()
    return "lead_criado", lead.id


def ler_caixa(db) -> int:
    n = 0
    for msg in emailer.ler_nao_lidas():
        try:
            processar_email_recebido(db, msg)
            n += 1
        except Exception:  # noqa: BLE001
            db.rollback()
            log.exception("Falha ao processar e-mail de %s", msg.remetente)
    return n


def limpar_sessoes(db) -> None:
    from .models import Sessao
    db.execute(Sessao.__table__.delete().where(Sessao.expira_em < agora()))
    db.commit()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    s = get_settings()
    log.info("Worker iniciado (IMAP %s).", "ativo" if s.imap_host else "desativado")
    ultimo_lembrete = ultimo_imap = 0.0
    while True:
        db = SessionLocal()
        try:
            processar_fila(db)
            t = time.monotonic()
            if t - ultimo_lembrete > 60:
                gerar_lembretes(db)
                limpar_sessoes(db)
                ultimo_lembrete = t
            if s.imap_host and t - ultimo_imap > s.imap_intervalo_seg:
                ler_caixa(db)
                ultimo_imap = t
        except Exception:  # noqa: BLE001
            log.exception("Erro no ciclo do worker")
        finally:
            db.close()
        time.sleep(3)


if __name__ == "__main__":
    main()
