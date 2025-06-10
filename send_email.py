import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

def send_email():
    """Reads the generated HTML digest and sends it via email."""
    load_dotenv()

    SENDER_EMAIL = os.getenv("SENDER_EMAIL")
    SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
    RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")

    if not all([SENDER_EMAIL, SENDER_PASSWORD, RECIPIENT_EMAIL]):
        print("Error: Missing email credentials in .env file.")
        return

    try:
        with open('daily_digest.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
    except FileNotFoundError:
        print("Error: 'daily_digest.html' not found. Please run generate_email.py first.")
        return

    message = MIMEMultipart("alternative")
    message["Subject"] = f"Your AI News Digest - {datetime.now().strftime('%B %d, %Y')}"
    message["From"] = SENDER_EMAIL
    message["To"] = RECIPIENT_EMAIL

    # Attach the HTML content
    message.attach(MIMEText(html_content, "html"))

    print(f"Connecting to SMTP server to send email to {RECIPIENT_EMAIL}...")
    # Use a secure SSL context
    try:
        # Assuming Gmail SMTP server
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, message.as_string())
        server.quit()
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == '__main__':
    # Need to import datetime to use in the subject line
    from datetime import datetime
    send_email()