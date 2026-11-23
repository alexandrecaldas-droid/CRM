import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, baixar } from "../api";
import { useCadastros, usePode } from "../contexto";
import { dataHora } from "../formato";
import { Aviso, Campo, Carregando, Icone, useCarregar, useToast } from "../ui";

type Etapa = "arquivo" | "mapear" | "processando" | "resultado";
const PASSOS: [Etapa, string][] = [["arquivo", "1. Arquivo"], ["mapear", "2. Colunas e opções"], ["processando", "3. Processamento"], ["resultado", "4. Resultado"]];

export default function Importar() {
  const pode = usePode();
  const toast = useToast();
  const { origens, usuarios } = useCadastros();
  const campos = useCarregar<Record<string, string>>(() => api.get("/importacoes/campos"), []);
  const historico = useCarregar<any[]>(() => api.get("/importacoes"), []);
  const [etapa, setEtapa] = useState<Etapa>("arquivo");
  const [imp, setImp] = useState<any>(null);
  const [mapa, setMapa] = useState<Record<string, string>>({});
  const [origem, setOrigem] = useState("");
  const [resp, setResp] = useState("");
  const [dup, setDup] = useState("ignorar");
  const [erro, setErro] = useState("");
  const [arrastando, setArrastando] = useState(false);
  const [ocupado, setOcupado] = useState(false);

  const enviar = async (f: File) => {
    setErro(""); setOcupado(true);
    const fd = new FormData(); fd.append("arquivo", f);
    try {
      const r = await api.post("/importacoes", fd);
      setImp(r); setMapa(Object.fromEntries(r.colunas.map((c: string) => [c, r.mapeamento?.[c] ?? ""]))); setEtapa("mapear");
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro"); } finally { setOcupado(false); }
  };

  useEffect(() => {
    if (etapa !== "processando" || !imp) return;
    const t = setInterval(async () => {
      const r = await api.get(`/importacoes/${imp.id}`);
      setImp(r);
      if (r.status === "concluida" || r.status === "erro") { setEtapa("resultado"); historico.recarregar(); clearInterval(t); }
    }, 1500);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [etapa, imp?.id]);

  const usados = Object.values(mapa).filter(Boolean);
  const temMinimo = usados.includes("nome") && (usados.includes("email") || usados.includes("telefone"));
  const processar = async () => {
    setErro(""); setOcupado(true);
    try {
      await api.post(`/importacoes/${imp.id}/processar`, { mapeamento: mapa, origem_id: origem ? Number(origem) : null, responsavel_id: resp ? Number(resp) : null, duplicados: dup });
      setEtapa("processando");
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro"); } finally { setOcupado(false); }
  };

  return (
    <>
      <div className="cabecalho-pagina">
        <div><h1>Importar leads</h1><p>Planilha CSV ou XLSX. Linhas válidas são importadas; as inválidas voltam em um relatório.</p></div>
        <button className="btn" onClick={() => baixar("/importacoes/modelo.csv")}><Icone nome="baixar" />Baixar planilha modelo</button>
      </div>
      <ol className="funil-passos" style={{ listStyle: "none", padding: 0, marginBottom: 16 }} aria-label="Etapas">
        {PASSOS.map(([k, r], i) => {
          const idx = PASSOS.findIndex(([x]) => x === etapa);
          return <li key={k} style={{ flex: 1 }}><span className={`btn ${i === idx ? "btn-primario" : ""}`} style={{ width: "100%", cursor: "default", opacity: i > idx ? 0.6 : 1 }} aria-current={i === idx ? "step" : undefined}>{r}</span></li>;
        })}
      </ol>
      {erro && <Aviso tipo="erro">{erro}</Aviso>}

      {etapa === "arquivo" && (
        <div className="cartao cartao-corpo">
          <label className={`zona-arquivo ${arrastando ? "ativa" : ""}`} style={{ display: "block" }}
            onDragOver={(e) => { e.preventDefault(); setArrastando(true); }} onDragLeave={() => setArrastando(false)}
            onDrop={(e) => { e.preventDefault(); setArrastando(false); const f = e.dataTransfer.files[0]; if (f) enviar(f); }}>
            <Icone nome="importar" tam={36} />
            <p><strong>Arraste a planilha aqui ou clique para escolher</strong></p>
            <p className="texto-3">.csv (separado por ; ou ,) ou .xlsx · até 20 MB · até 20 mil linhas</p>
            <input type="file" accept=".csv,.xlsx,.txt" className="sr-only" onChange={(e) => e.target.files?.[0] && enviar(e.target.files[0])} />
          </label>
          {ocupado && <Carregando texto="Lendo planilha…" />}
        </div>
      )}

      {etapa === "mapear" && imp && (
        <div className="pilha">
          <section className="cartao">
            <div className="cartao-cab"><h2>Relacione as colunas</h2><span className="texto-3">{imp.nome_arquivo} · {imp.total} linha(s)</span></div>
            <div className="tabela-wrap">
              <table>
                <thead><tr><th>Coluna da planilha</th><th>Campo no sistema</th><th>Exemplos</th></tr></thead>
                <tbody>{imp.colunas.map((c: string, i: number) => (
                  <tr key={c}>
                    <td><strong>{c}</strong></td>
                    <td style={{ minWidth: 220 }}>
                      <select aria-label={`Campo para a coluna ${c}`} value={mapa[c] ?? ""} onChange={(e) => setMapa({ ...mapa, [c]: e.target.value })}>
                        <option value="">— Ignorar —</option>
                        {Object.entries(campos.dados ?? {}).map(([k, v]) => <option key={k} value={k} disabled={usados.includes(k) && mapa[c] !== k}>{v}</option>)}
                      </select>
                    </td>
                    <td className="texto-3">{imp.amostra.slice(0, 3).map((r: string[]) => r[i]).filter(Boolean).join(" · ") || "—"}</td>
                  </tr>))}
                </tbody>
              </table>
            </div>
          </section>
          {!temMinimo && <Aviso tipo="alerta">Mapeie ao menos <strong>Nome</strong> e um contato (<strong>E-mail</strong> ou <strong>Telefone</strong>).</Aviso>}
          <section className="cartao cartao-corpo">
            <h2>Opções</h2>
            <div className="grade grade-3 mt">
              <Campo rotulo="Origem padrão" ajuda={usados.includes("origem") ? "Usada quando a coluna de origem estiver vazia." : "Obrigatória: a planilha não tem coluna de origem mapeada."} obrigatorio={!usados.includes("origem")}>{(p) => (
                <select {...p} value={origem} onChange={(e) => setOrigem(e.target.value)}>
                  <option value="">Selecione…</option>{origens.filter((o) => o.ativa).map((o) => <option key={o.id} value={o.id}>{o.nome}</option>)}
                </select>)}
              </Campo>
              {pode.gerir && (
                <Campo rotulo="Responsável" ajuda="Automático: distribui por rodízio/regras.">{(p) => (
                  <select {...p} value={resp} onChange={(e) => setResp(e.target.value)}>
                    <option value="">Automático</option>
                    {usuarios.filter((u) => u.ativo && u.perfil !== "leitura").map((u) => <option key={u.id} value={u.id}>{u.nome}</option>)}
                  </select>)}
                </Campo>
              )}
              <Campo rotulo="Contatos já cadastrados">{(p) => (
                <select {...p} value={dup} onChange={(e) => setDup(e.target.value)}>
                  <option value="ignorar">Ignorar a linha (recomendado)</option>
                  <option value="atualizar">Completar campos vazios do lead existente</option>
                  <option value="criar">Criar duplicado mesmo assim</option>
                </select>)}
              </Campo>
            </div>
          </section>
          <div className="grupo-botoes">
            <button className="btn" onClick={() => { setEtapa("arquivo"); setImp(null); }}>Voltar</button>
            <button className="btn btn-primario" disabled={!temMinimo || (!origem && !usados.includes("origem")) || ocupado} onClick={processar}>Importar {imp.total} linha(s)</button>
          </div>
        </div>
      )}

      {etapa === "processando" && <div className="cartao"><Carregando texto="Importando… você pode sair desta tela; avisaremos por notificação ao concluir." /></div>}

      {etapa === "resultado" && imp && (
        <div className="pilha">
          {imp.status === "erro" ? <Aviso tipo="erro">A importação falhou. Verifique o arquivo e tente de novo.</Aviso> : (
            <section className="kpis" style={{ marginBottom: 0 }}>
              <div className="cartao kpi bom"><span className="rotulo-kpi">Importados</span><span className="valor">{imp.importados}</span></div>
              <div className="cartao kpi"><span className="rotulo-kpi">Atualizados</span><span className="valor">{imp.atualizados}</span></div>
              <div className="cartao kpi"><span className="rotulo-kpi">Ignorados (duplicados)</span><span className="valor">{imp.ignorados}</span></div>
              <div className={`cartao kpi ${imp.rejeitados ? "alerta" : ""}`}><span className="rotulo-kpi">Rejeitados</span><span className="valor">{imp.rejeitados}</span></div>
            </section>
          )}
          {imp.total_erros > 0 && (
            <section className="cartao">
              <div className="cartao-cab"><h2>Linhas não importadas</h2>
                <button className="btn btn-pequeno" onClick={() => baixar(`/importacoes/${imp.id}/erros.csv`)}><Icone nome="baixar" tam={15} />Baixar relatório</button></div>
              <div className="tabela-wrap"><table>
                <thead><tr><th className="num">Linha</th><th>Situação</th><th>Motivo</th></tr></thead>
                <tbody>{imp.erros.slice(0, 100).map((e: any) => (
                  <tr key={e.linha}><td className="num">{e.linha}</td><td><span className={`selo ${e.tipo === "rejeitado" ? "selo-alerta" : "selo-aviso"}`}>{e.tipo}</span></td><td>{e.mensagem}</td></tr>))}</tbody>
              </table></div>
            </section>
          )}
          <div className="grupo-botoes">
            <Link to="/leads?visao=lista&ordenar=criado_em&direcao=desc" className="btn btn-primario">Ver leads</Link>
            <button className="btn" onClick={() => { setEtapa("arquivo"); setImp(null); toast("Pronto para nova importação.", "info"); }}>Nova importação</button>
          </div>
        </div>
      )}

      {(historico.dados ?? []).length > 0 && etapa === "arquivo" && (
        <section className="cartao mt">
          <div className="cartao-cab"><h2>Importações recentes</h2></div>
          <div className="tabela-wrap"><table className="responsiva">
            <thead><tr><th>Arquivo</th><th>Data</th><th>Situação</th><th className="num">Importados</th><th className="num">Rejeitados</th><th /></tr></thead>
            <tbody>{historico.dados!.map((h) => (
              <tr key={h.id}>
                <td data-rotulo="Arquivo">{h.nome_arquivo}</td><td data-rotulo="Data">{dataHora(h.criado_em)}</td><td data-rotulo="Situação">{h.status}</td>
                <td data-rotulo="Importados" className="num">{h.importados}</td><td data-rotulo="Rejeitados" className="num">{h.rejeitados}</td>
                <td>{h.status === "concluida" && h.total_erros > 0 && <button className="btn btn-pequeno" onClick={() => baixar(`/importacoes/${h.id}/erros.csv`)}>Erros</button>}
                  {h.status === "rascunho" && <button className="btn btn-pequeno" onClick={async () => { const r = await api.get(`/importacoes/${h.id}`); setImp({ ...r, amostra: [] }); setMapa(Object.fromEntries(r.colunas.map((c: string) => [c, r.mapeamento?.[c] ?? ""]))); setEtapa("mapear"); }}>Continuar</button>}</td>
              </tr>))}</tbody>
          </table></div>
        </section>
      )}
    </>
  );
}
