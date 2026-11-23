import re
import unicodedata

import phonenumbers
from email_validator import EmailNotValidError, validate_email

UFS = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
       "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"}


def normalizar_email(email: str | None) -> str | None:
    if email is None:
        return None
    email = email.strip().lower()
    if not email:
        return None
    try:
        validate_email(email, check_deliverability=False)
    except EmailNotValidError as e:
        raise ValueError("E-mail inválido.") from e
    return email


def normalizar_telefone(tel: str | None) -> str | None:
    """Converte para E.164, assumindo Brasil quando não houver DDI."""
    if tel is None:
        return None
    tel = tel.strip()
    if not re.search(r"\d", tel):
        if tel:
            raise ValueError("Telefone inválido.")
        return None
    try:
        num = phonenumbers.parse(tel, "BR")
    except phonenumbers.NumberParseException as e:
        raise ValueError("Telefone inválido.") from e
    if not phonenumbers.is_possible_number(num):
        raise ValueError("Telefone inválido. Informe DDD + número.")
    return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)


def normalizar_uf(uf: str | None) -> str | None:
    if not uf:
        return None
    uf = uf.strip().upper()
    if uf not in UFS:
        raise ValueError("UF inválida.")
    return uf


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()


def limpar(s: str | None) -> str | None:
    if s is None:
        return None
    s = s.strip()
    return s or None
