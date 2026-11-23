import {
  createContext, useCallback, useContext, useEffect, useId, useRef, useState,
  type ReactNode,
} from "react";
import { ErroApi } from "./api";

/* ---------------------------------------------------------------- ícones */
const PATHS: Record<string, string> = {
  painel: "M3 13h8V3H3zm10 8h8V11h-8zM3 21h8v-6H3zm10-18v6h8V3z",
  leads: "M16 11a4 4 0 1 0-4-4 4 4 0 0 0 4 4zm-8 0a3 3 0 1 0-3-3 3 3 0 0 0 3 3zm0 2c-2.7 0-8 1.3-8 4v3h8v-3c0-1 .4-2.1 1.5-3A10 10 0 0 0 8 13zm8 0c-2.7 0-8 1.3-8 4v3h16v-3c0-2.7-5.3-4-8-4z",
  tarefas: "M9 11l3 3 8-8M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11",
  relatorios: "M4 20V10m6 10V4m6 16v-7m4 7H2",
  importar: "M12 3v12m0 0l-4-4m4 4l4-4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2",
  admin: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm7.4-3a7.4 7.4 0 0 0-.1-1.2l2-1.6-2-3.4-2.4 1a7 7 0 0 0-2-1.2L14.5 3h-5l-.4 2.6a7 7 0 0 0-2 1.2l-2.4-1-2 3.4 2 1.6a7.4 7.4 0 0 0 0 2.4l-2 1.6 2 3.4 2.4-1a7 7 0 0 0 2 1.2l.4 2.6h5l.4-2.6a7 7 0 0 0 2-1.2l2.4 1 2-3.4-2-1.6c.1-.4.1-.8.1-1.2z",
  busca: "M11 19a8 8 0 1 1 5.3-2L21 21.7",
  sino: "M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9m-4.3 13a2 2 0 0 1-3.4 0",
  mais: "M12 5v14M5 12h14",
  fechar: "M18 6L6 18M6 6l12 12",
  menu: "M3 6h18M3 12h18M3 18h18",
  kanban: "M4 4h4v16H4zM10 4h4v10h-4zM16 4h4v13h-4z",
  lista: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
  filtro: "M3 4h18l-7 8.5V19l-4 2v-8.5z",
  telefone: "M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z",
  email: "M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zm18 2l-10 7L2 6",
  reuniao: "M8 2v4m8-4v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z",
  nota: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zm0 0v6h6M8 13h8M8 17h5",
  sistema: "M12 8v4l3 2m6-2a9 9 0 1 1-18 0 9 9 0 0 1 18 0z",
  anexo: "M21.4 11.1l-9.2 9.2a6 6 0 0 1-8.5-8.5l9.2-9.2a4 4 0 0 1 5.7 5.7l-9.2 9.2a2 2 0 0 1-2.8-2.8l8.5-8.5",
  alerta: "M12 9v4m0 4h.01M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z",
  check: "M20 6L9 17l-5-5",
  baixar: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4m4-5l5 5 5-5m-5 5V3",
  editar: "M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7m-1.5-9.5a2.1 2.1 0 0 1 3 3L12 15l-4 1 1-4z",
  lixeira: "M3 6h18m-2 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2",
  voltar: "M19 12H5m7 7l-7-7 7-7",
  usuario: "M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2m8-10a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
  relogio: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zm0-14v4l3 3",
  estrela: "M12 2l3 6.9 7.5.7-5.7 5 1.7 7.4L12 18l-6.5 4 1.7-7.4-5.7-5 7.5-.7z",
  escudo: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
  sair: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4m7 14l5-5-5-5m5 5H9",
};

export function Icone({ nome, tam = 18, titulo }: { nome: keyof typeof PATHS | string; tam?: number; titulo?: string }) {
  return (
    <svg width={tam} height={tam} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden={titulo ? undefined : true} role={titulo ? "img" : undefined}>
      {titulo && <title>{titulo}</title>}
      <path d={PATHS[nome] ?? PATHS.sistema} />
    </svg>
  );
}

/* ---------------------------------------------------------------- toasts */
type Toast = { id: number; msg: string; tipo: "ok" | "erro" | "info" };
const ToastCtx = createContext<(msg: string, tipo?: Toast["tipo"]) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [itens, setItens] = useState<Toast[]>([]);
  const mostrar = useCallback((msg: string, tipo: Toast["tipo"] = "ok") => {
    const id = Date.now() + Math.random();
    setItens((t) => [...t, { id, msg, tipo }]);
    setTimeout(() => setItens((t) => t.filter((x) => x.id !== id)), tipo === "erro" ? 7000 : 4000);
  }, []);
  return (
    <ToastCtx.Provider value={mostrar}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {itens.map((t) => (
          <div key={t.id} className={`toast ${t.tipo}`}>
            <Icone nome={t.tipo === "erro" ? "alerta" : "check"} />
            <span>{t.msg}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}
export const useToast = () => useContext(ToastCtx);

export function mensagemErro(e: unknown): string {
  if (e instanceof Error) return e.message;
  return "Erro inesperado.";
}

/* ---------------------------------------------------------------- formulário */
export function Campo({ rotulo, erro, ajuda, obrigatorio, children, className, id: idExt }: {
  rotulo: string; erro?: string; ajuda?: string; obrigatorio?: boolean; children: (p: { id: string; "aria-invalid"?: boolean; "aria-describedby"?: string }) => ReactNode;
  className?: string; id?: string;
}) {
  const auto = useId();
  const id = idExt ?? auto;
  const desc = erro ? `${id}-erro` : ajuda ? `${id}-ajuda` : undefined;
  return (
    <div className={`campo ${className ?? ""}`}>
      <label htmlFor={id}>{rotulo}{obrigatorio && <span className="obrig" aria-hidden> *</span>}</label>
      {children({ id, "aria-invalid": erro ? true : undefined, "aria-describedby": desc })}
      {erro ? <span className="erro-campo" id={`${id}-erro`}>{erro}</span>
        : ajuda ? <span className="ajuda" id={`${id}-ajuda`}>{ajuda}</span> : null}
    </div>
  );
}

export function errosDeCampo(e: unknown): Record<string, string> {
  if (e instanceof ErroApi && e.detalhes && typeof e.detalhes === "object" && !Array.isArray(e.detalhes)) {
    const out: Record<string, string> = {};
    for (const [k, v] of Object.entries(e.detalhes)) if (typeof v === "string") out[k.split(".")[0]] = v;
    return out;
  }
  return {};
}

/* ---------------------------------------------------------------- modal */
export function Modal({ titulo, aoFechar, children, rodape, largo }: {
  titulo: string; aoFechar: () => void; children: ReactNode; rodape?: ReactNode; largo?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const idTitulo = useId();
  useEffect(() => {
    const anterior = document.activeElement as HTMLElement | null;
    const foco = ref.current?.querySelector<HTMLElement>("input:not([type=hidden]), select, textarea, button:not(.fechar-modal)");
    (foco ?? ref.current)?.focus();
    const tecla = (e: KeyboardEvent) => {
      if (e.key === "Escape") aoFechar();
      if (e.key === "Tab" && ref.current) {
        const f = ref.current.querySelectorAll<HTMLElement>("a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex='-1'])");
        if (!f.length) return;
        const [p, u] = [f[0], f[f.length - 1]];
        if (e.shiftKey && document.activeElement === p) { e.preventDefault(); u.focus(); }
        else if (!e.shiftKey && document.activeElement === u) { e.preventDefault(); p.focus(); }
      }
    };
    document.addEventListener("keydown", tecla);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", tecla);
      document.body.style.overflow = "";
      anterior?.focus?.();
    };
  }, [aoFechar]);
  return (
    <div className="modal-fundo" onMouseDown={(e) => e.target === e.currentTarget && aoFechar()}>
      <div className={`modal ${largo ? "largo" : ""}`} role="dialog" aria-modal="true" aria-labelledby={idTitulo} ref={ref} tabIndex={-1}>
        <div className="modal-cab">
          <h2 id={idTitulo}>{titulo}</h2>
          <button className="btn btn-fantasma btn-icone fechar-modal" onClick={aoFechar} aria-label="Fechar"><Icone nome="fechar" /></button>
        </div>
        <div className="modal-corpo">{children}</div>
        {rodape && <div className="modal-rodape">{rodape}</div>}
      </div>
    </div>
  );
}

export function Confirmar({ titulo, mensagem, textoOk = "Confirmar", perigo, aoConfirmar, aoFechar }: {
  titulo: string; mensagem: ReactNode; textoOk?: string; perigo?: boolean; aoConfirmar: () => Promise<void> | void; aoFechar: () => void;
}) {
  const [ocupado, setOcupado] = useState(false);
  return (
    <Modal titulo={titulo} aoFechar={aoFechar} rodape={<>
      <button className="btn" onClick={aoFechar}>Cancelar</button>
      <button className={`btn ${perigo ? "btn-perigo" : "btn-primario"}`} disabled={ocupado}
        onClick={async () => { setOcupado(true); try { await aoConfirmar(); } finally { setOcupado(false); } }}>{textoOk}</button>
    </>}>
      <div>{mensagem}</div>
    </Modal>
  );
}

/* ---------------------------------------------------------------- diversos */
export function Carregando({ texto = "Carregando…" }: { texto?: string }) {
  return <div className="carregando" role="status"><span className="giro" aria-hidden />{texto}</div>;
}

export function Vazio({ titulo, children, icone = "leads" }: { titulo: string; children?: ReactNode; icone?: string }) {
  return <div className="vazio"><Icone nome={icone} tam={36} /><p><strong>{titulo}</strong></p>{children}</div>;
}

export function Aviso({ tipo = "info", titulo, children }: { tipo?: "erro" | "alerta" | "info" | "ok"; titulo?: string; children?: ReactNode }) {
  return (
    <div className={`aviso aviso-${tipo}`} role={tipo === "erro" ? "alert" : undefined}>
      <Icone nome={tipo === "ok" ? "check" : "alerta"} />
      <div>{titulo && <strong>{titulo}</strong>}{children}</div>
    </div>
  );
}

/** Cor de texto legível sobre a cor do estágio. */
function contraste(hex?: string | null): string {
  if (!hex || !/^#[0-9a-f]{6}$/i.test(hex)) return "#fff";
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.4 ? "#0f172a" : "#fff";
}

export function SeloEstagio({ estagio }: { estagio: { nome: string; cor?: string | null } }) {
  const cor = estagio.cor ?? "#475569";
  return <span className="selo selo-estagio" style={{ background: cor, color: contraste(cor) }}>{estagio.nome}</span>;
}

export function Etiquetas({ itens }: { itens: { id: number; nome: string; cor: string }[] }) {
  if (!itens.length) return null;
  return <span className="flex" style={{ gap: 4, flexWrap: "wrap" }}>
    {itens.map((e) => <span key={e.id} className="etiqueta" style={{ ["--cor" as string]: e.cor }}>{e.nome}</span>)}
  </span>;
}

export function MultiSelecao({ rotulo, opcoes, valor, aoMudar }: {
  rotulo: string; opcoes: { id: number; nome: string }[]; valor: number[]; aoMudar: (v: number[]) => void;
}) {
  const [aberto, setAberto] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const id = useId();
  useEffect(() => {
    if (!aberto) return;
    const fora = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setAberto(false); };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setAberto(false);
    document.addEventListener("mousedown", fora);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", fora); document.removeEventListener("keydown", esc); };
  }, [aberto]);
  const resumo = valor.length === 0 ? "Todos" : valor.length === 1 ? opcoes.find((o) => o.id === valor[0])?.nome ?? "1 selecionado" : `${valor.length} selecionados`;
  return (
    <div className="campo multi" ref={ref}>
      <span className="rotulo" id={`${id}-r`}>{rotulo}</span>
      <button type="button" className="btn" aria-haspopup="true" aria-expanded={aberto} aria-labelledby={`${id}-r ${id}-v`} onClick={() => setAberto(!aberto)}>
        <span id={`${id}-v`}>{resumo}</span><span aria-hidden>▾</span>
      </button>
      {aberto && (
        <div className="multi-lista" role="group" aria-label={rotulo}>
          {opcoes.map((o) => (
            <label key={o.id}>
              <input type="checkbox" checked={valor.includes(o.id)}
                onChange={(e) => aoMudar(e.target.checked ? [...valor, o.id] : valor.filter((x) => x !== o.id))} />
              {o.nome}
            </label>
          ))}
          {valor.length > 0 && <button type="button" className="btn btn-pequeno btn-fantasma" onClick={() => aoMudar([])}>Limpar</button>}
        </div>
      )}
    </div>
  );
}

export function Paginacao({ pagina, tamanho, total, aoMudar }: { pagina: number; tamanho: number; total: number; aoMudar: (p: number) => void }) {
  const paginas = Math.max(1, Math.ceil(total / tamanho));
  const ini = total ? (pagina - 1) * tamanho + 1 : 0;
  return (
    <nav className="paginacao" aria-label="Paginação">
      <span>{ini}–{Math.min(pagina * tamanho, total)} de {total.toLocaleString("pt-BR")}</span>
      <span className="grupo-botoes">
        <button className="btn btn-pequeno" disabled={pagina <= 1} onClick={() => aoMudar(pagina - 1)}>Anterior</button>
        <span aria-current="page">Página {pagina} de {paginas}</span>
        <button className="btn btn-pequeno" disabled={pagina >= paginas} onClick={() => aoMudar(pagina + 1)}>Próxima</button>
      </span>
    </nav>
  );
}

export function Abas<T extends string>({ abas, atual, aoMudar }: { abas: { id: T; rotulo: string }[]; atual: T; aoMudar: (a: T) => void }) {
  return (
    <div className="abas" role="tablist">
      {abas.map((a) => (
        <button key={a.id} role="tab" aria-selected={a.id === atual} onClick={() => aoMudar(a.id)}>{a.rotulo}</button>
      ))}
    </div>
  );
}

/** Hook simples de carregamento assíncrono com recarga. */
export function useCarregar<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [dados, setDados] = useState<T | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [versao, setVersao] = useState(0);
  useEffect(() => {
    let vivo = true;
    setCarregando(true);
    fn().then((d) => { if (vivo) { setDados(d); setErro(null); } })
      .catch((e) => vivo && setErro(mensagemErro(e)))
      .finally(() => vivo && setCarregando(false));
    return () => { vivo = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, versao]);
  return { dados, erro, carregando, recarregar: () => setVersao((v) => v + 1), setDados };
}
