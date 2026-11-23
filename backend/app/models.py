"""Modelo de dados (seção 4 da especificação) + tabelas de apoio."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, UTCDateTime, agora

PERFIS = ("admin", "gestor", "vendedor", "leitura")
TIPOS_ESTAGIO = ("aberto", "ganho", "perdido")
TIPOS_INTERACAO = ("ligacao", "email", "reuniao", "nota", "sistema")
STATUS_TAREFA = ("pendente", "concluida", "cancelada")
BASES_LEGAIS = (
    "consentimento",
    "legitimo_interesse",
    "procedimentos_preliminares_contrato",
    "execucao_contrato",
)


class Usuario(Base):
    __tablename__ = "usuario"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    perfil: Mapped[str] = mapped_column(String(20), default="vendedor")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    totp_secret: Mapped[str | None] = mapped_column(String(64))
    totp_ativo: Mapped[bool] = mapped_column(Boolean, default=False)
    uf_regiao: Mapped[str | None] = mapped_column(String(2))
    criado_em: Mapped[datetime] = mapped_column(UTCDateTime, default=agora)
    ultimo_login_em: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Sessao(Base):
    __tablename__ = "sessao"
    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"))
    criado_em: Mapped[datetime] = mapped_column(UTCDateTime, default=agora)
    expira_em: Mapped[datetime] = mapped_column(UTCDateTime)
    ip: Mapped[str | None] = mapped_column(String(64))
    usuario: Mapped[Usuario] = relationship()


class ResetSenha(Base):
    __tablename__ = "reset_senha"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expira_em: Mapped[datetime] = mapped_column(UTCDateTime)
    usado_em: Mapped[datetime | None] = mapped_column(UTCDateTime)


class TentativaLogin(Base):
    __tablename__ = "tentativa_login"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), index=True)
    ip: Mapped[str | None] = mapped_column(String(64))
    sucesso: Mapped[bool] = mapped_column(Boolean)
    data_hora: Mapped[datetime] = mapped_column(UTCDateTime, default=agora, index=True)


class Origem(Base):
    __tablename__ = "origem"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100), unique=True)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)


class Estagio(Base):
    __tablename__ = "estagio"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100))
    ordem: Mapped[int] = mapped_column(Integer)
    tipo: Mapped[str] = mapped_column(String(10), default="aberto")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    cor: Mapped[str | None] = mapped_column(String(9))


class MotivoPerda(Base):
    __tablename__ = "motivo_perda"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(150), unique=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class Etiqueta(Base):
    __tablename__ = "etiqueta"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(60), unique=True)
    cor: Mapped[str] = mapped_column(String(9), default="#64748b")


lead_etiqueta = Table(
    "lead_etiqueta",
    Base.metadata,
    Column("lead_id", ForeignKey("lead.id", ondelete="CASCADE"), primary_key=True),
    Column("etiqueta_id", ForeignKey("etiqueta.id", ondelete="CASCADE"), primary_key=True),
)


class Lead(Base):
    __tablename__ = "lead"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(254), index=True)
    telefone: Mapped[str | None] = mapped_column(String(20), index=True)
    empresa: Mapped[str | None] = mapped_column(String(200), index=True)
    cargo: Mapped[str | None] = mapped_column(String(120))
    cidade: Mapped[str | None] = mapped_column(String(120))
    uf: Mapped[str | None] = mapped_column(String(2))
    interesse: Mapped[str | None] = mapped_column(String(200))
    valor_estimado: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    observacoes: Mapped[str | None] = mapped_column(Text)
    origem_id: Mapped[int] = mapped_column(ForeignKey("origem.id"), index=True)
    estagio_id: Mapped[int] = mapped_column(ForeignKey("estagio.id"), index=True)
    responsavel_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), index=True)
    motivo_perda_id: Mapped[int | None] = mapped_column(ForeignKey("motivo_perda.id"))
    detalhe_perda: Mapped[str | None] = mapped_column(Text)
    valor_fechado: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    fechado_em: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True)
    utm_source: Mapped[str | None] = mapped_column(String(150))
    utm_medium: Mapped[str | None] = mapped_column(String(150))
    utm_campaign: Mapped[str | None] = mapped_column(String(150))
    base_legal: Mapped[str | None] = mapped_column(String(40))
    consentimento_em: Mapped[datetime | None] = mapped_column(UTCDateTime)
    criado_em: Mapped[datetime] = mapped_column(UTCDateTime, default=agora, index=True)
    atualizado_em: Mapped[datetime] = mapped_column(UTCDateTime, default=agora, onupdate=agora)
    ultimo_contato_em: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True)
    primeiro_contato_em: Mapped[datetime | None] = mapped_column(UTCDateTime)
    estagio_desde: Mapped[datetime] = mapped_column(UTCDateTime, default=agora)
    excluido_em: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True)
    anonimizado_em: Mapped[datetime | None] = mapped_column(UTCDateTime)
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))

    origem: Mapped[Origem] = relationship(lazy="joined")
    estagio: Mapped[Estagio] = relationship(lazy="joined")
    responsavel: Mapped[Usuario] = relationship(foreign_keys=[responsavel_id], lazy="joined")
    motivo_perda: Mapped[MotivoPerda | None] = relationship(lazy="joined")
    etiquetas: Mapped[list[Etiqueta]] = relationship(secondary=lead_etiqueta, lazy="selectin")

    __table_args__ = (Index("ix_lead_nome", "nome"),)


class HistoricoEstagio(Base):
    __tablename__ = "historico_estagio"
    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("lead.id", ondelete="CASCADE"), index=True)
    de_estagio_id: Mapped[int | None] = mapped_column(ForeignKey("estagio.id"))
    para_estagio_id: Mapped[int] = mapped_column(ForeignKey("estagio.id"), index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    data_hora: Mapped[datetime] = mapped_column(UTCDateTime, default=agora, index=True)


class Interacao(Base):
    __tablename__ = "interacao"
    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("lead.id", ondelete="CASCADE"), index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    tipo: Mapped[str] = mapped_column(String(10))
    data_hora: Mapped[datetime] = mapped_column(UTCDateTime, default=agora, index=True)
    resumo: Mapped[str] = mapped_column(Text)
    resultado: Mapped[str | None] = mapped_column(Text)
    dados: Mapped[dict | None] = mapped_column(JSON)
    criado_em: Mapped[datetime] = mapped_column(UTCDateTime, default=agora)
    usuario: Mapped[Usuario | None] = relationship(lazy="joined")
    anexos: Mapped[list["Anexo"]] = relationship(lazy="selectin", back_populates="interacao")


class Tarefa(Base):
    __tablename__ = "tarefa"
    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("lead.id", ondelete="CASCADE"), index=True)
    responsavel_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), index=True)
    titulo: Mapped[str] = mapped_column(String(200))
    descricao: Mapped[str | None] = mapped_column(Text)
    vencimento: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    status: Mapped[str] = mapped_column(String(12), default="pendente", index=True)
    concluida_em: Mapped[datetime | None] = mapped_column(UTCDateTime)
    criado_em: Mapped[datetime] = mapped_column(UTCDateTime, default=agora)
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    lead: Mapped[Lead] = relationship(lazy="joined")
    responsavel: Mapped[Usuario] = relationship(foreign_keys=[responsavel_id], lazy="joined")


class Anexo(Base):
    __tablename__ = "anexo"
    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("lead.id", ondelete="CASCADE"), index=True)
    interacao_id: Mapped[int | None] = mapped_column(ForeignKey("interacao.id", ondelete="SET NULL"))
    nome: Mapped[str] = mapped_column(String(255))
    caminho: Mapped[str] = mapped_column(String(500))
    tamanho: Mapped[int] = mapped_column(Integer)
    tipo_mime: Mapped[str | None] = mapped_column(String(120))
    enviado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    criado_em: Mapped[datetime] = mapped_column(UTCDateTime, default=agora)
    interacao: Mapped[Interacao | None] = relationship(back_populates="anexos")


class Auditoria(Base):
    """Somente inclusão. Nenhuma rota edita ou exclui registros desta tabela."""

    __tablename__ = "auditoria"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), index=True)
    entidade: Mapped[str] = mapped_column(String(40), index=True)
    entidade_id: Mapped[str | None] = mapped_column(String(40))
    acao: Mapped[str] = mapped_column(String(30), index=True)
    antes: Mapped[dict | None] = mapped_column(JSON)
    depois: Mapped[dict | None] = mapped_column(JSON)
    ip: Mapped[str | None] = mapped_column(String(64))
    data_hora: Mapped[datetime] = mapped_column(UTCDateTime, default=agora, index=True)
    usuario: Mapped[Usuario | None] = relationship(lazy="joined")


class Configuracao(Base):
    __tablename__ = "configuracao"
    chave: Mapped[str] = mapped_column(String(60), primary_key=True)
    valor: Mapped[dict | list | str | int | bool | None] = mapped_column(JSON)


class VisaoSalva(Base):
    __tablename__ = "visao_salva"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"), index=True)
    nome: Mapped[str] = mapped_column(String(100))
    filtros: Mapped[dict] = mapped_column(JSON)
    criado_em: Mapped[datetime] = mapped_column(UTCDateTime, default=agora)


class Notificacao(Base):
    __tablename__ = "notificacao"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(30))
    mensagem: Mapped[str] = mapped_column(String(500))
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("lead.id", ondelete="CASCADE"))
    tarefa_id: Mapped[int | None] = mapped_column(ForeignKey("tarefa.id", ondelete="CASCADE"))
    lida: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    chave_dedupe: Mapped[str | None] = mapped_column(String(120), unique=True)
    criado_em: Mapped[datetime] = mapped_column(UTCDateTime, default=agora)


class Job(Base):
    """Fila simples em banco consumida pelo worker (importações, e-mails, lembretes)."""

    __tablename__ = "job"
    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(String(30))
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(15), default="pendente", index=True)
    tentativas: Mapped[int] = mapped_column(Integer, default=0)
    erro: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(UTCDateTime, default=agora)
    executar_apos: Mapped[datetime] = mapped_column(UTCDateTime, default=agora)
    concluido_em: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Importacao(Base):
    __tablename__ = "importacao"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    nome_arquivo: Mapped[str] = mapped_column(String(255))
    caminho: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="rascunho")
    colunas: Mapped[list] = mapped_column(JSON, default=list)
    mapeamento: Mapped[dict | None] = mapped_column(JSON)
    opcoes: Mapped[dict | None] = mapped_column(JSON)
    total: Mapped[int] = mapped_column(Integer, default=0)
    importados: Mapped[int] = mapped_column(Integer, default=0)
    atualizados: Mapped[int] = mapped_column(Integer, default=0)
    ignorados: Mapped[int] = mapped_column(Integer, default=0)
    rejeitados: Mapped[int] = mapped_column(Integer, default=0)
    erros: Mapped[list] = mapped_column(JSON, default=list)
    criado_em: Mapped[datetime] = mapped_column(UTCDateTime, default=agora)
    concluido_em: Mapped[datetime | None] = mapped_column(UTCDateTime)


class ChaveApi(Base):
    __tablename__ = "chave_api"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100))
    prefixo: Mapped[str] = mapped_column(String(12), index=True)
    chave_hash: Mapped[str] = mapped_column(String(64), unique=True)
    origem_id: Mapped[int] = mapped_column(ForeignKey("origem.id"))
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(UTCDateTime, default=agora)
    ultimo_uso_em: Mapped[datetime | None] = mapped_column(UTCDateTime)
    origem: Mapped[Origem] = relationship(lazy="joined")


class ModeloEmail(Base):
    __tablename__ = "modelo_email"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100))
    assunto: Mapped[str] = mapped_column(String(200))
    corpo: Mapped[str] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class RegraAtribuicao(Base):
    __tablename__ = "regra_atribuicao"
    id: Mapped[int] = mapped_column(primary_key=True)
    origem_id: Mapped[int | None] = mapped_column(ForeignKey("origem.id"))
    uf: Mapped[str | None] = mapped_column(String(2))
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    prioridade: Mapped[int] = mapped_column(Integer, default=100)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
