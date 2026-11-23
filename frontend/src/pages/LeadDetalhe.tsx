import { useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, baixar } from "../api";
import LeadForm from "../components/LeadForm";
import MudarEstagio from "../components/MudarEstagio";
import { useCadastros, useAuth, usePode } from "../contexto";
import {
  BASES_LEGAIS, data, dataHora, duracao, isoParaLocal, localParaISO, moeda, relativo, telefone, TIPOS_INTERACAO,
} from "../formato";
import type { Estagio, Interacao, Lead, Tarefa } from "../tipos";
import {
  Abas, Aviso, Campo, Carregando, Confirmar, errosDeCampo, Etiquetas, Icone, Modal, SeloEstagio, useCarregar, useToast,
} from "../ui";

function tamanho(b: number) { return b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.ceil(b / 1024)} KB`; }

/* ---------------------------------------------------------------- registrar interação */
function NovaInteracao({ lead, aoSalvar }: { lead: Lead; aoSalvar: () => void }) {
  const toast = useToast();
  const [tipo, setTipo] = useState("ligacao");
  const [resumo, setResumo] = useState("");
  const [resultado, setResultado] = useState("");
  const [quando, setQuando] = useState("");
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [erros, setErros] = useState<Record<string, string>>({});
  const [ocupado, setOcupado] = useState(false);
  const inputArq = useRef<HTMLInputElement>(null);
  const salvar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resumo.trim()) return setErros({ resumo: "Descreva o que aconteceu." });
    if (arquivo && arquivo.size > 10 * 1024 * 1024) return setErros({ arquivo: "O arquivo excede 10 MB." });
    setOcupado(true);
    try {
      const i = await api.post<Interacao>(`/leads/${lead.id}/interacoes`, { tipo, resumo, resultado: resultado || null, data_hora: quando ? localParaISO(quando) : null });
      if (arquivo) {
        const fd = new FormData();
        fd.append("arquivo", arquivo);
        await api.post(`/leads/${lead.id}/anexos?interacao_id=${i.id}`, fd);
      }
      toast("Interação registrada.");
      setResumo(""); setResultado(""); setQuando(""); setArquivo(null); setErros({});
      if (inputArq.current) inputArq.current.value = "";
      aoSalvar();
    } catch (err) { setErros({ ...errosDeCampo(err), geral: err instanceof Error ? err.message : "Erro" }); }
    finally { setOcupado(false); }
  };
  return (
    <form className="cartao cartao-corpo pilha" onSubmit={salvar} noValidate aria-label="Registrar interação">
      <div className="flex" style={{ flexWrap: "wrap" }}>
        <div className="alternador" role="group" aria-label="Tipo de interação">
          {["ligacao", "email", "reuniao", "nota"].map((t) => (
            <button type="button" key={t} aria-pressed={tipo === t} onClick={() => setTipo(t)}><Icone nome={t} tam={16} />{TIPOS_INTERACAO[t]}</button>
          ))}
        </div>
      </div>
      {erros.geral && <Aviso tipo="erro">{erros.geral}</Aviso>}
      <Campo rotulo={tipo === "nota" ? "Nota interna" : "Resumo do contato"} erro={erros.resumo} obrigatorio>
        {(p) => <textarea {...p} rows={3} value={resumo} onChange={(e) => setResumo(e.target.value)} placeholder={tipo === "nota" ? "Visível só para a equipe" : "O que foi conversado?"} />}
      </Campo>
      <div className="grade grade-3">
        {tipo !== "nota" && <Campo rotulo="Resultado">{(p) => <input {...p} value={resultado} onChange={(e) => setResultado(e.target.value)} placeholder="Ex.: pediu proposta" />}</Campo>}
        <Campo rotulo="Data e hora" ajuda="Em branco: agora" erro={erros.data_hora}>{(p) => <input {...p} type="datetime-local" value={quando} max={isoParaLocal(new Date().toISOString())} onChange={(e) => setQuando(e.target.value)} />}</Campo>
        <Campo rotulo="Anexo (até 10 MB)" erro={erros.arquivo}>{(p) => <input {...p} ref={inputArq} type="file" onChange={(e) => setArquivo(e.target.files?.[0] ?? null)} />}</Campo>
      </div>
      <div><button className="btn btn-primario" disabled={ocupado}>{ocupado ? "Salvando…" : "Registrar"}</button></div>
    </form>
  );
}

/* ---------------------------------------------------------------- linha do tempo */
function LinhaDoTempo({ itens }: { itens: Interacao[] }) {
  const [filtro, setFiltro] = useState("");
  const [abertos, setAbertos] = useState<number[]>([]);
  const lista = itens.filter((i) => !filtro || (filtro === "contatos" ? i.tipo !== "sistema" : i.tipo === filtro));
  return (
    <>
      <div className="flex-entre" style={{ margin: "16px 0 12px" }}>
        <h2>Linha do tempo</h2>
        <div className="campo" style={{ minWidth: 180 }}>
          <label htmlFor="f-tl" className="sr-only">Filtrar linha do tempo</label>
          <select id="f-tl" value={filtro} onChange={(e) => setFiltro(e.target.value)}>
            <option value="">Tudo</option><option value="contatos">Somente interações</option>
            {Object.entries(TIPOS_INTERACAO).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
      </div>
      {lista.length === 0 ? <p className="texto-2">Nada registrado ainda.</p> : (
        <ol className="timeline">
          {lista.map((i) => (
            <li key={i.id}>
              <span className={`icone ${i.tipo}`} aria-hidden><Icone nome={i.tipo} tam={15} /></span>
              {i.tipo === "sistema" ? (
                <div className="item-sistema">{i.resumo}<div className="meta">{i.usuario?.nome ?? "Sistema"} · <time dateTime={i.data_hora}>{dataHora(i.data_hora)}</time></div></div>
              ) : (
                <div>
                  <div className="flex-entre">
                    <strong>{TIPOS_INTERACAO[i.tipo]}{i.dados?.direcao === "entrada" ? " recebido" : ""}</strong>
                    <span className="meta">{i.usuario?.nome ?? (i.dados?.direcao === "entrada" ? i.dados.de : "Sistema")} · <time dateTime={i.data_hora}>{dataHora(i.data_hora)}</time></span>
                  </div>
                  <div className="bolha">
                    {i.resumo}
                    {i.resultado && <div className="mt pequeno"><strong>Resultado:</strong> {i.resultado}</div>}
                    {i.dados?.corpo && (
                      <div className="mt">
                        <button className="btn btn-pequeno btn-fantasma" aria-expanded={abertos.includes(i.id)} onClick={() => setAbertos(abertos.includes(i.id) ? abertos.filter((x) => x !== i.id) : [...abertos, i.id])}>
                          {abertos.includes(i.id) ? "Ocultar mensagem" : "Ver mensagem"}</button>
                        {abertos.includes(i.id) && <div className="codigo mt" style={{ fontFamily: "inherit" }}>{i.dados.corpo}</div>}
                      </div>
                    )}
                    {i.anexos?.length > 0 && <div className="mt flex" style={{ flexWrap: "wrap" }}>{i.anexos.map((a) => (
                      <button key={a.id} className="btn btn-pequeno" onClick={() => baixar(`/anexos/${a.id}`)}><Icone nome="anexo" tam={14} />{a.nome}</button>))}</div>}
                  </div>
                </div>
              )}
            </li>
          ))}
        </ol>
      )}
    </>
  );
}

/* ---------------------------------------------------------------- tarefas do lead */
export function FormTarefa({ leadId, tarefa, aoFechar, aoSalvar }: { leadId: number; tarefa?: Tarefa; aoFechar: () => void; aoSalvar: () => void }) {
  const toast = useToast();
  const pode = usePode();
  const { usuarios } = useCadastros();
  const amanha = new Date(Date.now() + 86400000); amanha.setUTCHours(12, 0, 0, 0);
  const [titulo, setTitulo] = useState(tarefa?.titulo ?? "");
  const [descricao, setDescricao] = useState(tarefa?.descricao ?? "");
  const [venc, setVenc] = useState(isoParaLocal(tarefa?.vencimento ?? amanha.toISOString()));
  const [resp, setResp] = useState(tarefa ? String(tarefa.responsavel.id) : "");
  const [erros, setErros] = useState<Record<string, string>>({});
  const salvar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!titulo.trim()) return setErros({ titulo: "Informe o que precisa ser feito." });
    if (!venc) return setErros({ vencimento: "Informe data e hora." });
    try {
      const corpo: Record<string, unknown> = { titulo, descricao: descricao || null, vencimento: localParaISO(venc) };
      if (resp) corpo.responsavel_id = Number(resp);
      if (tarefa) await api.patch(`/tarefas/${tarefa.id}`, corpo); else await api.post("/tarefas", { ...corpo, lead_id: leadId });
      toast(tarefa ? "Tarefa atualizada." : "Tarefa agendada.");
      aoSalvar();
    } catch (err) { setErros({ ...errosDeCampo(err), geral: err instanceof Error ? err.message : "Erro" }); }
  };
  const atalhos: [string, number][] = [["Hoje 17h", 0], ["Amanhã 9h", 1], ["Em 3 dias", 3], ["Em 1 semana", 7]];
  return (
    <Modal titulo={tarefa ? "Editar tarefa" : "Agendar próxima ação"} aoFechar={aoFechar} rodape={<>
      <button className="btn" onClick={aoFechar}>Cancelar</button>
      <button className="btn btn-primario" form="form-tarefa">Salvar</button>
    </>}>
      <form id="form-tarefa" className="pilha" onSubmit={salvar} noValidate>
        {erros.geral && <Aviso tipo="erro">{erros.geral}</Aviso>}
        <Campo rotulo="O que fazer" erro={erros.titulo} obrigatorio>{(p) => <input {...p} value={titulo} onChange={(e) => setTitulo(e.target.value)} placeholder="Ex.: Ligar para apresentar a proposta" />}</Campo>
        <Campo rotulo="Vencimento" erro={erros.vencimento} obrigatorio>{(p) => <input {...p} type="datetime-local" value={venc} onChange={(e) => setVenc(e.target.value)} />}</Campo>
        <div className="grupo-botoes">{atalhos.map(([r, d]) => (
          <button type="button" key={r} className="btn btn-pequeno" onClick={() => {
            const base = new Date(Date.now() + d * 86400000);
            const local = isoParaLocal(base.toISOString()).slice(0, 10);
            setVenc(`${local}T${d === 0 ? "17:00" : "09:00"}`);
          }}>{r}</button>))}</div>
        {pode.gerir && (
          <Campo rotulo="Responsável" ajuda="Em branco: responsável pelo lead.">{(p) => (
            <select {...p} value={resp} onChange={(e) => setResp(e.target.value)}>
              <option value="">Responsável pelo lead</option>
              {usuarios.filter((u) => u.ativo && u.perfil !== "leitura").map((u) => <option key={u.id} value={u.id}>{u.nome}</option>)}
            </select>)}
          </Campo>
        )}
        <Campo rotulo="Detalhes">{(p) => <textarea {...p} rows={2} value={descricao} onChange={(e) => setDescricao(e.target.value)} />}</Campo>
      </form>
    </Modal>
  );
}

export function ItemTarefa({ t, aoMudar, mostrarLead }: { t: Tarefa; aoMudar: () => void; mostrarLead?: boolean }) {
  const pode = usePode();
  const toast = useToast();
  const [editar, setEditar] = useState(false);
  const atrasada = t.status === "pendente" && new Date(t.vencimento) < new Date();
  const status = async (s: string) => {
    try { await api.patch(`/tarefas/${t.id}`, { status: s }); toast(s === "concluida" ? "Tarefa concluída." : "Tarefa atualizada."); aoMudar(); }
    catch (err) { toast(err instanceof Error ? err.message : "Erro", "erro"); }
  };
  return (
    <li className={`tarefa-item ${t.status !== "pendente" ? "concluida" : ""}`}>
      <input type="checkbox" aria-label={`Concluir: ${t.titulo}`} checked={t.status === "concluida"} disabled={!pode.editar || t.status === "cancelada"}
        onChange={(e) => status(e.target.checked ? "concluida" : "pendente")} style={{ marginTop: 5 }} />
      <div className="info">
        <div className="titulo">{t.titulo}</div>
        <div className="texto-3">
          {mostrarLead && <><Link to={`/leads/${t.lead.id}`}>{t.lead.nome}</Link>{t.lead.empresa ? ` (${t.lead.empresa})` : ""} · </>}
          <span style={atrasada ? { color: "var(--danger)", fontWeight: 600 } : undefined}>{atrasada ? "Atrasada · " : ""}{dataHora(t.vencimento)}</span>
          {" · "}{t.responsavel.nome}{t.status === "cancelada" ? " · cancelada" : ""}
        </div>
        {t.descricao && <div className="pequeno texto-2">{t.descricao}</div>}
      </div>
      {pode.editar && t.status === "pendente" && (
        <span className="grupo-botoes">
          <button className="btn btn-pequeno btn-fantasma" onClick={() => setEditar(true)} aria-label={`Editar ${t.titulo}`}><Icone nome="editar" tam={15} /></button>
          <button className="btn btn-pequeno btn-fantasma" onClick={() => status("cancelada")} aria-label={`Cancelar ${t.titulo}`}><Icone nome="fechar" tam={15} /></button>
        </span>
      )}
      {editar && <FormTarefa leadId={t.lead_id} tarefa={t} aoFechar={() => setEditar(false)} aoSalvar={() => { setEditar(false); aoMudar(); }} />}
    </li>
  );
}

/* ---------------------------------------------------------------- e-mail */
function EnviarEmail({ lead, aoFechar, aoSalvar }: { lead: Lead; aoFechar: () => void; aoSalvar: () => void }) {
  const toast = useToast();
  const modelos = useCarregar(() => api.get("/modelos-email/ativos"), []);
  const [assunto, setAssunto] = useState("");
  const [corpo, setCorpo] = useState("");
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  return (
    <Modal titulo={`Enviar e-mail para ${lead.nome}`} largo aoFechar={aoFechar} rodape={<>
      <span className="texto-3" style={{ marginRight: "auto" }}>Enviado por comercial@tenti.com.br</span>
      <button className="btn" onClick={aoFechar}>Cancelar</button>
      <button className="btn btn-primario" disabled={ocupado || !assunto || !corpo} onClick={async () => {
        setOcupado(true); setErro("");
        try { await api.post(`/leads/${lead.id}/email`, { assunto, corpo }); toast("E-mail enviado e registrado na linha do tempo."); aoSalvar(); }
        catch (err) { setErro(err instanceof Error ? err.message : "Erro"); } finally { setOcupado(false); }
      }}>{ocupado ? "Enviando…" : "Enviar"}</button>
    </>}>
      <div className="pilha">
        {erro && <Aviso tipo="erro">{erro}</Aviso>}
        <div className="dados-lista"><dt>Para</dt><dd>{lead.email}</dd></div>
        <Campo rotulo="Modelo">{(p) => (
          <select {...p} defaultValue="" onChange={async (e) => {
            if (!e.target.value) return;
            const r = await api.get(`/leads/${lead.id}/email/previa`, { modelo_id: e.target.value });
            setAssunto(r.assunto); setCorpo(r.corpo);
          }}>
            <option value="">Escrever do zero</option>
            {(modelos.dados ?? []).map((m: any) => <option key={m.id} value={m.id}>{m.nome}</option>)}
          </select>)}
        </Campo>
        <Campo rotulo="Assunto" obrigatorio>{(p) => <input {...p} value={assunto} onChange={(e) => setAssunto(e.target.value)} />}</Campo>
        <Campo rotulo="Mensagem" obrigatorio>{(p) => <textarea {...p} rows={10} value={corpo} onChange={(e) => setCorpo(e.target.value)} />}</Campo>
      </div>
    </Modal>
  );
}

/* ---------------------------------------------------------------- página */
export default function LeadDetalhe() {
  const { id } = useParams();
  const nav = useNavigate();
  const pode = usePode();
  const { usuario } = useAuth();
  const toast = useToast();
  const { estagios, usuarios } = useCadastros();
  const lead = useCarregar<Lead>(() => api.get(`/leads/${id}`), [id]);
  const linha = useCarregar<Interacao[]>(() => api.get(`/leads/${id}/interacoes`), [id]);
  const tarefas = useCarregar(() => api.get("/tarefas", { lead_id: id, tamanho: 100 }), [id]);
  const anexos = useCarregar<any[]>(() => api.get(`/leads/${id}/anexos`), [id]);
  const hist = useCarregar(() => api.get(`/leads/${id}/estagios`), [id]);
  const [aba, setAba] = useState<"linha" | "tarefas" | "anexos" | "estagios">("linha");
  const [editar, setEditar] = useState(false);
  const [email, setEmail] = useState(false);
  const [novaTarefa, setNovaTarefa] = useState(false);
  const [estagioModal, setEstagioModal] = useState<Estagio | null>(null);
  const [confirmar, setConfirmar] = useState<null | "excluir" | "anonimizar">(null);
  const [reatribuir, setReatribuir] = useState(false);
  const [novoResp, setNovoResp] = useState("");
  const enviarAnexo = useRef<HTMLInputElement>(null);

  const tudo = () => { lead.recarregar(); linha.recarregar(); tarefas.recarregar(); anexos.recarregar(); hist.recarregar(); };

  if (lead.erro) return <><Link to="/leads" className="btn btn-fantasma"><Icone nome="voltar" />Voltar</Link><Aviso tipo="erro" titulo="Não foi possível abrir o lead">{lead.erro}</Aviso></>;
  if (!lead.dados) return <Carregando />;
  const l = lead.dados;
  const fechado = l.estagio.tipo !== "aberto";
  const podeEditar = pode.editar && !l.anonimizado_em;
  const podeMover = podeEditar && (!fechado || pode.gerir);
  const atual = estagios.find((e) => e.id === l.estagio.id);

  const mover = async (e: Estagio) => {
    if (e.id === l.estagio.id) return;
    if (e.tipo !== "aberto") { setEstagioModal(e); return; }
    try { await api.post(`/leads/${l.id}/estagio`, { estagio_id: e.id }); toast(`Movido para ${e.nome}.`); tudo(); }
    catch (err) { toast(err instanceof Error ? err.message : "Erro", "erro"); }
  };

  return (
    <>
      <div className="flex" style={{ marginBottom: 8 }}><Link to="/leads" className="btn btn-fantasma btn-pequeno"><Icone nome="voltar" tam={16} />Leads</Link></div>
      <div className="cabecalho-pagina">
        <div>
          <div className="flex" style={{ flexWrap: "wrap" }}><h1>{l.nome}</h1><SeloEstagio estagio={l.estagio} /><Etiquetas itens={l.etiquetas} /></div>
          <p>{[l.cargo, l.empresa].filter(Boolean).join(" · ") || "Sem empresa informada"} · responsável <strong>{l.responsavel.nome}</strong></p>
        </div>
        <div className="grupo-botoes">
          {podeEditar && l.telefone && <a className="btn" href={`tel:${l.telefone}`}><Icone nome="telefone" />Ligar</a>}
          {podeEditar && l.email && <button className="btn" onClick={() => setEmail(true)}><Icone nome="email" />Enviar e-mail</button>}
          {podeEditar && <button className="btn" onClick={() => setEditar(true)}><Icone nome="editar" />Editar</button>}
          {pode.gerir && !l.anonimizado_em && <button className="btn btn-fantasma" onClick={() => setConfirmar("excluir")} aria-label="Excluir lead"><Icone nome="lixeira" /></button>}
        </div>
      </div>

      <div className="pilha" style={{ gap: 10, marginBottom: 16 }}>
        {l.anonimizado_em && <Aviso tipo="info">Dados pessoais anonimizados em {data(l.anonimizado_em)} (LGPD). O registro é mantido apenas para estatística.</Aviso>}
        {l.sem_proxima_acao && podeEditar && (
          <Aviso tipo="alerta" titulo="Sem próxima ação agendada">
            Todo lead ativo precisa de um próximo passo. <button className="btn btn-pequeno" style={{ marginLeft: 8 }} onClick={() => setNovaTarefa(true)}>Agendar agora</button>
          </Aviso>
        )}
        {l.parado && <Aviso tipo="alerta" titulo="Lead parado">Último contato {relativo(l.ultimo_contato_em ?? l.criado_em)}. Registre uma interação para retomar.</Aviso>}
      </div>

      <section className="cartao cartao-corpo" aria-label="Funil" style={{ marginBottom: 16 }}>
        <div className="funil-passos" role="group" aria-label="Mover para o estágio">
          {estagios.filter((e) => e.ativo).map((e) => {
            const feito = !fechado && atual && e.tipo === "aberto" && e.ordem < atual.ordem;
            return (
              <button key={e.id} className={`${e.tipo} ${e.id === l.estagio.id ? "atual" : feito ? "feito" : ""}`} aria-current={e.id === l.estagio.id ? "step" : undefined}
                disabled={!podeMover || e.id === l.estagio.id} onClick={() => mover(e)} title={!podeMover && fechado ? "Somente gestor ou administrador reabre leads fechados" : undefined}>
                {e.nome}
              </button>
            );
          })}
        </div>
        {fechado && !pode.gerir && pode.editar && <p className="texto-3" style={{ margin: "8px 0 0" }}>Lead fechado. Apenas gestor ou administrador pode reabrir.</p>}
        {l.estagio.tipo === "ganho" && <p style={{ margin: "10px 0 0" }}><strong style={{ color: "var(--success)" }}>Ganho</strong> em {data(l.fechado_em)} · valor fechado {moeda(l.valor_fechado)}</p>}
        {l.estagio.tipo === "perdido" && <p style={{ margin: "10px 0 0" }}><strong style={{ color: "var(--danger)" }}>Perdido</strong> em {data(l.fechado_em)} · motivo: {l.motivo_perda?.nome}{l.detalhe_perda ? ` — ${l.detalhe_perda}` : ""}</p>}
      </section>

      <div className="detalhe">
        <div>
          <Abas atual={aba} aoMudar={setAba} abas={[
            { id: "linha", rotulo: "Interações" },
            { id: "tarefas", rotulo: `Tarefas (${(tarefas.dados?.itens ?? []).filter((t: Tarefa) => t.status === "pendente").length})` },
            { id: "anexos", rotulo: `Anexos (${anexos.dados?.length ?? 0})` },
            { id: "estagios", rotulo: "Tempo por estágio" },
          ]} />
          {aba === "linha" && (<>
            {podeEditar && <NovaInteracao lead={l} aoSalvar={tudo} />}
            {linha.dados ? <LinhaDoTempo itens={linha.dados} /> : <Carregando />}
          </>)}
          {aba === "tarefas" && (
            <div className="cartao cartao-corpo">
              <div className="flex-entre"><h2>Tarefas e lembretes</h2>{podeEditar && <button className="btn btn-primario btn-pequeno" onClick={() => setNovaTarefa(true)}><Icone nome="mais" tam={16} />Nova tarefa</button>}</div>
              {(tarefas.dados?.itens ?? []).length === 0 ? <p className="texto-2">Nenhuma tarefa.</p> : (
                <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                  {[...tarefas.dados.itens].sort((a: Tarefa, b: Tarefa) => (a.status === "pendente" ? 0 : 1) - (b.status === "pendente" ? 0 : 1)).map((t: Tarefa) => <ItemTarefa key={t.id} t={t} aoMudar={tudo} />)}
                </ul>
              )}
            </div>
          )}
          {aba === "anexos" && (
            <div className="cartao cartao-corpo">
              <div className="flex-entre"><h2>Anexos</h2>
                {podeEditar && <>
                  <input ref={enviarAnexo} type="file" className="sr-only" id="up-anexo" onChange={async (e) => {
                    const f = e.target.files?.[0]; if (!f) return;
                    if (f.size > 10 * 1024 * 1024) { toast("O arquivo excede 10 MB.", "erro"); return; }
                    const fd = new FormData(); fd.append("arquivo", f);
                    try { await api.post(`/leads/${l.id}/anexos`, fd); toast("Anexo enviado."); tudo(); }
                    catch (err) { toast(err instanceof Error ? err.message : "Erro", "erro"); }
                    e.target.value = "";
                  }} />
                  <label htmlFor="up-anexo" className="btn btn-pequeno"><Icone nome="anexo" tam={15} />Enviar arquivo</label>
                </>}
              </div>
              {(anexos.dados ?? []).length === 0 ? <p className="texto-2">Nenhum anexo. Limite de 10 MB por arquivo.</p> : (
                <table><tbody>{anexos.dados!.map((a) => (
                  <tr key={a.id}><td><button className="btn btn-fantasma btn-pequeno" onClick={() => baixar(`/anexos/${a.id}`)}><Icone nome="anexo" tam={15} />{a.nome}</button></td>
                    <td className="num texto-3">{tamanho(a.tamanho)}</td><td className="texto-3">{dataHora(a.criado_em)}</td></tr>))}</tbody></table>
              )}
            </div>
          )}
          {aba === "estagios" && hist.dados && (
            <div className="cartao cartao-corpo">
              <h2>Histórico de estágios</h2>
              <table className="mt">
                <thead><tr><th>Estágio</th><th>Entrada</th><th>Por</th><th className="num">Tempo</th></tr></thead>
                <tbody>{hist.dados.passagens.map((p: any, i: number) => (
                  <tr key={i}><td>{p.para}{p.atual && <span className="selo selo-info" style={{ marginLeft: 6 }}>atual</span>}</td><td>{dataHora(p.data_hora)}</td><td>{p.usuario ?? "Sistema"}</td><td className="num">{duracao(p.segundos_no_estagio)}</td></tr>
                ))}</tbody>
              </table>
            </div>
          )}
        </div>

        <aside className="pilha">
          <section className="cartao">
            <div className="cartao-cab"><h2>Dados</h2></div>
            <dl className="dados-lista cartao-corpo">
              <dt>E-mail</dt><dd>{l.email ? <a href={`mailto:${l.email}`}>{l.email}</a> : "—"}</dd>
              <dt>Telefone</dt><dd>{l.telefone ? <a href={`tel:${l.telefone}`}>{telefone(l.telefone)}</a> : "—"}</dd>
              <dt>Cidade/UF</dt><dd>{[l.cidade, l.uf].filter(Boolean).join(" / ") || "—"}</dd>
              <dt>Interesse</dt><dd>{l.interesse ?? "—"}</dd>
              <dt>Valor estimado</dt><dd>{moeda(l.valor_estimado)}</dd>
              <dt>Origem</dt><dd>{l.origem.nome}</dd>
              <dt>Criado em</dt><dd>{dataHora(l.criado_em)}</dd>
              <dt>Último contato</dt><dd>{l.ultimo_contato_em ? `${dataHora(l.ultimo_contato_em)} (${relativo(l.ultimo_contato_em)})` : "Nenhum"}</dd>
              <dt>Próxima ação</dt><dd>{l.proxima_tarefa ? dataHora(l.proxima_tarefa) : "—"}</dd>
              <dt>No estágio desde</dt><dd>{relativo(l.estagio_desde)}</dd>
              {(l.utm_source || l.utm_medium || l.utm_campaign) && <><dt>UTM</dt><dd>{[l.utm_source, l.utm_medium, l.utm_campaign].filter(Boolean).join(" / ")}</dd></>}
              {l.observacoes && <><dt>Observações</dt><dd style={{ whiteSpace: "pre-wrap" }}>{l.observacoes}</dd></>}
            </dl>
          </section>
          <section className="cartao cartao-corpo">
            <div className="flex-entre"><h3>Responsável</h3>{pode.gerir && !l.anonimizado_em && <button className="btn btn-pequeno" onClick={() => setReatribuir(true)}>Reatribuir</button>}</div>
            <p style={{ margin: "6px 0 0" }} className="flex"><span className="avatar" aria-hidden>{l.responsavel.nome[0]}</span>{l.responsavel.nome}{l.responsavel.id === usuario?.id && " (você)"}</p>
          </section>
          <section className="cartao cartao-corpo">
            <h3 className="flex"><Icone nome="escudo" />LGPD</h3>
            <dl className="dados-lista mt">
              <dt>Base legal</dt><dd>{l.base_legal ? BASES_LEGAIS[l.base_legal] : "Não informada"}</dd>
              <dt>Consentimento</dt><dd>{l.consentimento_em ? `Sim, em ${data(l.consentimento_em)}` : "Não registrado"}</dd>
            </dl>
            {pode.admin && !l.anonimizado_em && (
              <div className="grupo-botoes mt">
                <button className="btn btn-pequeno" onClick={async () => {
                  const d = await api.get(`/lgpd/leads/${l.id}/exportar`);
                  const a = document.createElement("a");
                  a.href = URL.createObjectURL(new Blob([JSON.stringify(d, null, 2)], { type: "application/json" }));
                  a.download = `titular_lead_${l.id}.json`; a.click();
                }}>Exportar dados do titular</button>
                <button className="btn btn-pequeno btn-fantasma" style={{ color: "var(--danger)" }} onClick={() => setConfirmar("anonimizar")}>Anonimizar</button>
              </div>
            )}
          </section>
        </aside>
      </div>

      {editar && <LeadForm lead={l} aoFechar={() => setEditar(false)} aoSalvar={() => { setEditar(false); tudo(); }} />}
      {email && <EnviarEmail lead={l} aoFechar={() => setEmail(false)} aoSalvar={() => { setEmail(false); tudo(); }} />}
      {novaTarefa && <FormTarefa leadId={l.id} aoFechar={() => setNovaTarefa(false)} aoSalvar={() => { setNovaTarefa(false); setAba("tarefas"); tudo(); }} />}
      {estagioModal && <MudarEstagio lead={l} estagio={estagioModal} aoFechar={() => setEstagioModal(null)} aoSalvar={() => { setEstagioModal(null); tudo(); }} />}
      {reatribuir && (
        <Modal titulo="Reatribuir lead" aoFechar={() => setReatribuir(false)} rodape={<>
          <button className="btn" onClick={() => setReatribuir(false)}>Cancelar</button>
          <button className="btn btn-primario" disabled={!novoResp} onClick={async () => {
            try {
              await api.post(`/leads/${l.id}/atribuir`, novoResp === "auto" ? { automatico: true } : { responsavel_id: Number(novoResp) });
              toast("Responsável alterado."); setReatribuir(false); tudo();
            } catch (err) { toast(err instanceof Error ? err.message : "Erro", "erro"); }
          }}>Salvar</button>
        </>}>
          <Campo rotulo="Novo responsável">{(p) => (
            <select {...p} value={novoResp} onChange={(e) => setNovoResp(e.target.value)}>
              <option value="">Selecione…</option><option value="auto">Automático (rodízio/regras)</option>
              {usuarios.filter((u) => u.ativo && u.perfil !== "leitura" && u.id !== l.responsavel.id).map((u) => <option key={u.id} value={u.id}>{u.nome}</option>)}
            </select>)}
          </Campo>
        </Modal>
      )}
      {confirmar === "excluir" && <Confirmar titulo="Excluir lead" perigo textoOk="Excluir" aoFechar={() => setConfirmar(null)}
        mensagem={<p>O lead <strong>{l.nome}</strong> sairá das listas e relatórios. A exclusão é lógica e fica registrada na auditoria.</p>}
        aoConfirmar={async () => { await api.del(`/leads/${l.id}`); toast("Lead excluído."); nav("/leads"); }} />}
      {confirmar === "anonimizar" && <Confirmar titulo="Anonimizar dados do titular" perigo textoOk="Anonimizar definitivamente" aoFechar={() => setConfirmar(null)}
        mensagem={<><p>Atende a pedido de eliminação (LGPD). Nome, contatos, textos das interações e anexos serão <strong>apagados de forma irreversível</strong>.</p><p>Exporte os dados antes, se o titular pediu cópia.</p></>}
        aoConfirmar={async () => { await api.post(`/lgpd/leads/${l.id}/anonimizar`); toast("Dados anonimizados."); setConfirmar(null); tudo(); }} />}
    </>
  );
}
