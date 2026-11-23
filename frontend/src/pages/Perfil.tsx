import QRCode from "qrcode";
import { useState } from "react";
import { api } from "../api";
import { useAuth } from "../contexto";
import { dataHora, PERFIS } from "../formato";
import { Aviso, Campo, errosDeCampo, useToast } from "../ui";

export default function Perfil() {
  const { usuario, atualizar } = useAuth();
  const toast = useToast();
  const [atual, setAtual] = useState("");
  const [nova, setNova] = useState("");
  const [conf, setConf] = useState("");
  const [erros, setErros] = useState<Record<string, string>>({});
  const [qr, setQr] = useState<{ img: string; segredo: string } | null>(null);
  const [codigo, setCodigo] = useState("");
  const [erro2fa, setErro2fa] = useState("");

  return (
    <>
      <div className="cabecalho-pagina"><div><h1>Meu perfil</h1><p>{usuario?.email} · {PERFIS[usuario?.perfil ?? ""]} · último acesso {dataHora(usuario?.ultimo_login_em)}</p></div></div>
      <div className="grade grade-2">
        <form className="cartao cartao-corpo pilha" onSubmit={async (e) => {
          e.preventDefault(); setErros({});
          if (nova !== conf) return setErros({ conf: "As senhas não conferem." });
          try { await api.post("/auth/trocar-senha", { senha_atual: atual, nova_senha: nova }); toast("Senha alterada."); setAtual(""); setNova(""); setConf(""); }
          catch (err) { setErros({ ...errosDeCampo(err), geral: err instanceof Error ? err.message : "" }); }
        }}>
          <h2>Trocar senha</h2>
          {erros.geral && <Aviso tipo="erro">{erros.geral}</Aviso>}
          <Campo rotulo="Senha atual" erro={erros.senha_atual}>{(p) => <input {...p} type="password" autoComplete="current-password" value={atual} onChange={(e) => setAtual(e.target.value)} />}</Campo>
          <Campo rotulo="Nova senha" ajuda="Mínimo de 8 caracteres, com letras e números.">{(p) => <input {...p} type="password" autoComplete="new-password" value={nova} onChange={(e) => setNova(e.target.value)} />}</Campo>
          <Campo rotulo="Confirmar nova senha" erro={erros.conf}>{(p) => <input {...p} type="password" autoComplete="new-password" value={conf} onChange={(e) => setConf(e.target.value)} />}</Campo>
          <div><button className="btn btn-primario" disabled={!atual || !nova}>Salvar</button></div>
        </form>
        <section className="cartao cartao-corpo pilha">
          <h2>Verificação em duas etapas</h2>
          {usuario?.totp_ativo ? (<>
            <Aviso tipo="ok">Ativada. Ao entrar, será pedido o código do aplicativo autenticador.</Aviso>
            {erro2fa && <Aviso tipo="erro">{erro2fa}</Aviso>}
            <Campo rotulo="Código atual para desativar">{(p) => <input {...p} inputMode="numeric" maxLength={6} value={codigo} onChange={(e) => setCodigo(e.target.value.replace(/\D/g, ""))} />}</Campo>
            <div><button className="btn" disabled={codigo.length !== 6} onClick={async () => {
              try { await api.post("/auth/2fa/desativar", { codigo }); setCodigo(""); toast("Verificação em duas etapas desativada."); atualizar(); }
              catch (e) { setErro2fa(e instanceof Error ? e.message : ""); }
            }}>Desativar</button></div>
          </>) : !qr ? (<>
            <p className="texto-2" style={{ margin: 0 }}>Proteja sua conta com um código do Google Authenticator, Microsoft Authenticator ou similar.</p>
            <div><button className="btn btn-primario" onClick={async () => {
              const r = await api.post("/auth/2fa/configurar");
              setQr({ img: await QRCode.toDataURL(r.uri, { width: 200, margin: 1 }), segredo: r.segredo });
            }}>Configurar</button></div>
          </>) : (<>
            <ol style={{ margin: 0, paddingLeft: 18 }}><li>Escaneie o QR code no aplicativo autenticador.</li><li>Digite o código de 6 dígitos gerado.</li></ol>
            <img src={qr.img} alt="QR code para configurar o aplicativo autenticador" width={200} height={200} style={{ background: "#fff", borderRadius: 8 }} />
            <p className="texto-3" style={{ margin: 0 }}>Sem câmera? Use a chave: <code>{qr.segredo}</code></p>
            {erro2fa && <Aviso tipo="erro">{erro2fa}</Aviso>}
            <Campo rotulo="Código de verificação">{(p) => <input {...p} inputMode="numeric" maxLength={6} value={codigo} onChange={(e) => setCodigo(e.target.value.replace(/\D/g, ""))} />}</Campo>
            <div><button className="btn btn-primario" disabled={codigo.length !== 6} onClick={async () => {
              try { await api.post("/auth/2fa/ativar", { codigo }); toast("Verificação em duas etapas ativada."); setQr(null); setCodigo(""); atualizar(); }
              catch (e) { setErro2fa(e instanceof Error ? e.message : ""); }
            }}>Ativar</button></div>
          </>)}
        </section>
      </div>
    </>
  );
}
