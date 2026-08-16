"""
Email sending service for OTP authentication.

Supports:
  1. Resend API (recommended, via RESEND_API_KEY)
  2. SMTP (via SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD)
  3. Server log fallback during development if no provider key is configured
"""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger("expense-intelligence.auth.email")


def send_otp_email(recipient_email: str, otp_code: str) -> tuple[bool, str]:
    """
    Send a 6-digit OTP code to any recipient email address.
    Supports:
      1. Brevo API (BREVO_API_KEY) - delivers to ALL emails (300 free emails/day)
      2. Resend API (RESEND_API_KEY)
      3. Standard SMTP (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD)
    """
    email_from = os.getenv("EMAIL_FROM", "auth@expense-intelligence.com")
    email_from_name = os.getenv("EMAIL_FROM_NAME", "Smart Expense Intelligence")

    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff;">
        <div style="text-align: center; margin-bottom: 20px;">
            <h2 style="color: #1e1b4b; margin: 0;">Smart Expense Intelligence</h2>
            <p style="color: #64748b; font-size: 14px; margin-top: 4px;">Secure Account Verification</p>
        </div>
        <div style="background: #f8fafc; border-radius: 8px; padding: 20px; text-align: center; margin-bottom: 20px;">
            <span style="font-size: 32px; font-weight: 800; letter-spacing: 6px; color: #4338ca;">{otp_code}</span>
        </div>
        <p style="color: #475569; font-size: 14px; line-height: 1.5; margin: 0 0 12px 0;">
            Use this 6-digit verification code to complete your signup. This code is valid for <strong>5 minutes</strong>.
        </p>
        <p style="color: #94a3b8; font-size: 12px; margin: 0;">
            If you did not request this verification code, please ignore this email.
        </p>
    </div>
    """

    # 1. Brevo HTTP API (Delivers to ANY email without sandbox lock)
    brevo_api_key = os.getenv("BREVO_API_KEY")
    if brevo_api_key and brevo_api_key.strip():
        try:
            import requests
            url = "https://api.brevo.com/v3/smtp/email"
            headers = {
                "accept": "application/json",
                "api-key": brevo_api_key.strip(),
                "content-type": "application/json",
            }
            payload = {
                "sender": {"name": email_from_name, "email": email_from},
                "to": [{"email": recipient_email}],
                "subject": f"Your Verification Code: {otp_code} - Smart Expense Intelligence",
                "htmlContent": html_content,
            }
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            if response.status_code in (200, 201, 202):
                logger.info(f"OTP sent successfully via Brevo API to {recipient_email}")
                return True, "Verification code sent to your email inbox."
            else:
                err_text = response.text
                logger.error(f"Brevo API error: {response.status_code} - {err_text}")
                return False, f"Brevo delivery failed: {err_text}"
        except Exception as e:
            logger.error(f"Brevo request failed: {e}")
            return False, f"Brevo delivery failed: {e}"

    # 2. Resend API
    resend_api_key = os.getenv("RESEND_API_KEY")
    if resend_api_key and resend_api_key.strip():
        try:
            import resend
            resend.api_key = resend_api_key.strip()
            params = {
                "from": os.getenv("EMAIL_FROM", "onboarding@resend.dev"),
                "to": [recipient_email],
                "subject": f"Your Verification Code: {otp_code} - Smart Expense Intelligence",
                "html": html_content,
            }
            resend.Emails.send(params)
            logger.info(f"OTP email sent via Resend to {recipient_email}")
            return True, "Verification code sent to your email inbox."
        except Exception as e:
            logger.error(f"Resend delivery failed: {e}")
            return False, f"Resend email delivery failed: {e}"

    # 3. SMTP (Supports Brevo SMTP smtp-relay.brevo.com or Gmail)
    smtp_host = os.getenv("SMTP_HOST")
    if smtp_host and smtp_host.strip():
        try:
            smtp_port = int(os.getenv("SMTP_PORT", 587))
            smtp_user = os.getenv("SMTP_USER", "")
            smtp_pass = os.getenv("SMTP_PASSWORD", "")

            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"Your Verification Code: {otp_code} - Smart Expense Intelligence"
            msg["From"] = f"{email_from_name} <{email_from}>"
            msg["To"] = recipient_email
            msg.attach(MIMEText(html_content, "html"))

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.starttls()
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.sendmail(email_from, recipient_email, msg.as_string())

            logger.info(f"OTP email sent via SMTP to {recipient_email}")
            return True, "Verification code sent to your email."
        except Exception as e:
            logger.error(f"SMTP delivery failed: {e}")
            return False, f"SMTP delivery failed: {e}"

    logger.error("No email service configured. Please set BREVO_API_KEY in backend .env")
    return False, "Email service not configured. Please set BREVO_API_KEY in backend .env."



