export const TZ = "America/Sao_Paulo";

const fData = new Intl.DateTimeFormat("pt-BR", { timeZone: TZ, day: "2-digit", month: "2-digit", year: "numeric" });
const fDataHora = new Intl.DateTimeFormat("pt-BR", { timeZone: TZ, day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
const fMoeda = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const fMoedaCurta = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", notation: "compact", maximumFractionDigits: 1 });
const fNum = new Intl.NumberFormat("pt-BR");

export const data = (s?: string | null) => (s ? fData.format(new Date(s)) : "—");
export const dataHora = (s?: string | null) => (s ? fDataHora.format(new Date(s)) : "—");
export const moeda = (v?: string | number | null) => (v === null || v === undefined || v === "" ? "—" : fMoeda.format(Number(v)));
export const moedaCurta = (v?: number | null) => (v ? fMoedaCurta.format(v) : "R$ 0");
export const numero = (v?: number | null) => (v === null || v === undefined ? "—" : fNum.format(v));

export function relativo(s?: string | null): string {
  if (!s) return "nunca";
  const diff = (Date.now() - new Date(s).getTime()) / 1000;
  const fut = diff < 0;
  const a = Math.abs(diff);
  const f = (n: number, u: string) => (fut ? `em ${n} ${u}` : `há ${n} ${u}`);
  if (a < 60) return fut ? "em instantes" : "agora";
  if (a < 3600) return f(Math.round(a / 60), "min");
  if (a < 86400) return f(Math.round(a / 3600), "h");
  const d = Math.round(a / 86400);
  return f(d, d === 1 ? "dia" : "dias");
}

export function telefone(t?: string | null): string {
  if (!t) return "—";
  const m = /^\+55(\d{2})(\d{4,5})(\d{4})$/.exec(t);
  return m ? `(${m[1]}) ${m[2]}-${m[3]}` : t;
}

export function duracao(seg: number): string {
  const d = Math.floor(seg / 86400), h = Math.floor((seg % 86400) / 3600), m = Math.floor((seg % 3600) / 60);
  if (d) return `${d}d ${h}h`;
  if (h) return `${h}h ${m}min`;
  return `${m} min`;
}

export function horas(h?: number | null): string {
  if (h === null || h === undefined) return "—";
  if (h < 1) return `${Math.round(h * 60)} min`;
  if (h < 48) return `${h.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} h`;
  return `${(h / 24).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} dias`;
}

/** Data local (fuso de São Paulo) no formato yyyy-mm-dd, para campos <input type=date>. */
export function hojeISO(deslocDias = 0): string {
  const d = new Date(Date.now() + deslocDias * 86400000);
  const p = new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" });
  return p.format(d);
}

/** Converte valor de <input type=datetime-local> (horário de São Paulo) para ISO UTC. */
export function localParaISO(v: string): string {
  // America/Sao_Paulo não tem horário de verão desde 2019: UTC-3 fixo.
  return new Date(`${v}:00-03:00`).toISOString();
}

export function isoParaLocal(iso: string): string {
  const d = new Date(new Date(iso).getTime() - 3 * 3600000);
  return d.toISOString().slice(0, 16);
}

export const TIPOS_INTERACAO: Record<string, string> = {
  ligacao: "Ligação", email: "E-mail", reuniao: "Reunião", nota: "Nota interna", sistema: "Sistema",
};
export const PERFIS: Record<string, string> = {
  admin: "Administrador", gestor: "Gestor", vendedor: "Vendedor", leitura: "Somente leitura",
};
export const BASES_LEGAIS: Record<string, string> = {
  consentimento: "Consentimento",
  legitimo_interesse: "Legítimo interesse",
  procedimentos_preliminares_contrato: "Procedimentos preliminares de contrato",
  execucao_contrato: "Execução de contrato",
};
export const UFS = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split(" ");

/** "1.500,50" → "1500.50"; "1500.5" → "1500.5"; vazio → null. */
export function paraDecimal(v: string | number | null | undefined): string | null {
  if (v === null || v === undefined || v === "") return null;
  const s = String(v).trim();
  return s.includes(",") ? s.replace(/\./g, "").replace(",", ".") : s;
}
