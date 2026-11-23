import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, definirToken, obterToken, quandoExpirar } from "./api";
import type { Estagio, Etiqueta, Motivo, Origem, Usuario } from "./tipos";

interface AuthCtx {
  usuario: Usuario | null;
  carregando: boolean;
  entrar: (email: string, senha: string, codigo?: string, lembrar?: boolean) => Promise<void>;
  sair: () => Promise<void>;
  atualizar: () => Promise<void>;
}
const Auth = createContext<AuthCtx>(null as never);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [carregando, setCarregando] = useState(true);
  const atualizar = useCallback(async () => {
    if (!obterToken()) { setUsuario(null); return; }
    try { setUsuario(await api.get<Usuario>("/auth/me")); } catch { setUsuario(null); }
  }, []);
  useEffect(() => {
    quandoExpirar(() => setUsuario(null));
    atualizar().finally(() => setCarregando(false));
  }, [atualizar]);
  const entrar = async (email: string, senha: string, codigo?: string, lembrar?: boolean) => {
    const r = await api.post<{ token: string; usuario: Usuario }>("/auth/login", { email, senha, codigo_2fa: codigo || null });
    definirToken(r.token, lembrar);
    setUsuario(r.usuario);
  };
  const sair = async () => {
    try { await api.post("/auth/logout"); } catch { /* sessão já inválida */ }
    definirToken(null);
    setUsuario(null);
  };
  return <Auth.Provider value={{ usuario, carregando, entrar, sair, atualizar }}>{children}</Auth.Provider>;
}
export const useAuth = () => useContext(Auth);

/** Permissões do perfil — espelham as regras do servidor (que é quem de fato decide). */
export function usePode() {
  const { usuario } = useAuth();
  const p = usuario?.perfil;
  return {
    editar: p === "admin" || p === "gestor" || p === "vendedor",
    gerir: p === "admin" || p === "gestor",
    admin: p === "admin",
    verTodos: p !== "vendedor",
    exportar: p === "admin" || p === "gestor",
  };
}

interface Cadastros {
  origens: Origem[]; estagios: Estagio[]; motivos: Motivo[]; etiquetas: Etiqueta[]; usuarios: Usuario[];
  parametros: { dias_lead_parado: number; atribuicao_automatica: boolean; notificar_por_email: boolean };
  pronto: boolean;
  recarregar: () => Promise<void>;
}
const CadCtx = createContext<Cadastros>(null as never);

export function CadastrosProvider({ children }: { children: ReactNode }) {
  const { usuario } = useAuth();
  const [estado, setEstado] = useState<Omit<Cadastros, "recarregar">>({
    origens: [], estagios: [], motivos: [], etiquetas: [], usuarios: [], pronto: false,
    parametros: { dias_lead_parado: 7, atribuicao_automatica: true, notificar_por_email: true },
  });
  const recarregar = useCallback(async () => {
    const [origens, estagios, motivos, etiquetas, usuarios, parametros] = await Promise.all([
      api.get("/origens"), api.get("/estagios"), api.get("/motivos-perda"), api.get("/etiquetas"),
      api.get("/usuarios"), api.get("/parametros"),
    ]);
    setEstado({ origens, estagios, motivos, etiquetas, usuarios, parametros, pronto: true });
  }, []);
  useEffect(() => { if (usuario) recarregar().catch(() => {}); }, [usuario, recarregar]);
  const valor = useMemo(() => ({ ...estado, recarregar }), [estado, recarregar]);
  return <CadCtx.Provider value={valor}>{children}</CadCtx.Provider>;
}
export const useCadastros = () => useContext(CadCtx);
