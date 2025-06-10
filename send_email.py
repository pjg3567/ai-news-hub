# send_email.py - FINAL VERSION
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from datetime import datetime

def send_digest_email(html_content):
    """Sends the provided HTML content as an email digest."""
    load_dotenv()

    SENDER_EMAIL = os.getenv("SENDER_EMAIL")
    SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
    RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")

    if not all([SENDER_EMAIL, SENDER_PASSWORD, RECIPIENT_EMAIL]):
        print("Error: Missing email credentials in .env file.")
        return False

    message = MIMEMultipart("alternative")
    message["Subject"] = f"Your AI News Digest - {datetime.now().strftime('%B %d, %Y')}"
    message["From"] = SENDER_EMAIL
    message["To"] = RECIPIENT_EMAIL
    message.attach(MIMEText(html_content, "html"))

    print(f"Connecting to SMTP server to send email to {RECIPIENT_EMAIL}...")
    try:
        # Assuming Gmail SMTP server
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, message.as_string())
        server.quit()
        print("Email sent successfully!")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

# This block allows you to still run this file manually for testing if needed
if __name__ == '__main__':
    try:
        with open('daily_digest.html', 'r', encoding='utf-8') as f:
            html = f.read()
        send_digest_email(html)
    except FileNotFoundError:
        print("Error: 'daily_digest.html' not found. You can generate one by running generate_email.py manually.")