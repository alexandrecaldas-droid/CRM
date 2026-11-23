import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useCadastros, usePode } from "../contexto";
import { Aviso, Carregando, Paginacao, useCarregar, Vazio } from "../ui";
import { ItemTarefa } from "./LeadDetalhe";

const SITUACOES = [
  ["atrasadas", "Atrasadas"], ["hoje", "Hoje"], ["proximas", "Próximas"], ["pendentes", "Todas pendentes"], ["concluidas", "Concluídas"],
] as const;

export default function Tarefas() {
  const [sp, setSp] = useSearchParams();
  const pode = usePode();
  const { usuarios } = useCadastros();
  const situacao = sp.get("situacao") || "pendentes";
  const resp = sp.get("responsavel_id") || "";
  const minhas = sp.get("minhas") !== "false";
  const pagina = Number(sp.get("pagina") || 1);
  const resumo = useCarregar(() => api.get("/tarefas/resumo"), []);
  const { dados, erro, carregando, recarregar } = useCarregar(() => api.get("/tarefas", {
    situacao, pagina, tamanho: 30, minhas: pode.verTodos ? (resp ? false : minhas) : false, responsavel_id: resp || undefined,
  }), [situacao, pagina, resp, minhas]);
  const definir = (k: string, v: string) => { const n = new URLSearchParams(sp); v ? n.set(k, v) : n.delete(k); if (k !== "pagina") n.delete("pagina"); setSp(n); };

  return (
    <>
      <div className="cabecalho-pagina">
        <div><h1>Tarefas</h1><p>Próximas ações e lembretes. Concluídas e atrasadas também chegam por notificação e e-mail.</p></div>
        {pode.verTodos && (
          <div className="grupo-botoes">
            <div className="alternador" role="group" aria-label="De quem">
              <button aria-pressed={minhas && !resp} onClick={() => { const n = new URLSearchParams(sp); n.delete("responsavel_id"); n.delete("minhas"); setSp(n); }}>Minhas</button>
              <button aria-pressed={!minhas || !!resp} onClick={() => definir("minhas", "false")}>Equipe</button>
            </div>
            {(!minhas || resp) && (
              <select aria-label="Responsável" value={resp} onChange={(e) => definir("responsavel_id", e.target.value)} style={{ width: 200 }}>
                <option value="">Todos</option>
                {usuarios.filter((u) => u.perfil !== "leitura").map((u) => <option key={u.id} value={u.id}>{u.nome}</option>)}
              </select>
            )}
          </div>
        )}
      </div>
      <div className="abas" role="tablist">
        {SITUACOES.map(([k, r]) => (
          <button key={k} role="tab" aria-selected={situacao === k} onClick={() => definir("situacao", k)}>
            {r}{k === "atrasadas" && resumo.dados?.atrasadas ? <span className="selo selo-alerta" style={{ marginLeft: 6 }}>{resumo.dados.atrasadas}</span> : null}
            {k === "hoje" && resumo.dados?.hoje ? <span className="selo selo-info" style={{ marginLeft: 6 }}>{resumo.dados.hoje}</span> : null}
          </button>
        ))}
      </div>
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      <div className="cartao">
        {carregando && !dados ? <Carregando /> : !dados?.itens.length ? (
          <Vazio titulo={situacao === "atrasadas" ? "Nenhuma tarefa atrasada" : "Nenhuma tarefa aqui"} icone="tarefas">
            <p className="texto-2">Agende próximas ações pela página de cada lead.</p>
          </Vazio>
        ) : (
          <div className="cartao-corpo">
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {dados.itens.map((t: any) => <ItemTarefa key={t.id} t={t} mostrarLead aoMudar={() => { recarregar(); resumo.recarregar(); }} />)}
            </ul>
          </div>
        )}
        {dados && dados.total > 30 && <Paginacao pagina={pagina} tamanho={30} total={dados.total} aoMudar={(p) => definir("pagina", String(p))} />}
      </div>
    </>
  );
}
