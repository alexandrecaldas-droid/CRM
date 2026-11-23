import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ErroApi } from "../api";
import { useCadastros, usePode } from "../contexto";
import { BASES_LEGAIS, paraDecimal, UFS } from "../formato";
import type { Lead } from "../tipos";
import { Aviso, Campo, errosDeCampo, Modal, useToast } from "../ui";

interface Dup { id: number | null; nome: string; email: string | null; telefone: string | null; responsavel: string; estagio: string; acessivel: boolean }

const VAZIO = {
  nome: "", email: "", telefone: "", origem_id: "", empresa: "", cargo: "", cidade: "", uf: "", interesse: "",
  valor_estimado: "", observacoes: "", etiqueta_ids: [] as number[], responsavel_id: "", base_legal: "", consentimento: false,
};

export default function LeadForm({ lead, aoFechar, aoSalvar }: { lead?: Lead; aoFechar: () => void; aoSalvar: (l: Lead) => void }) {
  const { origens, etiquetas, usuarios } = useCadastros();
  const pode = usePode();
  const toast = useToast();
  const nav = useNavigate();
  const [f, setF] = useState(() => lead ? {
    nome: lead.nome, email: lead.email ?? "", telefone: lead.telefone ?? "", origem_id: String(lead.origem.id),
    empresa: lead.empresa ?? "", cargo: lead.cargo ?? "", cidade: lead.cidade ?? "", uf: lead.uf ?? "",
    interesse: lead.interesse ?? "", valor_estimado: lead.valor_estimado ? String(Number(lead.valor_estimado)).replace(".", ",") : "", observacoes: lead.observacoes ?? "",
    etiqueta_ids: lead.etiquetas.map((e) => e.id), responsavel_id: "", base_legal: lead.base_legal ?? "",
    consentimento: !!lead.consentimento_em,
  } : VAZIO);
  const [erros, setErros] = useState<Record<string, string>>({});
  const [erroGeral, setErroGeral] = useState("");
  const [dups, setDups] = useState<Dup[]>([]);
  const [confirmarDup, setConfirmarDup] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const set = (k: string, v: unknown) => { setF((x) => ({ ...x, [k]: v })); setErros((e) => ({ ...e, [k]: "" })); };

  // Aviso de duplicidade em tempo real (ao sair do campo de e-mail/telefone).
  const checarDup = async () => {
    if (!f.email && !f.telefone) return setDups([]);
    try {
      const r = await api.get("/leads/duplicados", { email: f.email || undefined, telefone: f.telefone || undefined, ignorar_id: lead?.id });
      setDups(r.duplicados);
    } catch { /* silencioso */ }
  };
  useEffect(() => { setConfirmarDup(false); }, [f.email, f.telefone]);

  const salvar = async (e: React.FormEvent) => {
    e.preventDefault();
    setErroGeral("");
    const loc: Record<string, string> = {};
    if (!f.nome.trim()) loc.nome = "Informe o nome.";
    if (!f.email.trim() && !f.telefone.trim()) loc.email = "Informe e-mail ou telefone.";
    if (!f.origem_id) loc.origem_id = "Escolha a origem.";
    if (Object.keys(loc).length) { setErros(loc); return; }
    if (dups.length && !confirmarDup) { setConfirmarDup(true); return; }
    const corpo: Record<string, unknown> = {
      ...f, origem_id: Number(f.origem_id), valor_estimado: paraDecimal(f.valor_estimado),
      email: f.email || null, telefone: f.telefone || null, uf: f.uf || null, base_legal: f.base_legal || null,
      responsavel_id: f.responsavel_id ? Number(f.responsavel_id) : null, forcar_duplicado: confirmarDup,
    };
    if (lead) delete corpo.responsavel_id;
    setOcupado(true);
    try {
      const r = lead ? await api.patch<Lead>(`/leads/${lead.id}`, corpo) : await api.post<Lead>("/leads", corpo);
      toast(lead ? "Lead atualizado." : "Lead cadastrado.");
      aoSalvar(r);
    } catch (err) {
      if (err instanceof ErroApi && err.codigo === "lead_duplicado") { setDups(err.detalhes.duplicados); setConfirmarDup(true); }
      else { setErros(errosDeCampo(err)); setErroGeral(err instanceof Error ? err.message : "Erro ao salvar."); }
    } finally { setOcupado(false); }
  };

  const mesclar = async (d: Dup) => {
    if (!lead || !d.id) return;
    try {
      await api.post("/leads/mesclar", { principal_id: d.id, secundario_id: lead.id });
      toast("Leads mesclados.");
      nav(`/leads/${d.id}`);
      aoFechar();
    } catch (err) { setErroGeral(err instanceof Error ? err.message : "Erro"); }
  };

  return (
    <Modal titulo={lead ? "Editar lead" : "Novo lead"} aoFechar={aoFechar} largo rodape={<>
      <button type="button" className="btn" onClick={aoFechar}>Cancelar</button>
      <button type="submit" form="form-lead" className={`btn ${confirmarDup ? "btn-perigo" : "btn-primario"}`} disabled={ocupado}>
        {ocupado ? "Salvando…" : confirmarDup ? "Salvar mesmo assim" : "Salvar"}
      </button>
    </>}>
      <form id="form-lead" onSubmit={salvar} noValidate className="pilha">
        {erroGeral && <Aviso tipo="erro">{erroGeral}</Aviso>}
        {dups.length > 0 && (
          <Aviso tipo="alerta" titulo="Possível duplicidade">
            <p style={{ margin: "4px 0" }}>Já existe lead com este e-mail ou telefone:</p>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {dups.map((d, i) => (
                <li key={i}>
                  {d.acessivel ? <strong>{d.nome}</strong> : <em>Lead de outro vendedor</em>} — {d.estagio}, responsável {d.responsavel}
                  {d.acessivel && d.id && <> · <a href={`/leads/${d.id}`} onClick={(e) => { e.preventDefault(); aoFechar(); nav(`/leads/${d.id}`); }}>abrir existente</a></>}
                  {d.acessivel && d.id && lead && <> · <button type="button" className="btn btn-pequeno" onClick={() => mesclar(d)}>mesclar este nele</button></>}
                </li>
              ))}
            </ul>
            {!dups.some((d) => d.acessivel) && <p style={{ margin: "4px 0 0" }}>Peça ao gestor para verificar antes de cadastrar.</p>}
            {confirmarDup && <p style={{ margin: "6px 0 0" }}><strong>Clique em “Salvar mesmo assim” para confirmar o cadastro duplicado.</strong></p>}
          </Aviso>
        )}
        <div className="grade grade-2">
          <Campo rotulo="Nome" erro={erros.nome} obrigatorio className="span-2">{(p) => <input {...p} value={f.nome} onChange={(e) => set("nome", e.target.value)} maxLength={200} autoComplete="off" />}</Campo>
          <Campo rotulo="E-mail" erro={erros.email} ajuda="Informe e-mail e/ou telefone.">{(p) => <input {...p} type="email" value={f.email} onChange={(e) => set("email", e.target.value)} onBlur={checarDup} autoComplete="off" />}</Campo>
          <Campo rotulo="Telefone" erro={erros.telefone} ajuda="Com DDD. Ex.: (11) 98765-4321">{(p) => <input {...p} type="tel" value={f.telefone} onChange={(e) => set("telefone", e.target.value)} onBlur={checarDup} autoComplete="off" />}</Campo>
          <Campo rotulo="Origem" erro={erros.origem_id} obrigatorio>{(p) => (
            <select {...p} value={f.origem_id} onChange={(e) => set("origem_id", e.target.value)}>
              <option value="">Selecione…</option>
              {origens.filter((o) => o.ativa || String(o.id) === f.origem_id).map((o) => <option key={o.id} value={o.id}>{o.nome}</option>)}
            </select>)}
          </Campo>
          {!lead && pode.gerir ? (
            <Campo rotulo="Responsável" ajuda="Em branco: distribuição automática (rodízio).">{(p) => (
              <select {...p} value={f.responsavel_id} onChange={(e) => set("responsavel_id", e.target.value)}>
                <option value="">Automático</option>
                {usuarios.filter((u) => u.ativo && u.perfil !== "leitura").map((u) => <option key={u.id} value={u.id}>{u.nome}</option>)}
              </select>)}
            </Campo>
          ) : <div />}
          <Campo rotulo="Empresa">{(p) => <input {...p} value={f.empresa} onChange={(e) => set("empresa", e.target.value)} />}</Campo>
          <Campo rotulo="Cargo">{(p) => <input {...p} value={f.cargo} onChange={(e) => set("cargo", e.target.value)} />}</Campo>
          <Campo rotulo="Cidade">{(p) => <input {...p} value={f.cidade} onChange={(e) => set("cidade", e.target.value)} />}</Campo>
          <Campo rotulo="UF" erro={erros.uf}>{(p) => (
            <select {...p} value={f.uf} onChange={(e) => set("uf", e.target.value)}>
              <option value="">—</option>{UFS.map((u) => <option key={u}>{u}</option>)}
            </select>)}
          </Campo>
          <Campo rotulo="Produto ou serviço de interesse">{(p) => <input {...p} value={f.interesse} onChange={(e) => set("interesse", e.target.value)} />}</Campo>
          <Campo rotulo="Valor estimado (R$)" erro={erros.valor_estimado}>{(p) => <input {...p} inputMode="decimal" value={f.valor_estimado} onChange={(e) => set("valor_estimado", e.target.value.replace(/[^\d,.]/g, ""))} placeholder="0,00" />}</Campo>
          <fieldset className="span-2" style={{ border: 0, padding: 0, margin: 0 }}>
            <legend className="rotulo">Etiquetas</legend>
            <div className="flex" style={{ flexWrap: "wrap", marginTop: 6 }}>
              {etiquetas.map((e) => (
                <label key={e.id} className="check"><input type="checkbox" checked={f.etiqueta_ids.includes(e.id)}
                  onChange={(ev) => set("etiqueta_ids", ev.target.checked ? [...f.etiqueta_ids, e.id] : f.etiqueta_ids.filter((x) => x !== e.id))} />
                  <span className="etiqueta" style={{ ["--cor" as string]: e.cor }}>{e.nome}</span></label>
              ))}
              {!etiquetas.length && <span className="texto-3">Nenhuma etiqueta cadastrada.</span>}
            </div>
          </fieldset>
          <Campo rotulo="Observações" className="span-2">{(p) => <textarea {...p} value={f.observacoes} onChange={(e) => set("observacoes", e.target.value)} rows={3} />}</Campo>
          <Campo rotulo="Base legal (LGPD)" ajuda="Fundamento para tratar os dados deste contato.">{(p) => (
            <select {...p} value={f.base_legal} onChange={(e) => set("base_legal", e.target.value)}>
              <option value="">Não informada</option>
              {Object.entries(BASES_LEGAIS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>)}
          </Campo>
          <label className="check" style={{ alignSelf: "center" }}>
            <input type="checkbox" checked={f.consentimento} onChange={(e) => set("consentimento", e.target.checked)} />
            O titular consentiu com o contato comercial
          </label>
        </div>
      </form>
    </Modal>
  );
}
