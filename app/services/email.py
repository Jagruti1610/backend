"""
app/services/email.py — sends the "reset your password" email via Gmail SMTP.

Setup (one-time, on your Gmail account):
  1. Turn on 2-Step Verification: https://myaccount.google.com/security
  2. Create an "App Password": https://myaccount.google.com/apppasswords
     (choose app = Mail, device = Other -> name it "legal-summarizer")
     Google gives you a 16-character password like: abcd efgh ijkl mnop
  3. In backend/.env set:
       SMTP_EMAIL=youraddress@gmail.com
       SMTP_APP_PASSWORD=abcdefghijklmnop   (no spaces)
       FRONTEND_URL=http://localhost:5173

Do NOT use your normal Gmail password here — it will not work, and you
should never put your real password in a .env file anyway. Only the
16-character App Password works with SMTP.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from ..core.config import settings

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def send_reset_email(to_email: str, reset_link: str) -> None:
    """Raises an exception if sending fails — caller decides how to handle it."""
    if not settings.SMTP_EMAIL or not settings.SMTP_APP_PASSWORD:
        raise RuntimeError(
            "SMTP_EMAIL / SMTP_APP_PASSWORD not set in backend/.env — "
            "see app/services/email.py for setup steps."
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

    msg = MIMEMultipart()
    msg["From"] = settings.SMTP_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(settings.SMTP_EMAIL, settings.SMTP_APP_PASSWORD)
        server.sendmail(settings.SMTP_EMAIL, to_email, msg.as_string())