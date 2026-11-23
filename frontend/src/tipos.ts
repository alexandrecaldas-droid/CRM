export type Perfil = "admin" | "gestor" | "vendedor" | "leitura";
export interface Usuario {
  id: number; nome: string; email: string; perfil: Perfil; ativo: boolean; totp_ativo: boolean;
  uf_regiao?: string | null; criado_em: string; ultimo_login_em?: string | null;
}
export interface Ref { id: number; nome: string }
export interface Estagio { id: number; nome: string; ordem: number; tipo: "aberto" | "ganho" | "perdido"; ativo: boolean; cor?: string | null }
export interface Origem { id: number; nome: string; ativa: boolean }
export interface Motivo { id: number; nome: string; ativo: boolean }
export interface Etiqueta { id: number; nome: string; cor: string }
export interface Lead {
  id: number; nome: string; email: string | null; telefone: string | null; empresa: string | null;
  cargo: string | null; cidade: string | null; uf: string | null; interesse: string | null;
  valor_estimado: string | null; observacoes: string | null; origem: Ref;
  estagio: { id: number; nome: string; tipo: string; ordem: number; cor?: string | null };
  responsavel: Ref; motivo_perda: Ref | null; detalhe_perda: string | null; valor_fechado: string | null;
  fechado_em: string | null; utm_source: string | null; utm_medium: string | null; utm_campaign: string | null;
  base_legal: string | null; consentimento_em: string | null; criado_em: string; atualizado_em: string;
  ultimo_contato_em: string | null; primeiro_contato_em: string | null; estagio_desde: string;
  anonimizado_em: string | null; etiquetas: Etiqueta[]; parado: boolean; sem_proxima_acao: boolean;
  proxima_tarefa: string | null;
}
export interface Pagina<T> { itens: T[]; total: number; pagina: number; tamanho: number }
export interface Interacao {
  id: number; lead_id: number; tipo: string; data_hora: string; resumo: string; resultado: string | null;
  dados: any; usuario: Ref | null; anexos: { id: number; nome: string; tamanho: number }[];
}
export interface Tarefa {
  id: number; lead_id: number; titulo: string; descricao: string | null; vencimento: string; status: string;
  concluida_em: string | null; criado_em: string; responsavel: Ref; lead: { id: number; nome: string; empresa: string | null };
}
export type Filtros = Record<string, any>;
