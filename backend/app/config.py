"""Configuração da aplicação, lida exclusivamente de variáveis de ambiente."""
import os
from functools import lru_cache


def _bool(v: str | None, default: bool = False) -> bool:
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "sim", "yes", "on"}


class Settings:
    def __init__(self) -> None:
        e = os.environ.get
        self.database_url: str = e("DATABASE_URL", "sqlite:///./leads.db")
        self.secret_key: str = e("SECRET_KEY", "dev-inseguro-troque-em-producao")
        self.app_url: str = e("APP_URL", "https://localhost").rstrip("/")
        self.timezone: str = e("APP_TIMEZONE", "America/Sao_Paulo")
        self.sessao_horas: int = int(e("SESSAO_HORAS", "12"))
        self.upload_dir: str = e("UPLOAD_DIR", "./dados/anexos")
        self.max_upload_mb: int = int(e("MAX_UPLOAD_MB", "10"))
        self.cors_origens: list[str] = [o for o in e("CORS_ORIGENS", "").split(",") if o]
        self.login_max_tentativas: int = int(e("LOGIN_MAX_TENTATIVAS", "5"))
        self.login_janela_min: int = int(e("LOGIN_JANELA_MIN", "15"))
        self.public_rate_limit_min: int = int(e("PUBLIC_RATE_LIMIT_MIN", "30"))
        self.frontend_dir: str = e("FRONTEND_DIR", "")
        # E-mail corporativo (comercial@tenti.com.br). Credenciais SOMENTE por ambiente.
        self.smtp_host: str = e("SMTP_HOST", "")
        self.smtp_port: int = int(e("SMTP_PORT", "587"))
        self.smtp_usuario: str = e("SMTP_USUARIO", "")
        self.smtp_senha: str = e("SMTP_SENHA", "")
        self.smtp_tls: str = e("SMTP_TLS", "starttls")  # starttls | ssl | nenhum
        self.email_remetente: str = e("EMAIL_REMETENTE", "comercial@tenti.com.br")
        self.email_remetente_nome: str = e("EMAIL_REMETENTE_NOME", "Comercial Tenti")
        self.imap_host: str = e("IMAP_HOST", "")
        self.imap_port: int = int(e("IMAP_PORT", "993"))
        self.imap_usuario: str = e("IMAP_USUARIO", "")
        self.imap_senha: str = e("IMAP_SENHA", "")
        self.imap_pasta: str = e("IMAP_PASTA", "INBOX")
        self.imap_intervalo_seg: int = int(e("IMAP_INTERVALO_SEG", "120"))
        self.seed_admin_email: str = e("SEED_ADMIN_EMAIL", "admin@tenti.com.br")
        self.seed_admin_senha: str = e("SEED_ADMIN_SENHA", "Admin@12345")
        self.modo_teste: bool = _bool(e("MODO_TESTE"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
