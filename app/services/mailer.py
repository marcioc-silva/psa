from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Iterable


def send_email(
    *,
    smtp_host: str,
    smtp_port: int,
    smtp_usuario: str | None,
    smtp_senha: str | None,
    use_tls: bool,
    use_ssl: bool,
    sender_email: str,
    sender_name: str | None,
    to_emails: Iterable[str],
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> None:
    # --- Normalização (poka-yoke contra espaços/quebra de linha) ---
    smtp_host = (smtp_host or "").strip()
    smtp_usuario = (smtp_usuario or "").strip() if smtp_usuario else None
    smtp_senha = (smtp_senha or "").strip() if smtp_senha else None
    sender_email = (sender_email or "").strip()
    sender_name = (sender_name or "").strip() if sender_name else None
    subject = (subject or "").strip()

    to_list = [(e or "").strip() for e in to_emails]
    to_list = [e for e in to_list if e]

    if not smtp_host:
        raise ValueError("SMTP host vazio.")
    if not smtp_port:
        raise ValueError("SMTP port inválida.")
    if not sender_email:
        raise ValueError("Sender e-mail vazio.")
    if not to_list:
        raise ValueError("Lista de destinatários vazia.")

    # --- Poka-yoke de protocolo/porta ---
    # 465 => SSL
    # 587 => STARTTLS (TLS)
    if smtp_port == 465:
        use_ssl = True
        use_tls = False
    elif smtp_port == 587:
        use_ssl = False
        use_tls = True

    # Não permitir config incoerente
    if use_ssl and use_tls:
        raise ValueError("Configuração inválida: SSL e TLS não podem estar ativos ao mesmo tempo.")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{sender_name} <{sender_email}>" if sender_name else sender_email
    msg["To"] = ", ".join(to_list)

    if text_body:
        msg.set_content(text_body)
        msg.add_alternative(html_body, subtype="html")
    else:
        msg.set_content("Este e-mail contém um relatório em HTML.")
        msg.add_alternative(html_body, subtype="html")

    # --- Envio ---
    if use_ssl:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30) as server:
            # server.set_debuglevel(1)  # debug opcional
            if smtp_usuario and smtp_senha:
                server.login(smtp_usuario, smtp_senha)
            server.send_message(msg)
        return

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        # server.set_debuglevel(1)  # debug opcional
        server.ehlo()
        if use_tls:
            server.starttls()
            server.ehlo()
        if smtp_usuario and smtp_senha:
            server.login(smtp_usuario, smtp_senha)
        server.send_message(msg)
