import { useState } from "react";
import { Link } from "react-router-dom";
import { api, baixar } from "../api";
import { usePode } from "../contexto";
import { hojeISO, horas, moeda } from "../formato";
import { Abas, Aviso, Carregando, Icone, useCarregar, useToast } from "../ui";
import { linkLista, SeletorPeriodo } from "./Painel";

type Aba = "origens" | "vendedores" | "motivos" | "funil";
const ROTAS: Record<Aba, string> = { origens: "/relatorios/origens", vendedores: "/relatorios/vendedores", motivos: "/relatorios/motivos-perda", funil: "/relatorios/funil" };

const pct = (v?: number | null) => (v === null || v === undefined ? "—" : `${v.toLocaleString("pt-BR")}%`);

export default function Relatorios() {
  const pode = usePode();
  const toast = useToast();
  const [aba, setAba] = useState<Aba>("origens");
  const [de, setDe] = useState(hojeISO(-89));
  const [ate, setAte] = useState(hojeISO());
  const { dados, erro, carregando } = useCarregar(() => api.get(ROTAS[aba], { de, ate }), [aba, de, ate]);
  const exportar = (formato: string) => baixar("/exportacoes", { tipo: aba, formato, de, ate }).catch((e) => toast(e.message, "erro"));
  const max = Math.max(1, ...((dados?.linhas ?? []) as any[]).map((l) => l.total));

  return (
    <>
      <div className="cabecalho-pagina">
        <div><h1>Relatórios</h1><p>Quebras por origem, vendedor, motivo de perda e funil. Clique em uma linha para ver os leads.</p></div>
        <div className="grupo-botoes">
          <SeletorPeriodo de={de} ate={ate} aoMudar={(d, a) => { setDe(d); setAte(a); }} />
          {pode.exportar && <>
            <button className="btn" onClick={() => exportar("xlsx")}><Icone nome="baixar" />XLSX</button>
            <button className="btn" onClick={() => exportar("csv")}><Icone nome="baixar" />CSV</button>
          </>}
        </div>
      </div>
      <Abas atual={aba} aoMudar={setAba} abas={[{ id: "origens", rotulo: "Por origem" }, { id: "vendedores", rotulo: "Por vendedor" }, { id: "motivos", rotulo: "Motivos de perda" }, { id: "funil", rotulo: "Funil" }]} />
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      {carregando && !dados ? <Carregando /> : dados && (
        <div className="cartao">
          <div className="tabela-wrap">
            {(aba === "origens" || aba === "vendedores") && (
              <table className="responsiva">
                <caption className="sr-only">Leads criados no período por {aba === "origens" ? "origem" : "vendedor"}</caption>
                <thead><tr><th>{aba === "origens" ? "Origem" : "Vendedor"}</th><th className="num">Leads</th><th className="num">Abertos</th><th className="num">Ganhos</th><th className="num">Perdidos</th><th className="num">Conversão</th><th className="num">Valor ganho</th>
                  {aba === "vendedores" && <><th className="num">1º contato</th><th className="num">Tarefas atrasadas</th></>}</tr></thead>
                <tbody>{dados.linhas.map((l: any) => (
                  <tr key={l.id}>
                    <td data-rotulo="Nome"><Link className="link-linha" to={linkLista(l.filtros)}>{l.nome}</Link>
                      <div className="barra-trilho esconder-movel" style={{ height: 6, marginTop: 4 }}><div className="barra-preenchida" style={{ width: `${(l.total / max) * 100}%` }} /></div></td>
                    <td data-rotulo="Leads" className="num">{l.total}</td><td data-rotulo="Abertos" className="num">{l.abertos}</td>
                    <td data-rotulo="Ganhos" className="num">{l.ganhos}</td><td data-rotulo="Perdidos" className="num">{l.perdidos}</td>
                    <td data-rotulo="Conversão" className="num">{pct(l.conversao)}</td><td data-rotulo="Valor ganho" className="num">{moeda(l.valor_ganho)}</td>
                    {aba === "vendedores" && <><td data-rotulo="1º contato" className="num">{horas(l.primeiro_contato_horas)}</td><td data-rotulo="Atrasadas" className="num">{l.tarefas_atrasadas}</td></>}
                  </tr>))}
                </tbody>
              </table>
            )}
            {aba === "motivos" && (
              <div className="cartao-corpo">
                <p className="texto-2" style={{ marginTop: 0 }}>{dados.total} lead(s) perdido(s) no período.</p>
                <div className="barras">{dados.linhas.map((l: any) => (
                  <Link key={l.id ?? 0} className="barra-linha" to={linkLista({ status: "perdido", fechado_de: de, fechado_ate: ate })}>
                    <span className="barra-nome">{l.nome}</span>
                    <span className="barra-trilho"><span className="barra-preenchida" style={{ width: `${l.percentual}%`, ["--cor" as string]: "var(--danger)" }} /></span>
                    <span className="barra-valor">{l.total} · {pct(l.percentual)}</span>
                  </Link>))}
                  {!dados.linhas.length && <p className="texto-2">Nenhuma perda no período.</p>}
                </div>
              </div>
            )}
            {aba === "funil" && (
              <table className="responsiva">
                <thead><tr><th>Estágio</th><th className="num">Leads hoje</th><th className="num">Valor</th><th className="num">Dias médios no estágio</th><th className="num">Chegaram (novos do período)</th><th className="num">Conversão da etapa</th></tr></thead>
                <tbody>{dados.linhas.map((l: any) => (
                  <tr key={l.id}>
                    <td data-rotulo="Estágio"><Link className="link-linha" to={linkLista(l.filtros)}>{l.nome}</Link></td>
                    <td data-rotulo="Leads" className="num">{l.total}</td><td data-rotulo="Valor" className="num">{moeda(l.valor)}</td>
                    <td data-rotulo="Dias médios" className="num">{l.dias_medios ?? "—"}</td><td data-rotulo="Chegaram" className="num">{l.chegaram ?? "—"}</td>
                    <td data-rotulo="Conversão" className="num">{pct(l.taxa_etapa)}</td>
                  </tr>))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </>
  );
}
