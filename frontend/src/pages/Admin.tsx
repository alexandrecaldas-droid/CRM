import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useCadastros } from "../contexto";
import { dataHora, PERFIS, telefone, UFS } from "../formato";
import type { Usuario } from "../tipos";
import { Abas, Aviso, Campo, Carregando, Confirmar, errosDeCampo, Icone, Modal, Paginacao, useCarregar, useToast } from "../ui";

type Aba = "usuarios" | "funil" | "origens" | "motivos" | "etiquetas" | "atribuicao" | "captura" | "modelos" | "parametros" | "auditoria" | "lgpd";

/* ---------------------------------------------------------------- usuários */
function Usuarios() {
  const toast = useToast();
  const { usuarios, recarregar } = useCadastros();
  const [edit, setEdit] = useState<Partial<Usuario> & { senha?: string } | null>(null);
  const [erros, setErros] = useState<Record<string, string>>({});
  const salvar = async () => {
    setErros({});
    try {
      const corpo: any = { nome: edit!.nome, email: edit!.email, perfil: edit!.perfil, ativo: edit!.ativo ?? true, uf_regiao: edit!.uf_regiao || null };
      if (edit!.senha) corpo.senha = edit!.senha;
      if (edit!.id) await api.patch(`/usuarios/${edit!.id}`, corpo); else await api.post("/usuarios", corpo);
      toast("Usuário salvo."); setEdit(null); recarregar();
    } catch (e) { setErros({ ...errosDeCampo(e), geral: e instanceof Error ? e.message : "" }); }
  };
  return (
    <section className="cartao">
      <div className="cartao-cab"><h2>Usuários</h2><button className="btn btn-primario btn-pequeno" onClick={() => setEdit({ perfil: "vendedor", ativo: true })}><Icone nome="mais" tam={16} />Novo usuário</button></div>
      <div className="tabela-wrap"><table className="responsiva">
        <thead><tr><th>Nome</th><th>E-mail</th><th>Perfil</th><th>2FA</th><th>Último acesso</th><th>Situação</th><th /></tr></thead>
        <tbody>{usuarios.map((u) => (
          <tr key={u.id}>
            <td data-rotulo="Nome"><strong>{u.nome}</strong></td><td data-rotulo="E-mail">{u.email}</td><td data-rotulo="Perfil">{PERFIS[u.perfil]}</td>
            <td data-rotulo="2FA">{u.totp_ativo ? "Ativo" : "—"}</td><td data-rotulo="Último acesso">{dataHora(u.ultimo_login_em)}</td>
            <td data-rotulo="Situação"><span className={`selo ${u.ativo ? "selo-ok" : ""}`}>{u.ativo ? "Ativo" : "Inativo"}</span></td>
            <td><button className="btn btn-pequeno" onClick={() => setEdit(u)}>Editar</button></td>
          </tr>))}</tbody>
      </table></div>
      {edit && (
        <Modal titulo={edit.id ? "Editar usuário" : "Novo usuário"} aoFechar={() => setEdit(null)} rodape={<>
          <button className="btn" onClick={() => setEdit(null)}>Cancelar</button><button className="btn btn-primario" onClick={salvar}>Salvar</button>
        </>}>
          <div className="grade grade-2">
            {erros.geral && <div className="span-2"><Aviso tipo="erro">{erros.geral}</Aviso></div>}
            <Campo rotulo="Nome" erro={erros.nome} obrigatorio>{(p) => <input {...p} value={edit.nome ?? ""} onChange={(e) => setEdit({ ...edit, nome: e.target.value })} />}</Campo>
            <Campo rotulo="E-mail" erro={erros.email} obrigatorio>{(p) => <input {...p} type="email" value={edit.email ?? ""} onChange={(e) => setEdit({ ...edit, email: e.target.value })} />}</Campo>
            <Campo rotulo="Perfil" obrigatorio>{(p) => (
              <select {...p} value={edit.perfil} onChange={(e) => setEdit({ ...edit, perfil: e.target.value as Usuario["perfil"] })}>
                {Object.entries(PERFIS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>)}
            </Campo>
            <Campo rotulo="Região (UF)" ajuda="Informativo; regras de região ficam em Atribuição.">{(p) => (
              <select {...p} value={edit.uf_regiao ?? ""} onChange={(e) => setEdit({ ...edit, uf_regiao: e.target.value })}><option value="">—</option>{UFS.map((u) => <option key={u}>{u}</option>)}</select>)}
            </Campo>
            <Campo rotulo={edit.id ? "Nova senha (opcional)" : "Senha inicial"} erro={erros.senha} ajuda="Mín. 8 caracteres, letras e números." obrigatorio={!edit.id}>{(p) => <input {...p} type="password" autoComplete="new-password" value={edit.senha ?? ""} onChange={(e) => setEdit({ ...edit, senha: e.target.value })} />}</Campo>
            <label className="check" style={{ alignSelf: "center" }}><input type="checkbox" checked={edit.ativo ?? true} onChange={(e) => setEdit({ ...edit, ativo: e.target.checked })} />Usuário ativo</label>
            {edit.id && edit.totp_ativo && <button className="btn btn-pequeno" onClick={async () => { await api.patch(`/usuarios/${edit.id}`, { desativar_2fa: true }); toast("2FA desativado."); recarregar(); setEdit(null); }}>Desativar 2FA (perda do celular)</button>}
          </div>
        </Modal>
      )}
    </section>
  );
}

/* ---------------------------------------------------------------- cadastro simples genérico */
function Simples({ titulo, rota, campos, descricao }: { titulo: string; rota: string; campos: { k: string; r: string; tipo?: "texto" | "cor" | "bool" | "area" }[]; descricao?: string }) {
  const toast = useToast();
  const { recarregar: recarregarCad } = useCadastros();
  const { dados, recarregar } = useCarregar<any[]>(() => api.get(`/${rota}`), [rota]);
  const [edit, setEdit] = useState<any>(null);
  const [excluir, setExcluir] = useState<any>(null);
  const [erro, setErro] = useState("");
  const ativoK = campos.find((c) => c.tipo === "bool")?.k;
  const salvar = async () => {
    setErro("");
    try {
      const corpo = Object.fromEntries(campos.map((c) => [c.k, edit[c.k] ?? (c.tipo === "bool" ? true : c.tipo === "cor" ? "#64748b" : "")]));
      if (edit.id) await api.put(`/${rota}/${edit.id}`, corpo); else await api.post(`/${rota}`, corpo);
      toast("Salvo."); setEdit(null); recarregar(); recarregarCad();
    } catch (e) { setErro(e instanceof Error ? e.message : ""); }
  };
  return (
    <section className="cartao">
      <div className="cartao-cab"><div><h2>{titulo}</h2>{descricao && <p className="texto-3" style={{ margin: 0 }}>{descricao}</p>}</div>
        <button className="btn btn-primario btn-pequeno" onClick={() => setEdit({})}><Icone nome="mais" tam={16} />Adicionar</button></div>
      {!dados ? <Carregando /> : (
        <div className="tabela-wrap"><table>
          <thead><tr>{campos.filter((c) => c.tipo !== "area").map((c) => <th key={c.k}>{c.r}</th>)}<th /></tr></thead>
          <tbody>{dados.map((d) => (
            <tr key={d.id}>
              {campos.filter((c) => c.tipo !== "area").map((c) => <td key={c.k}>
                {c.tipo === "bool" ? <span className={`selo ${d[c.k] ? "selo-ok" : ""}`}>{d[c.k] ? "Sim" : "Não"}</span>
                  : c.tipo === "cor" ? <span className="etiqueta" style={{ ["--cor" as string]: d[c.k] }}>{d[c.k]}</span> : d[c.k]}</td>)}
              <td className="num"><span className="grupo-botoes" style={{ justifyContent: "flex-end" }}>
                <button className="btn btn-pequeno" onClick={() => setEdit(d)}>Editar</button>
                <button className="btn btn-pequeno btn-fantasma" aria-label={`Excluir ${d.nome}`} onClick={() => setExcluir(d)}><Icone nome="lixeira" tam={15} /></button>
              </span></td>
            </tr>))}</tbody>
        </table></div>
      )}
      {edit && (
        <Modal titulo={edit.id ? `Editar` : `Adicionar`} aoFechar={() => setEdit(null)} largo={campos.some((c) => c.tipo === "area")} rodape={<>
          <button className="btn" onClick={() => setEdit(null)}>Cancelar</button><button className="btn btn-primario" onClick={salvar}>Salvar</button></>}>
          <div className="pilha">
            {erro && <Aviso tipo="erro">{erro}</Aviso>}
            {campos.map((c) => c.tipo === "bool" ? (
              <label key={c.k} className="check"><input type="checkbox" checked={edit[c.k] ?? true} onChange={(e) => setEdit({ ...edit, [c.k]: e.target.checked })} />{c.r}</label>
            ) : (
              <Campo key={c.k} rotulo={c.r} ajuda={c.tipo === "area" ? "Variáveis: {{nome}}, {{primeiro_nome}}, {{empresa}}, {{interesse}}, {{vendedor}}" : undefined}>{(p) => c.tipo === "area"
                ? <textarea {...p} rows={8} value={edit[c.k] ?? ""} onChange={(e) => setEdit({ ...edit, [c.k]: e.target.value })} />
                : <input {...p} type={c.tipo === "cor" ? "color" : "text"} value={edit[c.k] ?? (c.tipo === "cor" ? "#64748b" : "")} onChange={(e) => setEdit({ ...edit, [c.k]: e.target.value })} />}</Campo>
            ))}
          </div>
        </Modal>
      )}
      {excluir && <Confirmar titulo="Excluir" perigo textoOk="Excluir" aoFechar={() => setExcluir(null)}
        mensagem={<p>Excluir <strong>{excluir.nome}</strong>?{ativoK && " Itens em uso não podem ser excluídos — desative-os."}</p>}
        aoConfirmar={async () => {
          try { await api.del(`/${rota}/${excluir.id}`); toast("Excluído."); recarregar(); recarregarCad(); }
          catch (e) { toast(e instanceof Error ? e.message : "", "erro"); }
          setExcluir(null);
        }} />}
    </section>
  );
}

/* ---------------------------------------------------------------- funil */
function Funil() {
  const toast = useToast();
  const { estagios, recarregar } = useCadastros();
  const [edit, setEdit] = useState<any>(null);
  const [erro, setErro] = useState("");
  const ordenados = [...estagios].sort((a, b) => a.ordem - b.ordem);
  const mover = async (i: number, d: number) => {
    const ids = ordenados.map((e) => e.id);
    [ids[i], ids[i + d]] = [ids[i + d], ids[i]];
    await api.post("/estagios/reordenar", ids); recarregar();
  };
  const salvar = async () => {
    setErro("");
    try {
      const corpo = { nome: edit.nome, ordem: edit.ordem ?? ordenados.length + 1, tipo: edit.tipo ?? "aberto", ativo: edit.ativo ?? true, cor: edit.cor ?? "#2563eb" };
      if (edit.id) await api.put(`/estagios/${edit.id}`, corpo); else await api.post("/estagios", corpo);
      toast("Estágio salvo."); setEdit(null); recarregar();
    } catch (e) { setErro(e instanceof Error ? e.message : ""); }
  };
  return (
    <section className="cartao">
      <div className="cartao-cab"><div><h2>Estágios do funil</h2><p className="texto-3" style={{ margin: 0 }}>A ordem define as colunas do quadro. Estágios em uso só podem ser desativados.</p></div>
        <button className="btn btn-primario btn-pequeno" onClick={() => setEdit({})}><Icone nome="mais" tam={16} />Novo estágio</button></div>
      <ol style={{ listStyle: "none", margin: 0, padding: 0 }}>
        {ordenados.map((e, i) => (
          <li key={e.id} className="flex-entre" style={{ padding: "10px 18px", borderBottom: "1px solid var(--border)" }}>
            <span className="flex"><span style={{ width: 14, height: 14, borderRadius: 4, background: e.cor ?? "#64748b" }} aria-hidden /><strong>{e.nome}</strong>
              <span className="selo">{{ aberto: "aberto", ganho: "ganho", perdido: "perdido" }[e.tipo]}</span>{!e.ativo && <span className="selo selo-aviso">inativo</span>}</span>
            <span className="grupo-botoes">
              <button className="btn btn-pequeno btn-fantasma" disabled={i === 0} onClick={() => mover(i, -1)} aria-label={`Subir ${e.nome}`}>↑</button>
              <button className="btn btn-pequeno btn-fantasma" disabled={i === ordenados.length - 1} onClick={() => mover(i, 1)} aria-label={`Descer ${e.nome}`}>↓</button>
              <button className="btn btn-pequeno" onClick={() => setEdit(e)}>Editar</button>
            </span>
          </li>))}
      </ol>
      {edit && (
        <Modal titulo={edit.id ? "Editar estágio" : "Novo estágio"} aoFechar={() => setEdit(null)} rodape={<>
          <button className="btn" onClick={() => setEdit(null)}>Cancelar</button><button className="btn btn-primario" onClick={salvar}>Salvar</button></>}>
          <div className="grade grade-2">
            {erro && <div className="span-2"><Aviso tipo="erro">{erro}</Aviso></div>}
            <Campo rotulo="Nome" obrigatorio>{(p) => <input {...p} value={edit.nome ?? ""} onChange={(e) => setEdit({ ...edit, nome: e.target.value })} />}</Campo>
            <Campo rotulo="Tipo" ajuda="Ganho exige valor; Perdido exige motivo.">{(p) => (
              <select {...p} value={edit.tipo ?? "aberto"} onChange={(e) => setEdit({ ...edit, tipo: e.target.value })}>
                <option value="aberto">Aberto</option><option value="ganho">Ganho</option><option value="perdido">Perdido</option></select>)}
            </Campo>
            <Campo rotulo="Cor">{(p) => <input {...p} type="color" value={edit.cor ?? "#2563eb"} onChange={(e) => setEdit({ ...edit, cor: e.target.value })} />}</Campo>
            <label className="check" style={{ alignSelf: "center" }}><input type="checkbox" checked={edit.ativo ?? true} onChange={(e) => setEdit({ ...edit, ativo: e.target.checked })} />Ativo</label>
          </div>
        </Modal>
      )}
    </section>
  );
}

/* ---------------------------------------------------------------- atribuição */
function Atribuicao() {
  const toast = useToast();
  const { origens, usuarios, parametros, recarregar } = useCadastros();
  const regras = useCarregar<any[]>(() => api.get("/regras-atribuicao"), []);
  const [nova, setNova] = useState<any>({ prioridade: 100 });
  const [erro, setErro] = useState("");
  const nome = (lista: { id: number; nome: string }[], id: number) => lista.find((x) => x.id === id)?.nome ?? "—";
  return (
    <div className="pilha">
      <section className="cartao cartao-corpo pilha">
        <h2>Distribuição automática</h2>
        <label className="check"><input type="checkbox" checked={parametros.atribuicao_automatica} onChange={async (e) => {
          await api.put("/parametros", { atribuicao_automatica: e.target.checked }); recarregar(); toast("Parâmetro salvo.");
        }} />Distribuir automaticamente leads cadastrados sem responsável (rodízio entre vendedores ativos)</label>
        <p className="texto-3" style={{ margin: 0 }}>Leads do webhook, importação e e-mail recebido sempre usam regras/rodízio. Leads criados por vendedores ficam com quem cadastrou.</p>
      </section>
      <section className="cartao">
        <div className="cartao-cab"><div><h2>Regras por origem ou região</h2><p className="texto-3" style={{ margin: 0 }}>Verificadas em ordem de prioridade (menor primeiro) antes do rodízio.</p></div></div>
        <div className="tabela-wrap"><table>
          <thead><tr><th>Prioridade</th><th>Origem</th><th>UF</th><th>Vai para</th><th>Ativa</th><th /></tr></thead>
          <tbody>
            {(regras.dados ?? []).map((r) => (
              <tr key={r.id}><td>{r.prioridade}</td><td>{r.origem_id ? nome(origens, r.origem_id) : "Qualquer"}</td><td>{r.uf ?? "Qualquer"}</td><td>{nome(usuarios, r.usuario_id)}</td>
                <td>{r.ativa ? "Sim" : "Não"}</td>
                <td><button className="btn btn-pequeno btn-fantasma" aria-label="Excluir regra" onClick={async () => { await api.del(`/regras-atribuicao/${r.id}`); regras.recarregar(); }}><Icone nome="lixeira" tam={15} /></button></td></tr>))}
            <tr>
              <td><input type="number" aria-label="Prioridade" value={nova.prioridade} onChange={(e) => setNova({ ...nova, prioridade: Number(e.target.value) })} style={{ width: 80 }} /></td>
              <td><select aria-label="Origem" value={nova.origem_id ?? ""} onChange={(e) => setNova({ ...nova, origem_id: e.target.value ? Number(e.target.value) : null })}><option value="">Qualquer</option>{origens.map((o) => <option key={o.id} value={o.id}>{o.nome}</option>)}</select></td>
              <td><select aria-label="UF" value={nova.uf ?? ""} onChange={(e) => setNova({ ...nova, uf: e.target.value || null })}><option value="">Qualquer</option>{UFS.map((u) => <option key={u}>{u}</option>)}</select></td>
              <td><select aria-label="Responsável" value={nova.usuario_id ?? ""} onChange={(e) => setNova({ ...nova, usuario_id: Number(e.target.value) })}><option value="">Selecione…</option>{usuarios.filter((u) => u.ativo && u.perfil !== "leitura").map((u) => <option key={u.id} value={u.id}>{u.nome}</option>)}</select></td>
              <td colSpan={2}><button className="btn btn-primario btn-pequeno" disabled={!nova.usuario_id} onClick={async () => {
                setErro("");
                try { await api.post("/regras-atribuicao", { ...nova, ativa: true }); setNova({ prioridade: 100 }); regras.recarregar(); toast("Regra criada."); }
                catch (e) { setErro(e instanceof Error ? e.message : ""); }
              }}>Adicionar regra</button></td>
            </tr>
          </tbody>
        </table></div>
        {erro && <div className="cartao-corpo"><Aviso tipo="erro">{erro}</Aviso></div>}
      </section>
    </div>
  );
}

/* ---------------------------------------------------------------- captura externa */
function Captura() {
  const toast = useToast();
  const { origens } = useCadastros();
  const chaves = useCarregar<any[]>(() => api.get("/chaves-api"), []);
  const [nome, setNome] = useState("");
  const [origem, setOrigem] = useState("");
  const [gerada, setGerada] = useState<string | null>(null);
  const url = `${location.origin}/api/public/leads`;
  const chaveExemplo = gerada ?? "SUA_CHAVE_AQUI";
  const html = `<form action="${url}" method="post">
  <input type="hidden" name="chave" value="${chaveExemplo}">
  <input type="hidden" name="utm_source" id="utm_source">
  <input type="hidden" name="utm_medium" id="utm_medium">
  <input type="hidden" name="utm_campaign" id="utm_campaign">
  <input type="hidden" name="redirecionar" value="https://seusite.com.br/obrigado">
  <input name="website" style="display:none" tabindex="-1" autocomplete="off">
  <label>Nome <input name="nome" required></label>
  <label>E-mail <input name="email" type="email"></label>
  <label>Telefone <input name="telefone"></label>
  <label>Empresa <input name="empresa"></label>
  <label><input type="checkbox" name="consentimento" value="1" required>
    Autorizo o contato comercial conforme a Política de Privacidade.</label>
  <button>Enviar</button>
</form>
<script>
  const p = new URLSearchParams(location.search);
  ["utm_source","utm_medium","utm_campaign"].forEach(k => {
    const el = document.getElementById(k); if (el) el.value = p.get(k) || "";
  });
</script>`;
  const curl = `curl -X POST ${url} \\
  -H "X-API-Key: ${chaveExemplo}" -H "Content-Type: application/json" \\
  -d '{"nome":"Maria","email":"maria@exemplo.com","utm_source":"google","utm_campaign":"promo"}'`;
  return (
    <div className="pilha">
      <section className="cartao">
        <div className="cartao-cab"><div><h2>Chaves de API</h2><p className="texto-3" style={{ margin: 0 }}>Cada site/formulário usa sua chave; a origem do lead vem da chave. Limite de requisições por minuto por chave.</p></div></div>
        <div className="cartao-corpo grade grade-3" style={{ alignItems: "end" }}>
          <Campo rotulo="Nome da chave">{(p) => <input {...p} value={nome} onChange={(e) => setNome(e.target.value)} placeholder="Ex.: Site institucional" />}</Campo>
          <Campo rotulo="Origem dos leads">{(p) => <select {...p} value={origem} onChange={(e) => setOrigem(e.target.value)}><option value="">Selecione…</option>{origens.filter((o) => o.ativa).map((o) => <option key={o.id} value={o.id}>{o.nome}</option>)}</select>}</Campo>
          <div><button className="btn btn-primario" disabled={!nome || !origem} onClick={async () => {
            const r = await api.post("/chaves-api", { nome, origem_id: Number(origem) }); setGerada(r.chave); setNome(""); chaves.recarregar();
          }}>Gerar chave</button></div>
        </div>
        {gerada && <div className="cartao-corpo"><Aviso tipo="ok" titulo="Chave gerada — copie agora, ela não será exibida de novo."><div className="codigo mt">{gerada}</div>
          <button className="btn btn-pequeno mt" onClick={() => { navigator.clipboard?.writeText(gerada); toast("Chave copiada."); }}>Copiar</button></Aviso></div>}
        <div className="tabela-wrap"><table>
          <thead><tr><th>Nome</th><th>Prefixo</th><th>Origem</th><th>Último uso</th><th>Situação</th><th /></tr></thead>
          <tbody>{(chaves.dados ?? []).map((c) => (
            <tr key={c.id}><td>{c.nome}</td><td><code>{c.prefixo}…</code></td><td>{c.origem.nome}</td><td>{dataHora(c.ultimo_uso_em)}</td>
              <td><span className={`selo ${c.ativa ? "selo-ok" : "selo-alerta"}`}>{c.ativa ? "Ativa" : "Revogada"}</span></td>
              <td>{c.ativa && <button className="btn btn-pequeno" onClick={async () => { await api.post(`/chaves-api/${c.id}/revogar`); chaves.recarregar(); toast("Chave revogada."); }}>Revogar</button>}</td></tr>))}</tbody>
        </table></div>
      </section>
      <section className="cartao cartao-corpo pilha">
        <h2>Formulário para incorporar no site</h2>
        <p className="texto-2" style={{ margin: 0 }}>Cole no HTML da página. UTMs da URL são enviadas automaticamente; o campo oculto “website” bloqueia robôs.</p>
        <div className="codigo">{html}</div>
        <div><button className="btn btn-pequeno" onClick={() => { navigator.clipboard?.writeText(html); toast("Código copiado."); }}>Copiar HTML</button></div>
        <h3>Integração via webhook (JSON)</h3>
        <div className="codigo">{curl}</div>
        <p className="texto-3" style={{ margin: 0 }}>Documentação completa da API: <a href="/api/docs" target="_blank" rel="noreferrer">/api/docs</a>.</p>
      </section>
    </div>
  );
}

/* ---------------------------------------------------------------- parâmetros */
function Parametros() {
  const toast = useToast();
  const { parametros, recarregar } = useCadastros();
  const [dias, setDias] = useState(String(parametros.dias_lead_parado));
  const [notif, setNotif] = useState(parametros.notificar_por_email);
  return (
    <section className="cartao cartao-corpo pilha" style={{ maxWidth: 620 }}>
      <h2>Parâmetros</h2>
      <Campo rotulo="Dias sem interação para considerar o lead parado" ajuda="Padrão: 7 dias.">{(p) => <input {...p} type="number" min={1} max={365} value={dias} onChange={(e) => setDias(e.target.value)} style={{ maxWidth: 140 }} />}</Campo>
      <label className="check"><input type="checkbox" checked={notif} onChange={(e) => setNotif(e.target.checked)} />Enviar notificações também por e-mail (comercial@tenti.com.br)</label>
      <div><button className="btn btn-primario" onClick={async () => {
        try { await api.put("/parametros", { dias_lead_parado: Number(dias), notificar_por_email: notif }); recarregar(); toast("Parâmetros salvos."); }
        catch (e) { toast(e instanceof Error ? e.message : "", "erro"); }
      }}>Salvar</button></div>
    </section>
  );
}

/* ---------------------------------------------------------------- auditoria */
const ACOES: Record<string, string> = { criar: "Criou", editar: "Editou", excluir: "Excluiu", exportar: "Exportou", login: "Entrou", logout: "Saiu", login_falhou: "Login falhou", mudar_estagio: "Mudou estágio", reabrir: "Reabriu", atribuir: "Atribuiu", mesclar: "Mesclou", lgpd_exportar: "LGPD: exportou", lgpd_anonimizar: "LGPD: anonimizou" };

function Auditoria() {
  const { usuarios } = useCadastros();
  const [f, setF] = useState<Record<string, string>>({});
  const [pagina, setPagina] = useState(1);
  const [ver, setVer] = useState<any>(null);
  const { dados, carregando } = useCarregar(() => api.get("/auditoria", { ...f, pagina, tamanho: 30 }), [JSON.stringify(f), pagina]);
  const set = (k: string, v: string) => { setF({ ...f, [k]: v }); setPagina(1); };
  return (
    <section className="cartao">
      <div className="cartao-cab"><div><h2>Log de auditoria</h2><p className="texto-3" style={{ margin: 0 }}>Imutável: registra quem criou, alterou, exportou ou excluiu o quê e quando.</p></div></div>
      <div className="cartao-corpo barra-filtros" style={{ marginBottom: 0 }}>
        <div className="campo"><label className="rotulo" htmlFor="a-ent">Entidade</label><select id="a-ent" value={f.entidade ?? ""} onChange={(e) => set("entidade", e.target.value)}>
          <option value="">Todas</option>{["lead", "usuario", "sessao", "interacao", "tarefa", "exportacao", "importacao", "estagio", "origem", "chave_api", "parametros"].map((x) => <option key={x}>{x}</option>)}</select></div>
        <div className="campo"><label className="rotulo" htmlFor="a-acao">Ação</label><select id="a-acao" value={f.acao ?? ""} onChange={(e) => set("acao", e.target.value)}>
          <option value="">Todas</option>{Object.entries(ACOES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
        <div className="campo"><label className="rotulo" htmlFor="a-u">Usuário</label><select id="a-u" value={f.usuario_id ?? ""} onChange={(e) => set("usuario_id", e.target.value)}>
          <option value="">Todos</option>{usuarios.map((u) => <option key={u.id} value={u.id}>{u.nome}</option>)}</select></div>
        <div className="campo"><label className="rotulo" htmlFor="a-id">ID do registro</label><input id="a-id" value={f.entidade_id ?? ""} onChange={(e) => set("entidade_id", e.target.value)} style={{ width: 110 }} /></div>
        <div className="campo"><label className="rotulo" htmlFor="a-de">De</label><input id="a-de" type="date" value={f.de ?? ""} onChange={(e) => set("de", e.target.value)} /></div>
        <div className="campo"><label className="rotulo" htmlFor="a-ate">Até</label><input id="a-ate" type="date" value={f.ate ?? ""} onChange={(e) => set("ate", e.target.value)} /></div>
      </div>
      {carregando && !dados ? <Carregando /> : (
        <div className="tabela-wrap"><table className="responsiva">
          <thead><tr><th>Quando</th><th>Quem</th><th>Ação</th><th>Registro</th><th>IP</th><th /></tr></thead>
          <tbody>{dados.itens.map((a: any) => (
            <tr key={a.id}><td data-rotulo="Quando">{dataHora(a.data_hora)}</td><td data-rotulo="Quem">{a.usuario}</td><td data-rotulo="Ação">{ACOES[a.acao] ?? a.acao}</td>
              <td data-rotulo="Registro">{a.entidade}{a.entidade_id ? ` #${a.entidade_id}` : ""}{a.entidade === "lead" && a.entidade_id && <> · <Link to={`/leads/${a.entidade_id}`}>abrir</Link></>}</td>
              <td data-rotulo="IP" className="texto-3">{a.ip ?? "—"}</td>
              <td>{(a.antes || a.depois) && <button className="btn btn-pequeno" onClick={() => setVer(a)}>Detalhes</button>}</td></tr>))}</tbody>
        </table></div>
      )}
      {dados && <Paginacao pagina={pagina} tamanho={30} total={dados.total} aoMudar={setPagina} />}
      {ver && <Modal titulo={`${ACOES[ver.acao] ?? ver.acao} — ${ver.entidade} #${ver.entidade_id ?? ""}`} largo aoFechar={() => setVer(null)}>
        <div className="grade grade-2">
          <div><span className="rotulo">Antes</span><div className="codigo">{JSON.stringify(ver.antes, null, 2) ?? "—"}</div></div>
          <div><span className="rotulo">Depois</span><div className="codigo">{JSON.stringify(ver.depois, null, 2) ?? "—"}</div></div>
        </div>
      </Modal>}
    </section>
  );
}

/* ---------------------------------------------------------------- LGPD */
function Lgpd() {
  const [email, setEmail] = useState("");
  const [tel, setTel] = useState("");
  const [res, setRes] = useState<any[] | null>(null);
  const [erro, setErro] = useState("");
  return (
    <section className="cartao cartao-corpo pilha">
      <h2>Pedidos de titulares (LGPD)</h2>
      <p className="texto-2" style={{ margin: 0 }}>O administrador é o encarregado pelos pedidos. Localize todos os registros de um titular para exportar (acesso/portabilidade) ou anonimizar (eliminação) na página do lead.</p>
      <form className="barra-filtros" onSubmit={async (e) => {
        e.preventDefault(); setErro("");
        try { setRes(await api.get("/lgpd/titular", { email: email || undefined, telefone: tel || undefined })); } catch (er) { setErro(er instanceof Error ? er.message : ""); }
      }}>
        <div className="campo"><label className="rotulo" htmlFor="l-e">E-mail</label><input id="l-e" type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></div>
        <div className="campo"><label className="rotulo" htmlFor="l-t">Telefone</label><input id="l-t" value={tel} onChange={(e) => setTel(e.target.value)} /></div>
        <button className="btn btn-primario" disabled={!email && !tel}>Localizar</button>
      </form>
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      {res && (res.length === 0 ? <p className="texto-2">Nenhum registro encontrado.</p> : (
        <table><thead><tr><th>Lead</th><th>E-mail</th><th>Telefone</th><th>Criado em</th><th /></tr></thead>
          <tbody>{res.map((r) => <tr key={r.id}><td>{r.nome}{r.excluido && <span className="selo selo-aviso" style={{ marginLeft: 6 }}>excluído</span>}</td><td>{r.email ?? "—"}</td><td>{telefone(r.telefone)}</td><td>{dataHora(r.criado_em)}</td>
            <td>{!r.excluido && <Link to={`/leads/${r.id}`} className="btn btn-pequeno">Abrir</Link>}</td></tr>)}</tbody></table>
      ))}
    </section>
  );
}

export default function Admin() {
  const [aba, setAba] = useState<Aba>("usuarios");
  return (
    <>
      <div className="cabecalho-pagina"><div><h1>Administração</h1><p>Usuários, funil, cadastros auxiliares, integrações e conformidade.</p></div></div>
      <Abas atual={aba} aoMudar={setAba} abas={[
        { id: "usuarios", rotulo: "Usuários" }, { id: "funil", rotulo: "Funil" }, { id: "origens", rotulo: "Origens" },
        { id: "motivos", rotulo: "Motivos de perda" }, { id: "etiquetas", rotulo: "Etiquetas" }, { id: "atribuicao", rotulo: "Atribuição" },
        { id: "captura", rotulo: "Captura (site/webhook)" }, { id: "modelos", rotulo: "Modelos de e-mail" }, { id: "parametros", rotulo: "Parâmetros" },
        { id: "auditoria", rotulo: "Auditoria" }, { id: "lgpd", rotulo: "LGPD" },
      ]} />
      {aba === "usuarios" && <Usuarios />}
      {aba === "funil" && <Funil />}
      {aba === "origens" && <Simples titulo="Origens" rota="origens" descricao="Origem é obrigatória em todo lead. Em uso: apenas desative." campos={[{ k: "nome", r: "Nome" }, { k: "ativa", r: "Ativa", tipo: "bool" }]} />}
      {aba === "motivos" && <Simples titulo="Motivos de perda" rota="motivos-perda" descricao="Exigido ao marcar um lead como perdido." campos={[{ k: "nome", r: "Nome" }, { k: "ativo", r: "Ativo", tipo: "bool" }]} />}
      {aba === "etiquetas" && <Simples titulo="Etiquetas" rota="etiquetas" campos={[{ k: "nome", r: "Nome" }, { k: "cor", r: "Cor", tipo: "cor" }]} />}
      {aba === "modelos" && <Simples titulo="Modelos de e-mail" rota="modelos-email" descricao="Usados no botão “Enviar e-mail” do lead." campos={[{ k: "nome", r: "Nome" }, { k: "assunto", r: "Assunto" }, { k: "corpo", r: "Mensagem", tipo: "area" }, { k: "ativo", r: "Ativo", tipo: "bool" }]} />}
      {aba === "atribuicao" && <Atribuicao />}
      {aba === "captura" && <Captura />}
      {aba === "parametros" && <Parametros />}
      {aba === "auditoria" && <Auditoria />}
      {aba === "lgpd" && <Lgpd />}
    </>
  );
}
