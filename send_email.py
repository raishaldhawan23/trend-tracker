"""
Sends the daily pulse digest to yourself via Gmail SMTP, using a Gmail App
Password (not your normal Gmail password — App Passwords are a separate
16-character code Gmail generates for exactly this kind of script access).

One-time setup:
  1. Turn on 2-Step Verification on your Google account, if it isn't already
     (App Passwords require it): https://myaccount.google.com/security
  2. Generate an App Password: https://myaccount.google.com/apppasswords
     — pick "Mail" as the app, name it e.g. "niche-pulse-tracker", copy the
     16-character code it gives you (spaces don't matter).
  3. In the GitHub repo: Settings -> Secrets and variables -> Actions -> New
     repository secret. Add two secrets:
       GMAIL_ADDRESS       -> your full Gmail address
       GMAIL_APP_PASSWORD  -> the 16-character code from step 2
  4. Locally (if testing outside GitHub Actions), set the same two as
     environment variables before running `python pulse.py --email`.

This sends from your own address to your own address, so it shows up as an
email "from yourself" in your inbox, as requested.
"""
import os
import smtplib
from email.mime.text import MIMEText

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def is_configured():
    return bool(os.environ.get("GMAIL_ADDRESS") and os.environ.get("GMAIL_APP_PASSWORD"))


def send_digest(subject, markdown_body):
    address = os.environ.get("GMAIL_ADDRESS", "").strip()
    app_password = os.environ.get("GMAIL_APP_PASSWORD", "").strip()

    if not address or not app_password:
        print(
            "[send_email] GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set — skipping email send. "
            "See this file's module docstring for one-time setup steps."
        )
        return False

    # Sent as plain text (not HTML) so markdown headers/links stay readable
    # as-is in a plain-text mail client; most webmail clients render the
    # markdown legibly enough without needing an HTML conversion step.
    msg = MIMEText(markdown_body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = address
    msg["To"] = address

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(address, app_password)
            server.send_message(msg)
        print(f"[send_email] Sent digest to {address}.")
        return True
    except Exception as e:
        print(f"[send_email] Failed to send: {e}")
        return False


if __name__ == "__main__":
    # Quick manual test: `python send_email.py` sends a canned test message.
    send_digest("Niche Pulse — test email", "This is a test of the niche-pulse email sender.")
