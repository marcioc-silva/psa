import requests

RESEND_API_URL = "https://api.resend.com/emails"

def send_email_resend(
    *,
    api_key: str,
    sender_email: str,
    sender_name: str | None,
    to_emails: list[str],
    subject: str,
    html_body: str,
):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "from": f"{sender_name} <{sender_email}>" if sender_name else sender_email,
        "to": to_emails,
        "subject": subject,
        "html": html_body,
    }

    response = requests.post(RESEND_API_URL, json=payload, headers=headers, timeout=30)

    if response.status_code >= 400:
        raise Exception(f"Erro Resend: {response.text}")
