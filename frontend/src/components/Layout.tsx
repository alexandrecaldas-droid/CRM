import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth, usePode } from "../contexto";
import { PERFIS, relativo } from "../formato";
import { Icone } from "../ui";

interface Notif { id: number; mensagem: string; lead_id: number | null; lida: boolean; criado_em: string }

function iniciais(nome: string) {
  return nome.split(" ").filter(Boolean).slice(0, 2).map((p) => p[0]).join("").toUpperCase();
}

export default function Layout() {
  const { usuario, sair } = useAuth();
  const pode = usePode();
  const nav = useNavigate();
  const loc = useLocation();
  const [menuAberto, setMenuAberto] = useState(false);
  const [busca, setBusca] = useState("");
  const [tarefas, setTarefas] = useState({ atrasadas: 0, hoje: 0 });
  const [notifs, setNotifs] = useState<{ nao_lidas: number; itens: Notif[] }>({ nao_lidas: 0, itens: [] });
  const [verNotifs, setVerNotifs] = useState(false);
  const [verUsuario, setVerUsuario] = useState(false);
  const notifRef = useRef<HTMLDivElement>(null);
  const userRef = useRef<HTMLDivElement>(null);

  const atualizarContadores = () => {
    api.get("/notificacoes").then(setNotifs).catch(() => {});
    api.get("/tarefas/resumo").then(setTarefas).catch(() => {});
  };
  useEffect(() => {
    atualizarContadores();
    const t = setInterval(atualizarContadores, 60000);
    return () => clearInterval(t);
  }, []);
  useEffect(() => { setMenuAberto(false); setVerNotifs(false); setVerUsuario(false); }, [loc.pathname]);
  useEffect(() => {
    const fora = (e: MouseEvent) => {
      if (!notifRef.current?.contains(e.target as Node)) setVerNotifs(false);
      if (!userRef.current?.contains(e.target as Node)) setVerUsuario(false);
    };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") { setVerNotifs(false); setVerUsuario(false); } };
    document.addEventListener("mousedown", fora);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", fora); document.removeEventListener("keydown", esc); };
  }, []);

  const abrirNotif = async (n: Notif) => {
    if (!n.lida) await api.post(`/notificacoes/${n.id}/lida`).catch(() => {});
    setVerNotifs(false);
    atualizarContadores();
    if (n.lead_id) nav(`/leads/${n.lead_id}`);
  };

  const pendencias = tarefas.atrasadas + tarefas.hoje;
  return (
    <div className="app">
      <a href="#conteudo" className="pular-conteudo">Pular para o conteúdo</a>
      {menuAberto && <div className="fundo-menu" onClick={() => setMenuAberto(false)} />}
      <aside className={`sidebar ${menuAberto ? "aberta" : ""}`} aria-label="Menu principal">
        <div className="marca">
          <svg width="30" height="30" viewBox="0 0 32 32" aria-hidden><rect width="32" height="32" rx="8" fill="#1d4ed8" /><path d="M8 9h16l-6 7v6l-4 2v-8z" fill="#fff" /></svg>
          Leads Tenti
        </div>
        <nav className="nav">
          <NavLink to="/" end><Icone nome="painel" />Painel</NavLink>
          <NavLink to="/leads"><Icone nome="leads" />Leads</NavLink>
          <NavLink to="/tarefas"><Icone nome="tarefas" />Tarefas
            {pendencias > 0 && <span className="contador" aria-label={`${pendencias} pendentes`}>{pendencias}</span>}
          </NavLink>
          <NavLink to="/relatorios"><Icone nome="relatorios" />Relatórios</NavLink>
          {pode.editar && <NavLink to="/importar"><Icone nome="importar" />Importar</NavLink>}
          {pode.admin && <NavLink to="/admin"><Icone nome="admin" />Administração</NavLink>}
        </nav>
        <div className="sidebar-rodape">
          <strong>{usuario?.nome}</strong>
          {PERFIS[usuario?.perfil ?? ""]}
        </div>
      </aside>
      <div className="principal">
        <header className="topo">
          <button className="btn btn-fantasma btn-icone menu-movel" aria-label="Abrir menu" onClick={() => setMenuAberto(true)}><Icone nome="menu" /></button>
          <form className="busca" role="search" onSubmit={(e) => { e.preventDefault(); nav(`/leads?q=${encodeURIComponent(busca.trim())}`); }}>
            <label htmlFor="busca-global" className="sr-only">Buscar leads</label>
            <Icone nome="busca" />
            <input id="busca-global" type="search" placeholder="Buscar por nome, e-mail, telefone ou empresa…" value={busca} onChange={(e) => setBusca(e.target.value)} />
          </form>
          <div style={{ marginLeft: "auto" }} className="flex">
            <div className="sino" ref={notifRef} style={{ position: "relative" }}>
              <button className="btn btn-fantasma btn-icone" aria-label={`Notificações (${notifs.nao_lidas} não lidas)`} aria-expanded={verNotifs} onClick={() => setVerNotifs(!verNotifs)}>
                <Icone nome="sino" />
                {notifs.nao_lidas > 0 && <span className="bolinha" aria-hidden>{notifs.nao_lidas > 99 ? "99+" : notifs.nao_lidas}</span>}
              </button>
              {verNotifs && (
                <div className="popover">
                  <div className="cartao-cab"><h3>Notificações</h3>
                    {notifs.nao_lidas > 0 && <button className="btn btn-pequeno btn-fantasma" onClick={async () => { await api.post("/notificacoes/lidas"); atualizarContadores(); }}>Marcar todas como lidas</button>}
                  </div>
                  {notifs.itens.length === 0 ? <p className="vazio pequeno">Nenhuma notificação.</p> : (
                    <ul>{notifs.itens.map((n) => (
                      <li key={n.id} className={n.lida ? "" : "nao-lida"}>
                        <button onClick={() => abrirNotif(n)}>
                          <div>{n.mensagem}</div>
                          <div className="texto-3">{relativo(n.criado_em)}</div>
                        </button>
                      </li>))}
                    </ul>)}
                </div>
              )}
            </div>
            <div className="menu-usuario" ref={userRef} style={{ position: "relative" }}>
              <button className="btn btn-fantasma" style={{ padding: 2 }} aria-label="Menu do usuário" aria-expanded={verUsuario} onClick={() => setVerUsuario(!verUsuario)}>
                <span className="avatar" aria-hidden>{iniciais(usuario?.nome ?? "?")}</span>
              </button>
              {verUsuario && (
                <div className="popover">
                  <div style={{ padding: "8px 10px" }}><strong>{usuario?.nome}</strong><div className="texto-3">{usuario?.email}</div></div>
                  <Link to="/perfil">Meu perfil e segurança</Link>
                  <button onClick={() => { sair(); nav("/"); }}>Sair</button>
                </div>
              )}
            </div>
          </div>
        </header>
        <main id="conteudo" className="conteudo" tabIndex={-1}>
          <Outlet context={{ atualizarContadores }} />
        </main>
      </div>
    </div>
  );
}
