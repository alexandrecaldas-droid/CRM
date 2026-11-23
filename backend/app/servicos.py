"""Regras de negócio de leads: criação, duplicidade, funil, atribuição, filtros, notificações."""
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import Select, and_, exists, func, or_, select
from sqlalchemy.orm import Session

from . import auditoria, parametros
from .config import get_settings
from .db import agora
from .erros import ErroApi, invalido, nao_encontrado, proibido
from .models import (
    Estagio,
    Etiqueta,
    HistoricoEstagio,
    Interacao,
    Job,
    Lead,
    MotivoPerda,
    Notificacao,
    Origem,
    RegraAtribuicao,
    Tarefa,
    Usuario,
    lead_etiqueta,
)
from .seguranca import ve_todos

TZ = ZoneInfo(get_settings().timezone)


def inicio_dia(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=TZ).astimezone(UTC)


def fim_dia(d: date) -> datetime:
    return inicio_dia(d + timedelta(days=1))


def hoje_local() -> date:
    return agora().astimezone(TZ).date()


# ---------------------------------------------------------------- acesso
def escopo_leads(usuario: Usuario) -> Select:
    q = select(Lead).where(Lead.excluido_em.is_(None))
    if not ve_todos(usuario):
        q = q.where(Lead.responsavel_id == usuario.id)
    return q


def obter_lead(db: Session, lead_id: int, usuario: Usuario, editar: bool = False) -> Lead:
    """Devolve 404 (e não 403) para leads fora do escopo, para não revelar sua existência."""
    lead = db.get(Lead, lead_id)
    if not lead or lead.excluido_em is not None:
        raise nao_encontrado("Lead não encontrado.")
    if not ve_todos(usuario) and lead.responsavel_id != usuario.id:
        raise nao_encontrado("Lead não encontrado.")
    if editar and usuario.perfil == "leitura":
        raise proibido()
    return lead


# ---------------------------------------------------------------- notificações
def notificar(db: Session, usuario_id: int, tipo: str, mensagem: str, lead_id: int | None = None,
              tarefa_id: int | None = None, chave: str | None = None) -> bool:
    if chave and db.scalar(select(Notificacao.id).where(Notificacao.chave_dedupe == chave)):
        return False
    db.add(Notificacao(usuario_id=usuario_id, tipo=tipo, mensagem=mensagem, lead_id=lead_id,
                       tarefa_id=tarefa_id, chave_dedupe=chave))
    if parametros.obter(db, "notificar_por_email"):
        u = db.get(Usuario, usuario_id)
        if u and u.ativo:
            link = f"{get_settings().app_url}/leads/{lead_id}" if lead_id else get_settings().app_url
            db.add(Job(tipo="email", payload={
                "para": u.email, "assunto": f"[Leads] {mensagem[:120]}",
                "corpo": f"Olá, {u.nome}.\n\n{mensagem}\n\nAcesse: {link}\n\n— Sistema de Leads"}))
    return True


# ---------------------------------------------------------------- linha do tempo
def evento_sistema(db: Session, lead: Lead, usuario: Usuario | None, resumo: str,
                   dados: dict | None = None) -> None:
    db.add(Interacao(lead_id=lead.id, usuario_id=usuario.id if usuario else None, tipo="sistema",
                     resumo=resumo, dados=dados))


def registrar_contato(lead: Lead, quando: datetime) -> None:
    if lead.ultimo_contato_em is None or quando > lead.ultimo_contato_em:
        lead.ultimo_contato_em = quando
    if lead.primeiro_contato_em is None or quando < lead.primeiro_contato_em:
        lead.primeiro_contato_em = quando


# ---------------------------------------------------------------- duplicidade
def buscar_duplicados(db: Session, email: str | None, telefone: str | None,
                      ignorar_id: int | None = None) -> list[Lead]:
    conds = []
    if email:
        conds.append(Lead.email == email)
    if telefone:
        conds.append(Lead.telefone == telefone)
    if not conds:
        return []
    q = select(Lead).where(or_(*conds), Lead.excluido_em.is_(None), Lead.anonimizado_em.is_(None))
    if ignorar_id:
        q = q.where(Lead.id != ignorar_id)
    return list(db.scalars(q.limit(10)))


def erro_duplicado(duplicados: list[Lead], usuario: Usuario) -> ErroApi:
    itens = []
    for d in duplicados:
        acessivel = ve_todos(usuario) or d.responsavel_id == usuario.id
        itens.append({"id": d.id if acessivel else None, "nome": d.nome if acessivel else "(restrito)",
                      "email": d.email if acessivel else None, "telefone": d.telefone if acessivel else None,
                      "responsavel": d.responsavel.nome, "estagio": d.estagio.nome, "acessivel": acessivel})
    return ErroApi(409, "lead_duplicado",
                   "Já existe lead com este e-mail ou telefone.", {"duplicados": itens})


# ---------------------------------------------------------------- funil
def estagio_inicial(db: Session) -> Estagio:
    e = db.scalar(select(Estagio).where(Estagio.ativo, Estagio.tipo == "aberto").order_by(Estagio.ordem))
    if not e:
        raise ErroApi(500, "configuracao", "Nenhum estágio inicial ativo configurado.")
    return e


def escolher_responsavel(db: Session, origem_id: int | None, uf: str | None) -> Usuario:
    """Regras (origem/UF) por prioridade; senão rodízio entre vendedores ativos."""
    regras = db.scalars(select(RegraAtribuicao).where(RegraAtribuicao.ativa)
                        .order_by(RegraAtribuicao.prioridade, RegraAtribuicao.id))
    for r in regras:
        if r.origem_id and r.origem_id != origem_id:
            continue
        if r.uf and r.uf != uf:
            continue
        u = db.get(Usuario, r.usuario_id)
        if u and u.ativo:
            return u
    vendedores = list(db.scalars(select(Usuario).where(Usuario.ativo, Usuario.perfil == "vendedor")
                                 .order_by(Usuario.id)))
    if not vendedores:
        fallback = db.scalar(select(Usuario).where(Usuario.ativo, Usuario.perfil.in_(("gestor", "admin")))
                             .order_by(Usuario.perfil.desc(), Usuario.id))
        if not fallback:
            raise ErroApi(500, "configuracao", "Nenhum usuário ativo para receber leads.")
        return fallback
    ultimo = parametros.obter(db, "rodizio_ultimo_usuario_id")
    proximo = next((v for v in vendedores if ultimo is not None and v.id > ultimo), vendedores[0])
    parametros.definir(db, "rodizio_ultimo_usuario_id", proximo.id)
    return proximo


def _validar_responsavel(db: Session, responsavel_id: int) -> Usuario:
    u = db.get(Usuario, responsavel_id)
    if not u or not u.ativo or u.perfil == "leitura":
        raise invalido("Responsável inválido ou inativo.", {"responsavel_id": "Responsável inválido."})
    return u


def _validar_origem(db: Session, origem_id: int) -> Origem:
    o = db.get(Origem, origem_id)
    if not o or not o.ativa:
        raise invalido("Origem inválida.", {"origem_id": "Escolha uma origem ativa."})
    return o


def _etiquetas(db: Session, ids: list[int]) -> list[Etiqueta]:
    if not ids:
        return []
    ets = list(db.scalars(select(Etiqueta).where(Etiqueta.id.in_(ids))))
    if len(ets) != len(set(ids)):
        raise invalido("Etiqueta inválida.", {"etiqueta_ids": "Etiqueta inexistente."})
    return ets


CAMPOS_LEAD = ("nome", "email", "telefone", "empresa", "cargo", "cidade", "uf", "interesse",
               "valor_estimado", "observacoes", "origem_id", "base_legal")


def criar_lead(db: Session, dados: dict, usuario: Usuario | None, ip: str | None = None,
               canal: str = "manual", verificar_duplicado: bool = True, notificar_resp: bool = True) -> Lead:
    if verificar_duplicado and not dados.get("forcar_duplicado"):
        dup = buscar_duplicados(db, dados.get("email"), dados.get("telefone"))
        if dup:
            raise erro_duplicado(dup, usuario) if usuario else ErroApi(409, "lead_duplicado", "Duplicado.")
    origem = _validar_origem(db, dados["origem_id"])
    if dados.get("responsavel_id"):
        if usuario and usuario.perfil == "vendedor" and dados["responsavel_id"] != usuario.id:
            raise proibido("Vendedores só podem cadastrar leads para si mesmos.")
        resp = _validar_responsavel(db, dados["responsavel_id"])
    elif usuario and usuario.perfil == "vendedor":
        resp = usuario
    elif parametros.obter(db, "atribuicao_automatica") or usuario is None:
        resp = escolher_responsavel(db, origem.id, dados.get("uf"))
    else:
        resp = usuario
    estagio = estagio_inicial(db)
    momento = agora()
    lead = Lead(**{k: dados.get(k) for k in CAMPOS_LEAD}, estagio_id=estagio.id, responsavel_id=resp.id,
                utm_source=dados.get("utm_source"), utm_medium=dados.get("utm_medium"),
                utm_campaign=dados.get("utm_campaign"), criado_por_id=usuario.id if usuario else None,
                criado_em=momento, estagio_desde=momento)
    if dados.get("consentimento"):
        lead.consentimento_em = momento
        lead.base_legal = lead.base_legal or "consentimento"
    lead.etiquetas = _etiquetas(db, dados.get("etiqueta_ids") or [])
    db.add(lead)
    db.flush()
    db.add(HistoricoEstagio(lead_id=lead.id, de_estagio_id=None, para_estagio_id=estagio.id,
                            usuario_id=usuario.id if usuario else None, data_hora=momento))
    evento_sistema(db, lead, usuario, f"Lead criado ({canal}) com origem “{origem.nome}”, "
                   f"estágio “{estagio.nome}” e responsável {resp.nome}.",
                   {"evento": "criado", "canal": canal})
    auditoria.registrar(db, usuario, "lead", lead.id, "criar", depois=auditoria.instantaneo(lead), ip=ip)
    if notificar_resp and (not usuario or usuario.id != resp.id):
        notificar(db, resp.id, "lead_atribuido", f"Novo lead atribuído a você: {lead.nome}", lead.id)
    return lead


def atualizar_lead(db: Session, lead: Lead, dados: dict, usuario: Usuario, ip: str | None) -> Lead:
    antes = auditoria.instantaneo(lead)
    if "origem_id" in dados and dados["origem_id"] != lead.origem_id:
        _validar_origem(db, dados["origem_id"])
    novo_email = dados.get("email", lead.email) if "email" in dados else lead.email
    novo_tel = dados.get("telefone", lead.telefone) if "telefone" in dados else lead.telefone
    if not novo_email and not novo_tel:
        raise invalido("Informe ao menos um contato: e-mail ou telefone.", {"email": "Informe e-mail ou telefone."})
    if not dados.get("forcar_duplicado") and (novo_email != lead.email or novo_tel != lead.telefone):
        dup = buscar_duplicados(db, novo_email if novo_email != lead.email else None,
                                novo_tel if novo_tel != lead.telefone else None, ignorar_id=lead.id)
        if dup:
            raise erro_duplicado(dup, usuario)
    if "nome" in dados and not dados["nome"]:
        raise invalido("Informe o nome.", {"nome": "Informe o nome."})
    etiquetas_antes = sorted(e.nome for e in lead.etiquetas)
    for k in CAMPOS_LEAD:
        if k in dados:
            setattr(lead, k, dados[k])
    if dados.get("consentimento") and not lead.consentimento_em:
        lead.consentimento_em = agora()
    elif dados.get("consentimento") is False:
        lead.consentimento_em = None
    if dados.get("etiqueta_ids") is not None:
        lead.etiquetas = _etiquetas(db, dados["etiqueta_ids"])
    db.flush()
    depois = auditoria.instantaneo(lead)
    mudancas = {k: {"de": antes.get(k), "para": depois.get(k)} for k in depois
                if antes.get(k) != depois.get(k) and k not in ("atualizado_em",)}
    etiquetas_depois = sorted(e.nome for e in lead.etiquetas)
    if etiquetas_antes != etiquetas_depois:
        mudancas["etiquetas"] = {"de": etiquetas_antes, "para": etiquetas_depois}
    if mudancas:
        rotulos = ", ".join(sorted(mudancas))
        evento_sistema(db, lead, usuario, f"Dados alterados: {rotulos}.", {"evento": "edicao", "mudancas": mudancas})
        auditoria.registrar(db, usuario, "lead", lead.id, "editar", antes, depois, ip=ip)
    return lead


def mudar_estagio(db: Session, lead: Lead, estagio_id: int, usuario: Usuario, ip: str | None,
                  motivo_perda_id: int | None = None, detalhe_perda: str | None = None,
                  valor_fechado: Decimal | None = None, fechado_em: date | None = None) -> Lead:
    novo = db.get(Estagio, estagio_id)
    if not novo or not novo.ativo:
        raise invalido("Estágio inválido.", {"estagio_id": "Estágio inválido."})
    atual = lead.estagio
    if novo.id == atual.id:
        return lead
    reabrindo = atual.tipo in ("ganho", "perdido")
    if reabrindo and usuario.perfil not in ("admin", "gestor"):
        raise proibido("Somente gestor ou administrador pode reabrir lead ganho ou perdido.")
    antes = auditoria.instantaneo(lead)
    detalhes: dict = {"evento": "estagio", "de": atual.nome, "para": novo.nome}
    if novo.tipo == "perdido":
        motivo = db.get(MotivoPerda, motivo_perda_id) if motivo_perda_id else None
        if not motivo or not motivo.ativo:
            raise invalido("Informe o motivo da perda.", {"motivo_perda_id": "Escolha o motivo da perda."})
        lead.motivo_perda_id = motivo.id
        lead.detalhe_perda = limpar_txt(detalhe_perda)
        lead.fechado_em = agora()
        lead.valor_fechado = None
        detalhes["motivo"] = motivo.nome
    elif novo.tipo == "ganho":
        if valor_fechado is None:
            raise invalido("Informe o valor fechado.", {"valor_fechado": "Informe o valor fechado."})
        lead.valor_fechado = valor_fechado
        quando = agora()
        if fechado_em:
            if fechado_em > hoje_local():
                raise invalido("A data de fechamento não pode ser futura.", {"fechado_em": "Data futura."})
            quando = inicio_dia(fechado_em) + timedelta(hours=12)
        lead.fechado_em = quando
        lead.motivo_perda_id = None
        lead.detalhe_perda = None
        detalhes["valor_fechado"] = float(valor_fechado)
    else:
        lead.motivo_perda_id = None
        lead.detalhe_perda = None
        lead.valor_fechado = None
        lead.fechado_em = None
    momento = agora()
    lead.estagio_id = novo.id
    lead.estagio = novo
    lead.estagio_desde = momento
    db.add(HistoricoEstagio(lead_id=lead.id, de_estagio_id=atual.id, para_estagio_id=novo.id,
                            usuario_id=usuario.id, data_hora=momento))
    txt = f"Estágio alterado de “{atual.nome}” para “{novo.nome}”"
    if reabrindo:
        txt = f"Lead reaberto: estágio “{atual.nome}” → “{novo.nome}”"
        detalhes["reabertura"] = True
    if "motivo" in detalhes:
        txt += f" (motivo: {detalhes['motivo']})"
    if "valor_fechado" in detalhes:
        valor = f"{detalhes['valor_fechado']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        txt += f" (valor fechado: R$ {valor})"
    evento_sistema(db, lead, usuario, txt + ".", detalhes)
    db.flush()
    auditoria.registrar(db, usuario, "lead", lead.id, "reabrir" if reabrindo else "mudar_estagio",
                        antes, auditoria.instantaneo(lead), ip=ip)
    return lead


def limpar_txt(s: str | None) -> str | None:
    return s.strip() or None if s else None


def atribuir(db: Session, lead: Lead, novo: Usuario, usuario: Usuario | None, ip: str | None,
             motivo: str = "manual") -> None:
    if lead.responsavel_id == novo.id:
        return
    anterior = lead.responsavel
    antes = {"responsavel_id": lead.responsavel_id}
    lead.responsavel_id = novo.id
    lead.responsavel = novo
    db.execute(Tarefa.__table__.update().where(and_(Tarefa.lead_id == lead.id, Tarefa.status == "pendente",
                                                    Tarefa.responsavel_id == anterior.id))
               .values(responsavel_id=novo.id))
    evento_sistema(db, lead, usuario, f"Responsável alterado de {anterior.nome} para {novo.nome} ({motivo}).",
                   {"evento": "responsavel", "de": anterior.nome, "para": novo.nome})
    auditoria.registrar(db, usuario, "lead", lead.id, "atribuir", antes, {"responsavel_id": novo.id}, ip=ip)
    if not usuario or usuario.id != novo.id:
        notificar(db, novo.id, "lead_atribuido", f"Novo lead atribuído a você: {lead.nome}", lead.id)


# ---------------------------------------------------------------- filtros
@dataclass
class FiltrosLead:
    q: str | None = None
    estagio_id: list[int] = field(default_factory=list)
    origem_id: list[int] = field(default_factory=list)
    responsavel_id: list[int] = field(default_factory=list)
    etiqueta_id: list[int] = field(default_factory=list)
    status: str | None = None  # aberto | ganho | perdido
    criado_de: date | None = None
    criado_ate: date | None = None
    contato_de: date | None = None
    contato_ate: date | None = None
    fechado_de: date | None = None
    fechado_ate: date | None = None
    valor_min: Decimal | None = None
    valor_max: Decimal | None = None
    parado: bool | None = None
    sem_proxima_acao: bool | None = None
    sem_contato: bool | None = None


def cond_parado(db: Session):
    dias = int(parametros.obter(db, "dias_lead_parado") or 7)
    limite = agora() - timedelta(days=dias)
    return and_(Estagio.tipo == "aberto",
                func.coalesce(Lead.ultimo_contato_em, Lead.criado_em) < limite)


def cond_tem_tarefa_pendente():
    return exists().where(Tarefa.lead_id == Lead.id, Tarefa.status == "pendente")


def aplicar_filtros(db: Session, q: Select, f: FiltrosLead) -> Select:
    q = q.join(Estagio, Lead.estagio_id == Estagio.id)
    if f.q:
        termo = f.q.strip()
        like = f"%{termo}%"
        conds = [Lead.nome.ilike(like), Lead.email.ilike(like), Lead.empresa.ilike(like)]
        digitos = "".join(c for c in termo if c.isdigit())
        if len(digitos) >= 4:
            conds.append(Lead.telefone.like(f"%{digitos}%"))
        q = q.where(or_(*conds))
    if f.estagio_id:
        q = q.where(Lead.estagio_id.in_(f.estagio_id))
    if f.origem_id:
        q = q.where(Lead.origem_id.in_(f.origem_id))
    if f.responsavel_id:
        q = q.where(Lead.responsavel_id.in_(f.responsavel_id))
    if f.etiqueta_id:
        q = q.where(exists().where(lead_etiqueta.c.lead_id == Lead.id,
                                   lead_etiqueta.c.etiqueta_id.in_(f.etiqueta_id)))
    if f.status in ("aberto", "ganho", "perdido"):
        q = q.where(Estagio.tipo == f.status)
    if f.criado_de:
        q = q.where(Lead.criado_em >= inicio_dia(f.criado_de))
    if f.criado_ate:
        q = q.where(Lead.criado_em < fim_dia(f.criado_ate))
    if f.contato_de:
        q = q.where(Lead.ultimo_contato_em >= inicio_dia(f.contato_de))
    if f.contato_ate:
        q = q.where(Lead.ultimo_contato_em < fim_dia(f.contato_ate))
    if f.fechado_de:
        q = q.where(Lead.fechado_em >= inicio_dia(f.fechado_de))
    if f.fechado_ate:
        q = q.where(Lead.fechado_em < fim_dia(f.fechado_ate))
    if f.valor_min is not None:
        q = q.where(Lead.valor_estimado >= f.valor_min)
    if f.valor_max is not None:
        q = q.where(Lead.valor_estimado <= f.valor_max)
    if f.parado:
        q = q.where(cond_parado(db))
    if f.sem_proxima_acao:
        q = q.where(Estagio.tipo == "aberto", ~cond_tem_tarefa_pendente())
    if f.sem_contato:
        q = q.where(Lead.ultimo_contato_em.is_(None))
    return q


ORDENACOES = {
    "criado_em": Lead.criado_em, "nome": Lead.nome, "valor_estimado": Lead.valor_estimado,
    "ultimo_contato_em": Lead.ultimo_contato_em, "empresa": Lead.empresa, "estagio": Estagio.ordem,
    "atualizado_em": Lead.atualizado_em, "fechado_em": Lead.fechado_em,
}


def enriquecer(db: Session, leads: list[Lead]) -> list[dict]:
    """Adiciona indicadores calculados: parado, sem próxima ação, próxima tarefa."""
    from .schemas import LeadSaida

    if not leads:
        return []
    ids = [lead.id for lead in leads]
    prox = dict(db.execute(select(Tarefa.lead_id, func.min(Tarefa.vencimento))
                           .where(Tarefa.lead_id.in_(ids), Tarefa.status == "pendente")
                           .group_by(Tarefa.lead_id)).all())
    dias = int(parametros.obter(db, "dias_lead_parado") or 7)
    limite = agora() - timedelta(days=dias)
    saida = []
    for lead in leads:
        d = LeadSaida.model_validate(lead).model_dump()
        aberto = lead.estagio.tipo == "aberto"
        p = prox.get(lead.id)
        if p is not None and p.tzinfo is None:
            p = p.replace(tzinfo=UTC)
        d["proxima_tarefa"] = p
        d["sem_proxima_acao"] = aberto and p is None
        d["parado"] = aberto and (lead.ultimo_contato_em or lead.criado_em) < limite
        saida.append(d)
    return saida
