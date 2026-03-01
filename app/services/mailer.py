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
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{sender_name} <{sender_email}>" if sender_name else sender_email
    msg["To"] = ", ".join(list(to_emails))

    if text_body:
        msg.set_content(text_body)
        msg.add_alternative(html_body, subtype="html")
    else:
        # fallback: envia html como alternativa e um texto simples mínimo
        msg.set_content("Este e-mail contém um relatório em HTML.")
        msg.add_alternative(html_body, subtype="html")

    if use_ssl:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30) as server:
            if smtp_usuario and smtp_senha:
                server.login(smtp_usuario, smtp_senha)
            server.send_message(msg)
        return

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.ehlo()
        if use_tls:
            server.starttls()
            server.ehlo()
        if smtp_usuario and smtp_senha:
            server.login(smtp_usuario, smtp_senha)
        server.send_message(msg)
