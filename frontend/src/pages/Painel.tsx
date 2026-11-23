import { useState } from "react";
import { Link } from "react-router-dom";
import { api, qs } from "../api";
import { useAuth, useCadastros, usePode } from "../contexto";
import { hojeISO, horas, moeda, moedaCurta, numero } from "../formato";
import { Aviso, Carregando, Icone, useCarregar } from "../ui";

export const linkLista = (filtros: Record<string, unknown>) => `/leads${qs({ ...filtros, visao: "lista" })}`;

export function SeletorPeriodo({ de, ate, aoMudar }: { de: string; ate: string; aoMudar: (de: string, ate: string) => void }) {
  const atalhos: [string, string, string][] = [
    ["7 dias", hojeISO(-6), hojeISO()], ["30 dias", hojeISO(-29), hojeISO()], ["90 dias", hojeISO(-89), hojeISO()],
    ["Este mês", hojeISO().slice(0, 8) + "01", hojeISO()],
  ];
  return (
    <div className="barra-filtros" style={{ marginBottom: 0 }}>
      <div className="alternador" role="group" aria-label="Período rápido">
        {atalhos.map(([r, d, a]) => <button key={r} aria-pressed={de === d && ate === a} onClick={() => aoMudar(d, a)}>{r}</button>)}
      </div>
      <div className="campo" style={{ minWidth: 140 }}><label htmlFor="p-de" className="sr-only">De</label><input id="p-de" type="date" value={de} max={ate} onChange={(e) => aoMudar(e.target.value, ate)} /></div>
      <div className="campo" style={{ minWidth: 140 }}><label htmlFor="p-ate" className="sr-only">Até</label><input id="p-ate" type="date" value={ate} min={de} onChange={(e) => aoMudar(de, e.target.value)} /></div>
    </div>
  );
}

export default function Painel() {
  const { usuario } = useAuth();
  const pode = usePode();
  const { usuarios, parametros } = useCadastros();
  const [de, setDe] = useState(hojeISO(-29));
  const [ate, setAte] = useState(hojeISO());
  const [resp, setResp] = useState("");
  const { dados: p, erro, carregando } = useCarregar(() => api.get("/relatorios/painel", { de, ate, responsavel_id: resp || undefined }), [de, ate, resp]);
  const tarefas = useCarregar(() => api.get("/tarefas", { situacao: "atrasadas", tamanho: 6, minhas: !pode.verTodos }), []);

  const maxEstagio = Math.max(1, ...(p?.por_estagio ?? []).map((e: any) => e.total));
  return (
    <>
      <div className="cabecalho-pagina">
        <div>
          <h1>Olá, {usuario?.nome.split(" ")[0]}</h1>
          <p>{pode.verTodos ? "Visão geral da equipe comercial." : "Seus leads e pendências."}</p>
        </div>
        <div className="grupo-botoes">
          {pode.verTodos && (
            <div className="campo" style={{ minWidth: 180 }}>
              <label htmlFor="p-resp" className="sr-only">Vendedor</label>
              <select id="p-resp" value={resp} onChange={(e) => setResp(e.target.value)}>
                <option value="">Toda a equipe</option>
                {usuarios.filter((u) => u.perfil === "vendedor" || u.perfil === "gestor").map((u) => <option key={u.id} value={u.id}>{u.nome}</option>)}
              </select>
            </div>
          )}
          <SeletorPeriodo de={de} ate={ate} aoMudar={(d, a) => { setDe(d); setAte(a); }} />
        </div>
      </div>
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      {carregando && !p ? <Carregando /> : p && (
        <>
          <section className="kpis" aria-label="Indicadores">
            <Link className="cartao kpi" to={linkLista(p.novos.filtros)}>
              <span className="rotulo-kpi">Leads novos no período</span>
              <span className="valor">{numero(p.novos.total)}</span>
              <span className="sub">criados entre as datas</span>
            </Link>
            <div className="cartao kpi bom">
              <span className="rotulo-kpi">Conversão geral</span>
              <span className="valor">{p.conversao.geral.toLocaleString("pt-BR")}%</span>
              <span className="sub">{p.conversao.ganhos} ganhos de {p.conversao.base} novos</span>
            </div>
            <div className="cartao kpi">
              <span className="rotulo-kpi">Tempo médio até 1º contato</span>
              <span className="valor">{horas(p.primeiro_contato.media_horas)}</span>
              <Link className="sub" to={linkLista(p.primeiro_contato.filtros_sem_contato)}>{p.primeiro_contato.sem_contato} ainda sem contato</Link>
            </div>
            <Link className={`cartao kpi ${p.tarefas_atrasadas ? "alerta" : ""}`} to="/tarefas?situacao=atrasadas">
              <span className="rotulo-kpi">Tarefas atrasadas</span>
              <span className="valor">{numero(p.tarefas_atrasadas)}</span>
              <span className="sub">pendentes com vencimento passado</span>
            </Link>
            <Link className={`cartao kpi ${p.parados.total ? "alerta" : ""}`} to={linkLista(p.parados.filtros)}>
              <span className="rotulo-kpi">Leads parados</span>
              <span className="valor">{numero(p.parados.total)}</span>
              <span className="sub">sem interação há mais de {parametros.dias_lead_parado} dias</span>
            </Link>
            <Link className={`cartao kpi ${p.sem_proxima_acao.total ? "alerta" : ""}`} to={linkLista(p.sem_proxima_acao.filtros)}>
              <span className="rotulo-kpi">Sem próxima ação</span>
              <span className="valor">{numero(p.sem_proxima_acao.total)}</span>
              <span className="sub">leads ativos sem tarefa agendada</span>
            </Link>
            <Link className="cartao kpi" to={linkLista(p.valor_funil.filtros)}>
              <span className="rotulo-kpi">Valor do funil (aberto)</span>
              <span className="valor" title={moeda(p.valor_funil.total)}>{moedaCurta(p.valor_funil.total)}</span>
              <span className="sub">{p.valor_funil.quantidade} leads em aberto</span>
            </Link>
            <Link className="cartao kpi bom" to={linkLista(p.valor_ganho.filtros)}>
              <span className="rotulo-kpi">Valor ganho no período</span>
              <span className="valor" title={moeda(p.valor_ganho.total)}>{moedaCurta(p.valor_ganho.total)}</span>
              <span className="sub">{p.valor_ganho.quantidade} negócios fechados</span>
            </Link>
          </section>

          <div className="grade grade-2">
            <section className="cartao" aria-labelledby="t-estagios">
              <div className="cartao-cab"><h2 id="t-estagios">Leads por estágio</h2><span className="texto-3">situação atual</span></div>
              <div className="cartao-corpo barras">
                {p.por_estagio.map((e: any) => (
                  <Link key={e.id} className="barra-linha" to={linkLista(e.filtros)} aria-label={`${e.nome}: ${e.total} leads`}>
                    <span className="barra-nome">{e.nome}</span>
                    <span className="barra-trilho"><span className="barra-preenchida" style={{ width: `${(e.total / maxEstagio) * 100}%`, ["--cor" as string]: e.cor ?? undefined }} /></span>
                    <span className="barra-valor">{e.total}</span>
                  </Link>
                ))}
              </div>
            </section>
            <section className="cartao" aria-labelledby="t-conv">
              <div className="cartao-cab"><h2 id="t-conv">Conversão por estágio</h2><span className="texto-3">leads novos no período</span></div>
              <div className="cartao-corpo">
                <table>
                  <thead><tr><th>Estágio</th><th className="num">Chegaram</th><th className="num">Da etapa anterior</th></tr></thead>
                  <tbody>
                    {p.conversao.por_estagio.map((c: any) => (
                      <tr key={c.id}><td>{c.nome}</td><td className="num">{c.chegaram}</td><td className="num">{c.taxa_etapa.toLocaleString("pt-BR")}%</td></tr>
                    ))}
                  </tbody>
                </table>
                <p className="texto-3 mt">Perdidos no período: {p.conversao.perdidos}. Leads que avançaram mais de uma etapa contam em todas as etapas intermediárias.</p>
              </div>
            </section>
          </div>

          <section className="cartao mt" aria-labelledby="t-atr">
            <div className="cartao-cab"><h2 id="t-atr">Tarefas atrasadas</h2><Link to="/tarefas?situacao=atrasadas" className="pequeno">Ver todas</Link></div>
            <div className="cartao-corpo">
              {tarefas.dados?.itens?.length ? (
                <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                  {tarefas.dados.itens.map((t: any) => (
                    <li key={t.id} className="tarefa-item">
                      <span style={{ color: "var(--danger)" }}><Icone nome="relogio" /></span>
                      <div className="info">
                        <div className="titulo">{t.titulo}</div>
                        <div className="texto-3"><Link to={`/leads/${t.lead.id}`}>{t.lead.nome}</Link> · {t.responsavel.nome}</div>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : <p className="texto-2" style={{ margin: 0 }}>Nenhuma tarefa atrasada. 🎉</p>}
            </div>
          </section>
        </>
      )}
    </>
  );
}
