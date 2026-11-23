export class ErroApi extends Error {
  codigo: string;
  status: number;
  detalhes: any;
  constructor(status: number, codigo: string, mensagem: string, detalhes?: any) {
    super(mensagem);
    this.status = status;
    this.codigo = codigo;
    this.detalhes = detalhes;
  }
}

const CHAVE = "leads.token";
let token: string | null = (() => {
  try { return sessionStorage.getItem(CHAVE) ?? localStorage.getItem(CHAVE); } catch { return null; }
})();
let aoExpirar: (() => void) | null = null;

export function definirToken(t: string | null, lembrar = false) {
  token = t;
  try {
    sessionStorage.removeItem(CHAVE);
    localStorage.removeItem(CHAVE);
    if (t) (lembrar ? localStorage : sessionStorage).setItem(CHAVE, t);
  } catch { /* armazenamento indisponível */ }
}
export const obterToken = () => token;
export function quandoExpirar(fn: () => void) { aoExpirar = fn; }

type Params = Record<string, unknown>;

export function qs(params?: Params): string {
  if (!params) return "";
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "" || v === false) continue;
    if (Array.isArray(v)) v.forEach((x) => u.append(k, String(x)));
    else u.append(k, String(v));
  }
  const s = u.toString();
  return s ? `?${s}` : "";
}

async function req<T>(metodo: string, url: string, corpo?: unknown, params?: Params): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (corpo instanceof FormData) body = corpo;
  else if (corpo !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(corpo);
  }
  let r: Response;
  try {
    r = await fetch(`/api${url}${qs(params)}`, { method: metodo, headers, body });
  } catch {
    throw new ErroApi(0, "rede", "Sem conexão com o servidor. Verifique sua internet e tente novamente.");
  }
  if (r.status === 401 && token && !url.startsWith("/auth/login")) {
    definirToken(null);
    aoExpirar?.();
  }
  const tipo = r.headers.get("content-type") || "";
  const dados = tipo.includes("application/json") ? await r.json() : null;
  if (!r.ok) {
    const e = dados?.erro;
    throw new ErroApi(r.status, e?.codigo ?? "erro", e?.mensagem ?? "Ocorreu um erro inesperado.", e?.detalhes);
  }
  return dados as T;
}

export const api = {
  get: <T = any>(url: string, params?: Params) => req<T>("GET", url, undefined, params),
  post: <T = any>(url: string, corpo?: unknown) => req<T>("POST", url, corpo ?? {}),
  put: <T = any>(url: string, corpo?: unknown) => req<T>("PUT", url, corpo),
  patch: <T = any>(url: string, corpo?: unknown) => req<T>("PATCH", url, corpo),
  del: <T = any>(url: string) => req<T>("DELETE", url),
};

/** Baixa um arquivo autenticado (exportações, anexos, relatórios de erro). */
export async function baixar(url: string, params?: Params) {
  const r = await fetch(`/api${url}${qs(params)}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!r.ok) {
    const d = await r.json().catch(() => null);
    throw new ErroApi(r.status, d?.erro?.codigo ?? "erro", d?.erro?.mensagem ?? "Falha no download.");
  }
  const disp = r.headers.get("content-disposition") || "";
  const nome = decodeURIComponent(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disp)?.[1] ?? "arquivo");
  const blob = await r.blob();
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = nome;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 2000);
}
