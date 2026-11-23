"""Esquemas de entrada e saída da API (validação com Pydantic)."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .utils import limpar, normalizar_email, normalizar_telefone, normalizar_uf

Perfil = Literal["admin", "gestor", "vendedor", "leitura"]
TipoInteracao = Literal["ligacao", "email", "reuniao", "nota"]
BaseLegal = Literal["consentimento", "legitimo_interesse", "procedimentos_preliminares_contrato",
                    "execucao_contrato"]


class Orm(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- autenticação ----------
class LoginEntrada(BaseModel):
    email: str
    senha: str
    codigo_2fa: str | None = None


class RecuperarSenhaEntrada(BaseModel):
    email: str


class RedefinirSenhaEntrada(BaseModel):
    token: str
    nova_senha: str


class TrocarSenhaEntrada(BaseModel):
    senha_atual: str
    nova_senha: str


class CodigoEntrada(BaseModel):
    codigo: str


class UsuarioResumo(Orm):
    id: int
    nome: str


class UsuarioSaida(Orm):
    id: int
    nome: str
    email: str
    perfil: str
    ativo: bool
    totp_ativo: bool
    uf_regiao: str | None = None
    criado_em: datetime
    ultimo_login_em: datetime | None = None


class UsuarioEntrada(BaseModel):
    nome: str = Field(min_length=2, max_length=150)
    email: str
    perfil: Perfil
    senha: str | None = None
    ativo: bool = True
    uf_regiao: str | None = None

    _email = field_validator("email")(lambda v: normalizar_email(v))
    _uf = field_validator("uf_regiao")(lambda v: normalizar_uf(v))


class UsuarioAtualizacao(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=150)
    email: str | None = None
    perfil: Perfil | None = None
    senha: str | None = None
    ativo: bool | None = None
    uf_regiao: str | None = None
    desativar_2fa: bool | None = None

    _email = field_validator("email")(lambda v: normalizar_email(v) if v else v)
    _uf = field_validator("uf_regiao")(lambda v: normalizar_uf(v))


# ---------- cadastros auxiliares ----------
class OrigemSaida(Orm):
    id: int
    nome: str
    ativa: bool


class OrigemEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=100)
    ativa: bool = True


class EstagioSaida(Orm):
    id: int
    nome: str
    ordem: int
    tipo: str
    ativo: bool
    cor: str | None = None


class EstagioEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=100)
    ordem: int
    tipo: Literal["aberto", "ganho", "perdido"] = "aberto"
    ativo: bool = True
    cor: str | None = None


class MotivoSaida(Orm):
    id: int
    nome: str
    ativo: bool


class MotivoEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=150)
    ativo: bool = True


class EtiquetaSaida(Orm):
    id: int
    nome: str
    cor: str


class EtiquetaEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=60)
    cor: str = Field(default="#64748b", pattern=r"^#[0-9a-fA-F]{6}$")


# ---------- leads ----------
class _CamposLead(BaseModel):
    @field_validator("email", check_fields=False)
    @classmethod
    def _v_email(cls, v):
        return normalizar_email(v)

    @field_validator("telefone", check_fields=False)
    @classmethod
    def _v_tel(cls, v):
        return normalizar_telefone(v)

    @field_validator("uf", check_fields=False)
    @classmethod
    def _v_uf(cls, v):
        return normalizar_uf(v)

    @field_validator("empresa", "cargo", "cidade", "interesse", "observacoes", check_fields=False)
    @classmethod
    def _v_texto(cls, v):
        return limpar(v)


class LeadEntrada(_CamposLead):
    nome: str = Field(min_length=1, max_length=200)
    email: str | None = None
    telefone: str | None = None
    origem_id: int
    empresa: str | None = Field(default=None, max_length=200)
    cargo: str | None = Field(default=None, max_length=120)
    cidade: str | None = Field(default=None, max_length=120)
    uf: str | None = None
    interesse: str | None = Field(default=None, max_length=200)
    valor_estimado: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    observacoes: str | None = None
    etiqueta_ids: list[int] = []
    responsavel_id: int | None = None
    base_legal: BaseLegal | None = None
    consentimento: bool = False
    forcar_duplicado: bool = False

    @field_validator("nome")
    @classmethod
    def _nome(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Informe o nome.")
        return v

    @model_validator(mode="after")
    def _contato(self):
        if not self.email and not self.telefone:
            raise ValueError("Informe ao menos um contato: e-mail ou telefone.")
        return self


class LeadAtualizacao(_CamposLead):
    nome: str | None = Field(default=None, min_length=1, max_length=200)
    email: str | None = None
    telefone: str | None = None
    origem_id: int | None = None
    empresa: str | None = None
    cargo: str | None = None
    cidade: str | None = None
    uf: str | None = None
    interesse: str | None = None
    valor_estimado: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    observacoes: str | None = None
    etiqueta_ids: list[int] | None = None
    base_legal: BaseLegal | None = None
    consentimento: bool | None = None
    forcar_duplicado: bool = False


class EstagioResumo(Orm):
    id: int
    nome: str
    tipo: str
    ordem: int
    cor: str | None = None


class NomeResumo(Orm):
    id: int
    nome: str


class LeadSaida(Orm):
    id: int
    nome: str
    email: str | None
    telefone: str | None
    empresa: str | None
    cargo: str | None
    cidade: str | None
    uf: str | None
    interesse: str | None
    valor_estimado: Decimal | None
    observacoes: str | None
    origem: NomeResumo
    estagio: EstagioResumo
    responsavel: NomeResumo
    motivo_perda: NomeResumo | None
    detalhe_perda: str | None
    valor_fechado: Decimal | None
    fechado_em: datetime | None
    utm_source: str | None
    utm_medium: str | None
    utm_campaign: str | None
    base_legal: str | None
    consentimento_em: datetime | None
    criado_em: datetime
    atualizado_em: datetime
    ultimo_contato_em: datetime | None
    primeiro_contato_em: datetime | None
    estagio_desde: datetime
    anonimizado_em: datetime | None
    etiquetas: list[EtiquetaSaida]
    parado: bool = False
    sem_proxima_acao: bool = False
    proxima_tarefa: datetime | None = None


class Pagina(BaseModel):
    itens: list
    total: int
    pagina: int
    tamanho: int


class MudarEstagioEntrada(BaseModel):
    estagio_id: int
    motivo_perda_id: int | None = None
    detalhe_perda: str | None = None
    valor_fechado: Decimal | None = Field(default=None, ge=0)
    fechado_em: date | None = None


class AtribuirEntrada(BaseModel):
    responsavel_id: int | None = None
    automatico: bool = False


class AtribuirLoteEntrada(BaseModel):
    lead_ids: list[int] = Field(min_length=1, max_length=1000)
    responsavel_id: int | None = None
    automatico: bool = False


class MesclarEntrada(BaseModel):
    principal_id: int
    secundario_id: int


# ---------- interações, tarefas ----------
class InteracaoEntrada(BaseModel):
    tipo: TipoInteracao
    data_hora: datetime | None = None
    resumo: str = Field(min_length=1, max_length=5000)
    resultado: str | None = Field(default=None, max_length=2000)


class AnexoSaida(Orm):
    id: int
    nome: str
    tamanho: int
    tipo_mime: str | None
    criado_em: datetime


class InteracaoSaida(Orm):
    id: int
    lead_id: int
    tipo: str
    data_hora: datetime
    resumo: str
    resultado: str | None
    dados: dict | None
    usuario: UsuarioResumo | None
    anexos: list[AnexoSaida] = []


class EnviarEmailEntrada(BaseModel):
    assunto: str = Field(min_length=1, max_length=200)
    corpo: str = Field(min_length=1, max_length=20000)


class TarefaEntrada(BaseModel):
    lead_id: int
    titulo: str = Field(min_length=1, max_length=200)
    descricao: str | None = None
    vencimento: datetime
    responsavel_id: int | None = None


class TarefaAtualizacao(BaseModel):
    titulo: str | None = Field(default=None, min_length=1, max_length=200)
    descricao: str | None = None
    vencimento: datetime | None = None
    status: Literal["pendente", "concluida", "cancelada"] | None = None
    responsavel_id: int | None = None


class LeadMini(Orm):
    id: int
    nome: str
    empresa: str | None


class TarefaSaida(Orm):
    id: int
    lead_id: int
    titulo: str
    descricao: str | None
    vencimento: datetime
    status: str
    concluida_em: datetime | None
    criado_em: datetime
    responsavel: UsuarioResumo
    lead: LeadMini


class VisaoEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=100)
    filtros: dict


class VisaoSaida(Orm):
    id: int
    nome: str
    filtros: dict


class ModeloEmailEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=100)
    assunto: str = Field(min_length=1, max_length=200)
    corpo: str = Field(min_length=1)
    ativo: bool = True


class ModeloEmailSaida(Orm):
    id: int
    nome: str
    assunto: str
    corpo: str
    ativo: bool


class RegraEntrada(BaseModel):
    origem_id: int | None = None
    uf: str | None = None
    usuario_id: int
    prioridade: int = 100
    ativa: bool = True

    _uf = field_validator("uf")(lambda v: normalizar_uf(v))

    @model_validator(mode="after")
    def _criterio(self):
        if not self.origem_id and not self.uf:
            raise ValueError("Informe a origem e/ou a UF da regra.")
        return self


class RegraSaida(Orm):
    id: int
    origem_id: int | None
    uf: str | None
    usuario_id: int
    prioridade: int
    ativa: bool


class ChaveApiEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=100)
    origem_id: int


class ChaveApiSaida(Orm):
    id: int
    nome: str
    prefixo: str
    origem: NomeResumo
    ativa: bool
    criado_em: datetime
    ultimo_uso_em: datetime | None


class ParametrosEntrada(BaseModel):
    dias_lead_parado: int | None = Field(default=None, ge=1, le=365)
    atribuicao_automatica: bool | None = None
    notificar_por_email: bool | None = None
