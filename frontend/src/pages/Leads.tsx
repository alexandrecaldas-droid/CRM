import {
  DndContext, DragOverlay, KeyboardSensor, PointerSensor, useDraggable, useDroppable, useSensor, useSensors,
  type DragEndEvent, type DragStartEvent,
} from "@dnd-kit/core";
import { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, baixar } from "../api";
import LeadForm from "../components/LeadForm";
import MudarEstagio from "../components/MudarEstagio";
import { useCadastros, usePode } from "../contexto";
import { data, moeda, moedaCurta, relativo, telefone } from "../formato";
import type { Estagio, Lead, Pagina } from "../tipos";
import {
  Aviso, Campo, Carregando, Etiquetas, Icone, Modal, MultiSelecao, Paginacao, SeloEstagio, useCarregar, useToast, Vazio,
} from "../ui";

const LISTAS = ["estagio_id", "origem_id", "responsavel_id", "etiqueta_id"] as const;
const SIMPLES = ["q", "status", "criado_de", "criado_ate", "contato_de", "contato_ate", "fechado_de", "fechado_ate", "valor_min", "valor_max"] as const;
const BOOLEANOS = ["parado", "sem_proxima_acao", "sem_contato"] as const;

function lerFiltros(sp: URLSearchParams): Record<string, any> {
  const f: Record<string, any> = {};
  for (const k of LISTAS) { const v = sp.getAll(k).map(Number).filter(Boolean); if (v.length) f[k] = v; }
  for (const k of SIMPLES) { const v = sp.get(k); if (v) f[k] = v; }
  for (const k of BOOLEANOS) if (sp.get(k) === "true") f[k] = true;
  return f;
}

function Alertas({ lead }: { lead: Lead }) {
  return (
    <>
      {lead.parado && <span className="selo selo-alerta" title="Sem interação há mais de N dias">Parado</span>}
      {lead.sem_proxima_acao && <span className="selo selo-aviso">Sem próxima ação</span>}
    </>
  );
}

/* ---------------------------------------------------------------- Kanban */
function CartaoLead({ lead, sobreposto }: { lead: Lead; sobreposto?: boolean }) {
  return (
    <div className={`card-lead ${sobreposto ? "sobreposto" : ""}`}>
      <Link to={`/leads/${lead.id}`} onPointerDown={(e) => e.stopPropagation()}>{lead.nome}</Link>
      {lead.empresa && <div className="texto-3">{lead.empresa}</div>}
      <div className="linha">
        <span>{lead.valor_estimado ? moeda(lead.valor_estimado) : "Sem valor"}</span>
        <span title="Responsável">{lead.responsavel.nome.split(" ")[0]}</span>
      </div>
      <div className="linha"><span>Últ. contato: {relativo(lead.ultimo_contato_em)}</span></div>
      {(lead.parado || lead.sem_proxima_acao || lead.etiquetas.length > 0) && (
        <div className="alertas"><Alertas lead={lead} /><Etiquetas itens={lead.etiquetas} /></div>
      )}
    </div>
  );
}

function Arrastavel({ lead, pode }: { lead: Lead; pode: boolean }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: lead.id, data: { lead }, disabled: !pode });
  return (
    <div ref={setNodeRef} {...listeners} {...attributes} className={isDragging ? "arrastando" : ""}
      aria-roledescription="cartão arrastável" aria-label={`${lead.nome}, estágio ${lead.estagio.nome}`}>
      <CartaoLead lead={lead} />
    </div>
  );
}

function Coluna({ col, pode }: { col: any; pode: boolean }) {
  const { setNodeRef, isOver } = useDroppable({ id: `col-${col.estagio.id}`, data: { estagio: col.estagio } });
  return (
    <section className={`coluna ${isOver ? "alvo" : ""}`} ref={setNodeRef} aria-label={`Estágio ${col.estagio.nome}`}
      style={{ ["--cor" as string]: col.estagio.cor ?? undefined }}>
      <div className="coluna-cab">
        <h2>{col.estagio.nome}<span className="selo">{col.total}</span></h2>
        <div className="sub">{moedaCurta(col.valor)}</div>
      </div>
      <div className="coluna-lista">
        {col.leads.map((l: Lead) => <Arrastavel key={l.id} lead={l} pode={pode} />)}
        {col.total > col.leads.length && <p className="texto-3" style={{ textAlign: "center", margin: 4 }}>+{col.total - col.leads.length} leads — use a lista ou filtros</p>}
        {col.total === 0 && <p className="texto-3" style={{ textAlign: "center", margin: 8 }}>Solte um lead aqui</p>}
      </div>
    </section>
  );
}

function Kanban({ filtros }: { filtros: Record<string, any> }) {
  const pode = usePode();
  const toast = useToast();
  const { dados, erro, carregando, recarregar, setDados } = useCarregar(() => api.get("/leads/kanban", filtros), [JSON.stringify(filtros)]);
  const [ativo, setAtivo] = useState<Lead | null>(null);
  const [pendente, setPendente] = useState<{ lead: Lead; estagio: Estagio } | null>(null);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }), useSensor(KeyboardSensor));

  const mover = (lead: Lead, destinoId: number) => {
    // Atualização otimista; a resposta do servidor confirma ou desfaz.
    setDados((d: any) => {
      if (!d) return d;
      const cols = d.colunas.map((c: any) => ({ ...c, leads: c.leads.filter((l: Lead) => l.id !== lead.id), total: c.estagio.id === lead.estagio.id ? c.total - 1 : c.total }));
      const alvo = cols.find((c: any) => c.estagio.id === destinoId);
      if (alvo) { alvo.leads = [{ ...lead, estagio: alvo.estagio }, ...alvo.leads]; alvo.total += 1; }
      return { colunas: cols };
    });
  };

  const aoSoltar = async (e: DragEndEvent) => {
    setAtivo(null);
    const lead = e.active.data.current?.lead as Lead;
    const estagio = e.over?.data.current?.estagio as Estagio | undefined;
    if (!lead || !estagio || estagio.id === lead.estagio.id) return;
    if (estagio.tipo !== "aberto") { setPendente({ lead, estagio }); return; }
    mover(lead, estagio.id);
    try {
      await api.post(`/leads/${lead.id}/estagio`, { estagio_id: estagio.id });
      toast(`${lead.nome} movido para ${estagio.nome}.`);
      recarregar();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Não foi possível mover.", "erro");
      recarregar();
    }
  };

  if (erro) return <Aviso tipo="erro">{erro}</Aviso>;
  if (carregando && !dados) return <Carregando />;
  return (
    <>
      <p className="sr-only">Para mover com o teclado: foque um cartão, pressione espaço, use as setas e espaço novamente para soltar.</p>
      <DndContext sensors={sensors} onDragStart={(e: DragStartEvent) => setAtivo(e.active.data.current?.lead)} onDragEnd={aoSoltar} onDragCancel={() => setAtivo(null)}
        accessibility={{ announcements: {
          onDragStart: ({ active }) => `Pegou o lead ${active.data.current?.lead?.nome}.`,
          onDragOver: ({ over }) => over ? `Sobre o estágio ${over.data.current?.estagio?.nome}.` : "Fora de um estágio.",
          onDragEnd: ({ over }) => over ? `Solto no estágio ${over.data.current?.estagio?.nome}.` : "Movimento cancelado.",
          onDragCancel: () => "Movimento cancelado.",
        }, screenReaderInstructions: { draggable: "Pressione espaço para pegar, setas para mover e espaço para soltar." } }}>
        <div className="kanban">{dados.colunas.map((c: any) => <Coluna key={c.estagio.id} col={c} pode={pode.editar} />)}</div>
        <DragOverlay>{ativo ? <CartaoLead lead={ativo} sobreposto /> : null}</DragOverlay>
      </DndContext>
      {pendente && <MudarEstagio lead={pendente.lead} estagio={pendente.estagio} aoFechar={() => setPendente(null)} aoSalvar={() => { setPendente(null); recarregar(); }} />}
    </>
  );
}

/* ---------------------------------------------------------------- Lista */
const COLUNAS: [string, string][] = [["nome", "Nome"], ["estagio", "Estágio"], ["", "Origem"], ["", "Responsável"], ["valor_estimado", "Valor"], ["ultimo_contato_em", "Últ. contato"], ["criado_em", "Criado em"]];

function Lista({ filtros, sp, setSp }: { filtros: Record<string, any>; sp: URLSearchParams; setSp: (s: URLSearchParams) => void }) {
  const pode = usePode();
  const toast = useToast();
  const { usuarios } = useCadastros();
  const pagina = Number(sp.get("pagina") || 1);
  const ordenar = sp.get("ordenar") || "criado_em";
  const direcao = sp.get("direcao") || "desc";
  const { dados, erro, carregando, recarregar } = useCarregar<Pagina<Lead>>(
    () => api.get("/leads", { ...filtros, pagina, ordenar, direcao, tamanho: 25 }), [JSON.stringify(filtros), pagina, ordenar, direcao]);
  const [sel, setSel] = useState<number[]>([]);
  const [lote, setLote] = useState(false);
  const [destino, setDestino] = useState("");

  const mudar = (k: string, v: string) => { const n = new URLSearchParams(sp); n.set(k, v); if (k !== "pagina") n.delete("pagina"); setSp(n); };
  const ordenarPor = (c: string) => {
    const n = new URLSearchParams(sp);
    n.set("ordenar", c);
    n.set("direcao", ordenar === c && direcao === "asc" ? "desc" : "asc");
    setSp(n);
  };

  if (erro) return <Aviso tipo="erro">{erro}</Aviso>;
  const itens = dados?.itens ?? [];
  return (
    <div className="cartao">
      {pode.gerir && sel.length > 0 && (
        <div className="cartao-cab" style={{ background: "var(--primary-soft)" }}>
          <span>{sel.length} selecionado(s)</span>
          <div className="grupo-botoes">
            <button className="btn btn-pequeno" onClick={() => setLote(true)}>Reatribuir</button>
            <button className="btn btn-pequeno btn-fantasma" onClick={() => setSel([])}>Limpar seleção</button>
          </div>
        </div>
      )}
      {carregando && !dados ? <Carregando /> : itens.length === 0 ? (
        <Vazio titulo="Nenhum lead encontrado">Ajuste os filtros ou cadastre um novo lead.</Vazio>
      ) : (
        <div className="tabela-wrap">
          <table className="responsiva">
            <thead>
              <tr>
                {pode.gerir && <th style={{ width: 36 }}><input type="checkbox" aria-label="Selecionar todos da página" checked={itens.every((l) => sel.includes(l.id))}
                  onChange={(e) => setSel(e.target.checked ? [...new Set([...sel, ...itens.map((l) => l.id)])] : sel.filter((x) => !itens.some((l) => l.id === x)))} /></th>}
                {COLUNAS.map(([k, r]) => (
                  <th key={r} className={k === "valor_estimado" ? "num" : ""} aria-sort={ordenar === k ? (direcao === "asc" ? "ascending" : "descending") : undefined}>
                    {k ? <button onClick={() => ordenarPor(k)}>{r}{ordenar === k ? (direcao === "asc" ? " ▲" : " ▼") : ""}</button> : r}
                  </th>
                ))}
                <th>Situação</th>
              </tr>
            </thead>
            <tbody>
              {itens.map((l) => (
                <tr key={l.id}>
                  {pode.gerir && <td data-rotulo="Selecionar"><input type="checkbox" aria-label={`Selecionar ${l.nome}`} checked={sel.includes(l.id)} onChange={(e) => setSel(e.target.checked ? [...sel, l.id] : sel.filter((x) => x !== l.id))} /></td>}
                  <td data-rotulo="Nome">
                    <Link className="link-linha" to={`/leads/${l.id}`}>{l.nome}</Link>
                    <div className="texto-3">{[l.empresa, l.email ?? telefone(l.telefone)].filter(Boolean).join(" · ")}</div>
                  </td>
                  <td data-rotulo="Estágio"><SeloEstagio estagio={l.estagio} /></td>
                  <td data-rotulo="Origem">{l.origem.nome}</td>
                  <td data-rotulo="Responsável">{l.responsavel.nome}</td>
                  <td data-rotulo="Valor" className="num">{moeda(l.valor_estimado)}</td>
                  <td data-rotulo="Últ. contato">{relativo(l.ultimo_contato_em)}</td>
                  <td data-rotulo="Criado em">{data(l.criado_em)}</td>
                  <td data-rotulo="Situação"><span className="flex" style={{ gap: 4, flexWrap: "wrap" }}><Alertas lead={l} /><Etiquetas itens={l.etiquetas} /></span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {dados && dados.total > 0 && <Paginacao pagina={pagina} tamanho={25} total={dados.total} aoMudar={(p) => mudar("pagina", String(p))} />}
      {lote && (
        <Modal titulo={`Reatribuir ${sel.length} lead(s)`} aoFechar={() => setLote(false)} rodape={<>
          <button className="btn" onClick={() => setLote(false)}>Cancelar</button>
          <button className="btn btn-primario" disabled={!destino} onClick={async () => {
            try {
              const corpo = destino === "auto" ? { lead_ids: sel, automatico: true } : { lead_ids: sel, responsavel_id: Number(destino) };
              const r = await api.post("/leads/atribuir-lote", corpo);
              toast(`${r.atualizados} lead(s) reatribuído(s).`);
              setSel([]); setLote(false); recarregar();
            } catch (err) { toast(err instanceof Error ? err.message : "Erro", "erro"); }
          }}>Reatribuir</button>
        </>}>
          <Campo rotulo="Novo responsável">{(p) => (
            <select {...p} value={destino} onChange={(e) => setDestino(e.target.value)}>
              <option value="">Selecione…</option>
              <option value="auto">Distribuir por rodízio/regras</option>
              {usuarios.filter((u) => u.ativo && u.perfil !== "leitura").map((u) => <option key={u.id} value={u.id}>{u.nome}</option>)}
            </select>)}
          </Campo>
        </Modal>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- Página */
export default function Leads() {
  const [sp, setSp] = useSearchParams();
  const nav = useNavigate();
  const pode = usePode();
  const toast = useToast();
  const { estagios, origens, usuarios, etiquetas, parametros } = useCadastros();
  const visao = sp.get("visao") === "lista" || (sp.get("visao") !== "kanban" && window.matchMedia?.("(max-width: 860px)").matches) ? "lista" : "kanban";
  const filtros = useMemo(() => lerFiltros(sp), [sp]);
  const [novo, setNovo] = useState(false);
  const [maisFiltros, setMaisFiltros] = useState(() => ["criado_de", "contato_de", "valor_min", "fechado_de"].some((k) => sp.get(k)));
  const [salvarVisao, setSalvarVisao] = useState(false);
  const [nomeVisao, setNomeVisao] = useState("");
  const visoes = useCarregar(() => api.get("/visoes"), []);
  const [busca, setBusca] = useState(sp.get("q") ?? "");

  const definir = (k: string, v: unknown) => {
    const n = new URLSearchParams(sp);
    n.delete(k); n.delete("pagina");
    if (Array.isArray(v)) v.forEach((x) => n.append(k, String(x)));
    else if (v !== undefined && v !== null && v !== "" && v !== false) n.set(k, String(v));
    setSp(n);
  };
  const aplicar = (f: Record<string, any>) => {
    const n = new URLSearchParams();
    n.set("visao", visao);
    for (const [k, v] of Object.entries(f)) Array.isArray(v) ? v.forEach((x) => n.append(k, String(x))) : n.set(k, String(v));
    setSp(n);
    setBusca(f.q ?? "");
  };

  const nomes = (k: string, ids: number[]) => {
    const fonte: { id: number; nome: string }[] = k === "estagio_id" ? estagios : k === "origem_id" ? origens : k === "responsavel_id" ? usuarios : etiquetas;
    return ids.map((i) => fonte.find((x) => x.id === i)?.nome ?? i).join(", ");
  };
  const ROT: Record<string, string> = {
    estagio_id: "Estágio", origem_id: "Origem", responsavel_id: "Responsável", etiqueta_id: "Etiqueta", q: "Busca", status: "Situação",
    criado_de: "Criado desde", criado_ate: "Criado até", contato_de: "Contato desde", contato_ate: "Contato até",
    fechado_de: "Fechado desde", fechado_ate: "Fechado até", valor_min: "Valor mín.", valor_max: "Valor máx.",
    parado: `Parados (+${parametros.dias_lead_parado} dias)`, sem_proxima_acao: "Sem próxima ação", sem_contato: "Sem contato",
  };
  const chips = Object.entries(filtros);

  return (
    <>
      <div className="cabecalho-pagina">
        <div>
          <h1>Leads</h1>
          <p>Arraste os cartões entre os estágios ou use a lista para ordenar e filtrar.</p>
        </div>
        <div className="grupo-botoes">
          <div className="alternador" role="group" aria-label="Modo de visualização">
            <button aria-pressed={visao === "kanban"} onClick={() => definir("visao", "kanban")}><Icone nome="kanban" />Quadro</button>
            <button aria-pressed={visao === "lista"} onClick={() => definir("visao", "lista")}><Icone nome="lista" />Lista</button>
          </div>
          {pode.exportar && (
            <button className="btn" onClick={() => baixar("/exportacoes", { tipo: "leads", formato: "xlsx", ...filtros }).catch((e) => toast(e.message, "erro"))}>
              <Icone nome="baixar" />Exportar
            </button>
          )}
          {pode.editar && <button className="btn btn-primario" onClick={() => setNovo(true)}><Icone nome="mais" />Novo lead</button>}
        </div>
      </div>

      <div className="barra-filtros">
        <form className="campo" style={{ flex: "1 1 220px" }} onSubmit={(e) => { e.preventDefault(); definir("q", busca.trim()); }} role="search">
          <label htmlFor="f-q" className="rotulo">Buscar</label>
          <input id="f-q" type="search" value={busca} placeholder="Nome, e-mail, telefone, empresa" onChange={(e) => setBusca(e.target.value)} onBlur={() => busca !== (sp.get("q") ?? "") && definir("q", busca.trim())} />
        </form>
        <MultiSelecao rotulo="Estágio" opcoes={estagios.filter((e) => e.ativo)} valor={filtros.estagio_id ?? []} aoMudar={(v) => definir("estagio_id", v)} />
        <MultiSelecao rotulo="Origem" opcoes={origens} valor={filtros.origem_id ?? []} aoMudar={(v) => definir("origem_id", v)} />
        {pode.verTodos && <MultiSelecao rotulo="Responsável" opcoes={usuarios.filter((u) => u.perfil !== "leitura")} valor={filtros.responsavel_id ?? []} aoMudar={(v) => definir("responsavel_id", v)} />}
        <MultiSelecao rotulo="Etiqueta" opcoes={etiquetas} valor={filtros.etiqueta_id ?? []} aoMudar={(v) => definir("etiqueta_id", v)} />
        <div className="campo">
          <label htmlFor="f-status" className="rotulo">Situação</label>
          <select id="f-status" value={filtros.status ?? ""} onChange={(e) => definir("status", e.target.value)}>
            <option value="">Todas</option><option value="aberto">Em aberto</option><option value="ganho">Ganhos</option><option value="perdido">Perdidos</option>
          </select>
        </div>
        <button className="btn" aria-expanded={maisFiltros} onClick={() => setMaisFiltros(!maisFiltros)}><Icone nome="filtro" />Mais filtros</button>
        <div className="campo">
          <label htmlFor="f-visao" className="rotulo">Visões salvas</label>
          <select id="f-visao" value="" onChange={(e) => {
            const v = (visoes.dados ?? []).find((x: any) => String(x.id) === e.target.value);
            if (v) aplicar(v.filtros);
          }}>
            <option value="">{visoes.dados?.length ? "Escolher…" : "Nenhuma"}</option>
            {(visoes.dados ?? []).map((v: any) => <option key={v.id} value={v.id}>{v.nome}</option>)}
          </select>
        </div>
      </div>

      {maisFiltros && (
        <div className="cartao painel-filtros">
          <div className="grade grade-4">
            <Campo rotulo="Criado de">{(p) => <input {...p} type="date" value={filtros.criado_de ?? ""} onChange={(e) => definir("criado_de", e.target.value)} />}</Campo>
            <Campo rotulo="Criado até">{(p) => <input {...p} type="date" value={filtros.criado_ate ?? ""} onChange={(e) => definir("criado_ate", e.target.value)} />}</Campo>
            <Campo rotulo="Último contato de">{(p) => <input {...p} type="date" value={filtros.contato_de ?? ""} onChange={(e) => definir("contato_de", e.target.value)} />}</Campo>
            <Campo rotulo="Último contato até">{(p) => <input {...p} type="date" value={filtros.contato_ate ?? ""} onChange={(e) => definir("contato_ate", e.target.value)} />}</Campo>
            <Campo rotulo="Valor mínimo (R$)">{(p) => <input {...p} type="number" min={0} value={filtros.valor_min ?? ""} onChange={(e) => definir("valor_min", e.target.value)} />}</Campo>
            <Campo rotulo="Valor máximo (R$)">{(p) => <input {...p} type="number" min={0} value={filtros.valor_max ?? ""} onChange={(e) => definir("valor_max", e.target.value)} />}</Campo>
            <label className="check" style={{ alignSelf: "end" }}><input type="checkbox" checked={!!filtros.parado} onChange={(e) => definir("parado", e.target.checked)} />Somente parados</label>
            <label className="check" style={{ alignSelf: "end" }}><input type="checkbox" checked={!!filtros.sem_proxima_acao} onChange={(e) => definir("sem_proxima_acao", e.target.checked)} />Sem próxima ação</label>
          </div>
        </div>
      )}

      {chips.length > 0 && (
        <div className="chips" aria-label="Filtros ativos">
          {chips.map(([k, v]) => (
            <span key={k} className="chip">
              {ROT[k] ?? k}{v === true ? "" : `: ${LISTAS.includes(k as never) ? nomes(k, v) : k === "status" ? { aberto: "em aberto", ganho: "ganhos", perdido: "perdidos" }[v as string] : v}`}
              <button aria-label={`Remover filtro ${ROT[k] ?? k}`} onClick={() => { definir(k, null); if (k === "q") setBusca(""); }}>×</button>
            </span>
          ))}
          <button className="btn btn-pequeno btn-fantasma" onClick={() => { aplicar({}); }}>Limpar tudo</button>
          <button className="btn btn-pequeno" onClick={() => setSalvarVisao(true)}>Salvar como visão</button>
        </div>
      )}

      {visao === "kanban" ? <Kanban filtros={filtros} /> : <Lista filtros={filtros} sp={sp} setSp={setSp} />}

      {novo && <LeadForm aoFechar={() => setNovo(false)} aoSalvar={(l) => { setNovo(false); nav(`/leads/${l.id}`); }} />}
      {salvarVisao && (
        <Modal titulo="Salvar visão" aoFechar={() => setSalvarVisao(false)} rodape={<>
          {(visoes.dados ?? []).length > 0 && <span className="texto-3" style={{ marginRight: "auto" }}>Você tem {(visoes.dados ?? []).length} visão(ões).</span>}
          <button className="btn" onClick={() => setSalvarVisao(false)}>Cancelar</button>
          <button className="btn btn-primario" disabled={!nomeVisao.trim()} onClick={async () => {
            await api.post("/visoes", { nome: nomeVisao, filtros });
            toast("Visão salva."); setSalvarVisao(false); setNomeVisao(""); visoes.recarregar();
          }}>Salvar</button>
        </>}>
          <div className="pilha">
            <Campo rotulo="Nome da visão" ajuda="Ex.: Meus leads parados, Eventos do trimestre">{(p) => <input {...p} value={nomeVisao} onChange={(e) => setNomeVisao(e.target.value)} />}</Campo>
            {(visoes.dados ?? []).length > 0 && (
              <div>
                <span className="rotulo">Visões existentes</span>
                <ul style={{ paddingLeft: 18 }}>{(visoes.dados ?? []).map((v: any) => (
                  <li key={v.id} className="flex-entre">{v.nome}
                    <button className="btn btn-pequeno btn-fantasma" onClick={async () => { await api.del(`/visoes/${v.id}`); visoes.recarregar(); }}>Excluir</button></li>))}
                </ul>
              </div>
            )}
          </div>
        </Modal>
      )}
    </>
  );
}
