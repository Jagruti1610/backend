"""
app/services/email.py — sends password reset email via SendGrid API.
Works on Render free tier (no SMTP port restrictions).
"""

import requests
from ..core.config import settings

def send_reset_email(to_email: str, reset_link: str) -> None:
    """Raises an exception if sending fails."""
    
    if not settings.SENDGRID_API_KEY or not settings.FROM_EMAIL:
        raise RuntimeError(
            "SENDGRID_API_KEY / FROM_EMAIL not set in environment variables. "
            "Please add them in Render dashboard or .env file."
        )

    subject = "Reset your Legal Summarizer password"
    body = f"""Hi,

We received a request to reset your password.

Click the link below to set a new password. This link expires in 15 minutes:

{reset_link}

If you didn't request this, you can safely ignore this email — your
password will not change.

- Legal Summarizer
"""

    url = "https://api.sendgrid.com/v3/mail/send"
    headers = {
        "Authorization": f"Bearer {settings.SENDGRID_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "personalizations": [
            {
                "to": [{"email": to_email}],
                "subject": subject
            }
        ],
        "from": {"email": settings.FROM_EMAIL},
        "content": [{"type": "text/plain", "value": body}]
    }

    response = requests.post(url, json=data, headers=headers, timeout=30)

    if response.status_code != 202:
        raise Exception(f"SendGrid error: {response.status_code} - {response.text}")