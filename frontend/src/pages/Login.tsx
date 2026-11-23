import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, ErroApi } from "../api";
import { useAuth } from "../contexto";
import { Aviso, Campo } from "../ui";

function Lateral() {
  return (
    <div className="login-lado">
      <div className="marca" style={{ padding: 0 }}>Leads Tenti</div>
      <div>
        <h1>Todo lead em um só lugar, com dono e próximo passo.</h1>
        <ul>
          <li>Funil visual com arrastar e soltar</li>
          <li>Histórico completo de cada contato</li>
          <li>Lembretes para nenhum lead ficar parado</li>
        </ul>
      </div>
      <small style={{ color: "#c7d2fe" }}>Dados protegidos conforme a LGPD.</small>
    </div>
  );
}

export function Login({ destino }: { destino: string }) {
  const { entrar } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [codigo, setCodigo] = useState("");
  const [pedir2fa, setPedir2fa] = useState(false);
  const [lembrar, setLembrar] = useState(false);
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    setErro("");
    setOcupado(true);
    try {
      await entrar(email, senha, codigo, lembrar);
      nav(destino.startsWith("/redefinir") || destino.startsWith("/recuperar") ? "/" : destino, { replace: true });
    } catch (err) {
      if (err instanceof ErroApi && err.codigo === "2fa_requerido") setPedir2fa(true);
      else setErro(err instanceof Error ? err.message : "Falha ao entrar.");
    } finally {
      setOcupado(false);
    }
  };

  return (
    <div className="tela-login">
      <Lateral />
      <main className="login-form">
        <form onSubmit={enviar} noValidate>
          <div>
            <h1>Entrar</h1>
            <p className="texto-2">Acesse com seu e-mail corporativo.</p>
          </div>
          {erro && <Aviso tipo="erro">{erro}</Aviso>}
          {!pedir2fa ? (<>
            <Campo rotulo="E-mail" obrigatorio>{(p) => <input {...p} type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />}</Campo>
            <Campo rotulo="Senha" obrigatorio>{(p) => <input {...p} type="password" autoComplete="current-password" value={senha} onChange={(e) => setSenha(e.target.value)} required />}</Campo>
            <div className="flex-entre">
              <label className="check"><input type="checkbox" checked={lembrar} onChange={(e) => setLembrar(e.target.checked)} />Manter conectado neste dispositivo</label>
              <Link to="/recuperar-senha" className="pequeno">Esqueci a senha</Link>
            </div>
          </>) : (
            <Campo rotulo="Código de verificação" ajuda="Abra o aplicativo autenticador e digite o código de 6 dígitos." obrigatorio>
              {(p) => <input {...p} inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={codigo} onChange={(e) => setCodigo(e.target.value.replace(/\D/g, ""))} autoFocus />}
            </Campo>
          )}
          <button className="btn btn-primario" disabled={ocupado || !email || !senha}>{ocupado ? "Entrando…" : pedir2fa ? "Verificar" : "Entrar"}</button>
        </form>
      </main>
    </div>
  );
}

export function RecuperarSenha() {
  const [email, setEmail] = useState("");
  const [msg, setMsg] = useState("");
  const [ocupado, setOcupado] = useState(false);
  return (
    <div className="tela-login">
      <Lateral />
      <main className="login-form">
        <form onSubmit={async (e) => {
          e.preventDefault(); setOcupado(true);
          try { const r = await api.post("/auth/recuperar-senha", { email }); setMsg(r.mensagem); } finally { setOcupado(false); }
        }}>
          <h1>Recuperar senha</h1>
          <p className="texto-2">Enviaremos um link para criar uma nova senha.</p>
          {msg ? <Aviso tipo="ok">{msg}</Aviso> : (
            <Campo rotulo="E-mail" obrigatorio>{(p) => <input {...p} type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />}</Campo>
          )}
          {!msg && <button className="btn btn-primario" disabled={ocupado || !email}>Enviar link</button>}
          <Link to="/">Voltar ao login</Link>
        </form>
      </main>
    </div>
  );
}

export function RedefinirSenha() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const [senha, setSenha] = useState("");
  const [conf, setConf] = useState("");
  const [erro, setErro] = useState("");
  const [ok, setOk] = useState(false);
  return (
    <div className="tela-login">
      <Lateral />
      <main className="login-form">
        <form onSubmit={async (e) => {
          e.preventDefault(); setErro("");
          if (senha !== conf) { setErro("As senhas não conferem."); return; }
          try { await api.post("/auth/redefinir-senha", { token: params.get("token"), nova_senha: senha }); setOk(true); }
          catch (err) { setErro(err instanceof Error ? err.message : "Erro"); }
        }}>
          <h1>Nova senha</h1>
          {ok ? (<><Aviso tipo="ok">Senha alterada. Entre com a nova senha.</Aviso><button type="button" className="btn btn-primario" onClick={() => nav("/")}>Ir para o login</button></>) : (<>
            {erro && <Aviso tipo="erro">{erro}</Aviso>}
            <Campo rotulo="Nova senha" ajuda="Mínimo de 8 caracteres, com letras e números." obrigatorio>{(p) => <input {...p} type="password" autoComplete="new-password" value={senha} onChange={(e) => setSenha(e.target.value)} />}</Campo>
            <Campo rotulo="Confirme a senha" obrigatorio>{(p) => <input {...p} type="password" autoComplete="new-password" value={conf} onChange={(e) => setConf(e.target.value)} />}</Campo>
            <button className="btn btn-primario" disabled={!senha || !conf}>Salvar nova senha</button>
          </>)}
        </form>
      </main>
    </div>
  );
}
