from __future__ import annotations

import os
from typing import Iterable

import requests


RESEND_API_URL = "https://api.resend.com/emails"


def send_email(
    *,
    # Mantive assinatura "compatível" com seu código atual.
    # Os parâmetros SMTP ficam opcionais e ignorados no modo Resend.
    smtp_host: str | None = None,
    smtp_port: int | None = None,
    smtp_usuario: str | None = None,
    smtp_senha: str | None = None,
    use_tls: bool | None = None,
    use_ssl: bool | None = None,
    sender_email: str,
    sender_name: str | None,
    to_emails: Iterable[str],
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> None:
    """
    Envia e-mail via Resend (HTTP API).
    Configure a API key via variável de ambiente RESEND_API_KEY.

    Importante:
    - sender_email precisa ser um remetente permitido no Resend (domain/sender verificado).
    """

    api_key = (os.getenv("RESEND_API_KEY") or "").strip()
    if not api_key:
        raise ValueError("RESEND_API_KEY não configurada nas variáveis de ambiente.")

    sender_email = (sender_email or "").strip()
    sender_name = (sender_name or "").strip() if sender_name else None
    subject = (subject or "").strip()

    to_list = [(e or "").strip() for e in to_emails]
    to_list = [e for e in to_list if e]

    if not sender_email:
        raise ValueError("Sender e-mail vazio.")
    if not to_list:
        raise ValueError("Lista de destinatários vazia.")
    if not subject:
        raise ValueError("Assunto vazio.")
    if not html_body:
        raise ValueError("Corpo HTML vazio.")

    payload: dict = {
        "from": f"{sender_name} <{sender_email}>" if sender_name else sender_email,
        "to": to_list,
        "subject": subject,
        "html": html_body,
    }

    # Se você quiser, dá pra mandar versão texto também
    if text_body:
        payload["text"] = text_body

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    resp = requests.post(RESEND_API_URL, json=payload, headers=headers, timeout=30)
    if resp.status_code >= 400:
        # Resend retorna json com detalhes; não exponha a API key
        raise Exception(f"Erro Resend ({resp.status_code}): {resp.text}")
