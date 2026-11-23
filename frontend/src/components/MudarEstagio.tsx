import { useState } from "react";
import { api } from "../api";
import { useCadastros } from "../contexto";
import { hojeISO, paraDecimal } from "../formato";
import type { Estagio, Lead } from "../tipos";
import { Aviso, Campo, errosDeCampo, Modal, useToast } from "../ui";

/** Muda o estágio. Para Perdido exige motivo; para Ganho exige valor e data. */
export async function mudarEstagioDireto(lead: Pick<Lead, "id">, estagio: Estagio): Promise<Lead> {
  return api.post<Lead>(`/leads/${lead.id}/estagio`, { estagio_id: estagio.id });
}

export default function MudarEstagio({ lead, estagio, aoFechar, aoSalvar }: {
  lead: Pick<Lead, "id" | "nome" | "valor_estimado">; estagio: Estagio; aoFechar: () => void; aoSalvar: (l: Lead) => void;
}) {
  const { motivos } = useCadastros();
  const toast = useToast();
  const [motivo, setMotivo] = useState("");
  const [detalhe, setDetalhe] = useState("");
  const [valor, setValor] = useState(lead.valor_estimado ? String(Number(lead.valor_estimado)).replace(".", ",") : "");
  const [data, setData] = useState(hojeISO());
  const [erros, setErros] = useState<Record<string, string>>({});
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const perdido = estagio.tipo === "perdido";

  const salvar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (perdido && !motivo) return setErros({ motivo_perda_id: "Escolha o motivo da perda." });
    if (!perdido && !valor) return setErros({ valor_fechado: "Informe o valor fechado." });
    setOcupado(true);
    try {
      const r = await api.post<Lead>(`/leads/${lead.id}/estagio`, perdido
        ? { estagio_id: estagio.id, motivo_perda_id: Number(motivo), detalhe_perda: detalhe || null }
        : { estagio_id: estagio.id, valor_fechado: paraDecimal(valor), fechado_em: data });
      toast(perdido ? "Lead marcado como perdido." : "Negócio ganho registrado! 🎉");
      aoSalvar(r);
    } catch (err) { setErros(errosDeCampo(err)); setErro(err instanceof Error ? err.message : "Erro"); }
    finally { setOcupado(false); }
  };

  return (
    <Modal titulo={perdido ? `Marcar “${lead.nome}” como perdido` : `Registrar ganho — ${lead.nome}`} aoFechar={aoFechar} rodape={<>
      <button className="btn" onClick={aoFechar}>Cancelar</button>
      <button form="form-estagio" className={`btn ${perdido ? "btn-perigo" : "btn-sucesso"}`} disabled={ocupado}>{perdido ? "Marcar como perdido" : "Registrar ganho"}</button>
    </>}>
      <form id="form-estagio" onSubmit={salvar} className="pilha" noValidate>
        {erro && <Aviso tipo="erro">{erro}</Aviso>}
        {perdido ? (<>
          <Campo rotulo="Motivo da perda" erro={erros.motivo_perda_id} obrigatorio>{(p) => (
            <select {...p} value={motivo} onChange={(e) => setMotivo(e.target.value)}>
              <option value="">Selecione…</option>
              {motivos.filter((m) => m.ativo).map((m) => <option key={m.id} value={m.id}>{m.nome}</option>)}
            </select>)}
          </Campo>
          <Campo rotulo="Detalhes (opcional)">{(p) => <textarea {...p} value={detalhe} onChange={(e) => setDetalhe(e.target.value)} rows={3} />}</Campo>
        </>) : (<div className="grade grade-2">
          <Campo rotulo="Valor fechado (R$)" erro={erros.valor_fechado} obrigatorio>{(p) => <input {...p} inputMode="decimal" value={valor} onChange={(e) => setValor(e.target.value.replace(/[^\d,.]/g, ""))} />}</Campo>
          <Campo rotulo="Data do fechamento" erro={erros.fechado_em} obrigatorio>{(p) => <input {...p} type="date" max={hojeISO()} value={data} onChange={(e) => setData(e.target.value)} />}</Campo>
        </div>)}
      </form>
    </Modal>
  );
}
