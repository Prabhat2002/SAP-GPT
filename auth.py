import smtplib
import random
import os
from email.mime.text import MIMEText
from database import save_otp, verify_otp, email_exists

def _get_smtp_creds():
    try:
        import streamlit as st
        email = st.secrets.get("SENDER_EMAIL", os.environ.get("SENDER_EMAIL", ""))
        pwd   = st.secrets.get("SENDER_PASSWORD", os.environ.get("SENDER_PASSWORD", ""))
        return email, pwd
    except Exception:
        return os.environ.get("SENDER_EMAIL", ""), os.environ.get("SENDER_PASSWORD", "")


def generate_otp():
    return str(random.randint(100000, 999999))


def send_otp_email(to_email):
    """Send OTP. Returns (otp, success, error_msg)."""
    otp = generate_otp()
    save_otp(to_email, otp)

    sender_email, sender_password = _get_smtp_creds()

    if not sender_email or not sender_password:
        return otp, False, "EMAIL_NOT_CONFIGURED"

    try:
        msg = MIMEText(f"""
Hello,

Your SAP-GPT verification code is:

  {otp}

This code expires in 10 minutes.

— SAP-GPT Team
""")
        msg["Subject"] = f"Your SAP-GPT OTP: {otp}"
        msg["From"] = sender_email
        msg["To"] = to_email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, msg.as_string())

        return otp, True, None

    except Exception as e:
        return otp, False, str(e)


# Legacy compat
def register_user(username, password):
    from database import get_connection
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    if cur.fetchone():
        cur.close(); conn.close()
        return False
    cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
    conn.commit()
    cur.close(); conn.close()
    return True


def login_user(username, password):
    from database import get_connection
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username = ? AND password = ?", (username, password))
    row = cur.fetchone()
    cur.close(); conn.close()
    return row[0] if row else None
