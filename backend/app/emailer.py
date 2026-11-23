"""Envio (SMTP) e leitura (IMAP) da caixa comercial@tenti.com.br.

Credenciais vêm só de variáveis de ambiente. Sem SMTP_HOST configurado, o e-mail
é apenas registrado no log (modo desenvolvimento) e a chamada não falha.
"""
import email
import email.utils
import imaplib
import logging
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime
from email.header import decode_header, make_header
from email.message import EmailMessage

from .config import get_settings

log = logging.getLogger("emailer")
ENVIADOS_TESTE: list[EmailMessage] = []  # usado nos testes automatizados


def enviar(para: str, assunto: str, corpo: str, responder_para: str | None = None) -> str:
    s = get_settings()
    msg = EmailMessage()
    msg["From"] = email.utils.formataddr((s.email_remetente_nome, s.email_remetente))
    msg["To"] = para
    msg["Subject"] = assunto
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = email.utils.make_msgid(domain=s.email_remetente.split("@")[-1])
    if responder_para:
        msg["Reply-To"] = responder_para
    msg.set_content(corpo)
    if s.modo_teste:
        ENVIADOS_TESTE.append(msg)
        return msg["Message-ID"]
    if not s.smtp_host:
        log.warning("SMTP não configurado; e-mail NÃO enviado. Para=%s Assunto=%s", para, assunto)
        return msg["Message-ID"]
    ctx = ssl.create_default_context()
    if s.smtp_tls == "ssl":
        with smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, context=ctx, timeout=30) as smtp:
            _login_enviar(smtp, s, msg)
    else:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=30) as smtp:
            if s.smtp_tls == "starttls":
                smtp.starttls(context=ctx)
            _login_enviar(smtp, s, msg)
    return msg["Message-ID"]


def _login_enviar(smtp, s, msg):
    if s.smtp_usuario:
        smtp.login(s.smtp_usuario, s.smtp_senha)
    smtp.send_message(msg)


@dataclass
class MensagemRecebida:
    remetente: str
    nome: str
    assunto: str
    corpo: str
    data: datetime | None
    message_id: str | None


def _decodificar(v: str | None) -> str:
    if not v:
        return ""
    try:
        return str(make_header(decode_header(v)))
    except Exception:
        return v


def _texto(msg) -> str:
    if msg.is_multipart():
        for parte in msg.walk():
            if parte.get_content_type() == "text/plain" and not parte.get_filename():
                return parte.get_payload(decode=True).decode(parte.get_content_charset() or "utf-8", "replace")
        return ""
    payload = msg.get_payload(decode=True) or b""
    return payload.decode(msg.get_content_charset() or "utf-8", "replace")


def interpretar(bruto: bytes) -> MensagemRecebida:
    msg = email.message_from_bytes(bruto)
    nome, endereco = email.utils.parseaddr(_decodificar(msg.get("From")))
    data = None
    if msg.get("Date"):
        try:
            data = email.utils.parsedate_to_datetime(msg["Date"])
        except (TypeError, ValueError):
            data = None
    return MensagemRecebida(remetente=endereco.lower(), nome=nome, assunto=_decodificar(msg.get("Subject")),
                            corpo=_texto(msg)[:5000], data=data, message_id=msg.get("Message-ID"))


def ler_nao_lidas() -> list[MensagemRecebida]:
    """Lê mensagens não lidas da caixa e as marca como lidas."""
    s = get_settings()
    if not s.imap_host:
        return []
    resultado = []
    with imaplib.IMAP4_SSL(s.imap_host, s.imap_port) as imap:
        imap.login(s.imap_usuario, s.imap_senha)
        imap.select(s.imap_pasta)
        _, dados = imap.search(None, "UNSEEN")
        for num in dados[0].split():
            _, partes = imap.fetch(num, "(RFC822)")
            resultado.append(interpretar(partes[0][1]))
            imap.store(num, "+FLAGS", "\\Seen")
    return resultado
