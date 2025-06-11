# send_email.py - FINAL BROADCAST VERSION
import smtplib
import os
import psycopg2 # For connecting to PostgreSQL
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from datetime import datetime

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    load_dotenv()
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    return conn

def send_digest_email(html_content):
    """
    Fetches all subscribers from the database and sends them the daily digest.
    """
    load_dotenv()

    SENDER_EMAIL = os.getenv("SENDER_EMAIL")
    SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

    if not all([SENDER_EMAIL, SENDER_PASSWORD]):
        print("Error: Missing email credentials in .env file.")
        return False

    # --- NEW: Fetch subscribers from the database ---
    print("Fetching subscriber list from database...")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT email FROM subscribers;")
    subscribers = cur.fetchall()
    cur.close()
    conn.close()

    if not subscribers:
        print("No subscribers found. No email will be sent.")
        return False
    
    # The list of recipients is a list of tuples, e.g., [('test@test.com',), ('test2@test.com',)]
    # We need to extract the first element from each tuple.
    recipient_list = [item[0] for item in subscribers]
    print(f"Found {len(recipient_list)} subscribers. Preparing to send.")
    # -----------------------------------------------

    message = MIMEMultipart("alternative")
    message["Subject"] = f"Your AI News Digest - {datetime.now().strftime('%B %d, %Y')}"
    message["From"] = SENDER_EMAIL
    # The 'To' field can be your own email, as subscribers will be in BCC
    message["To"] = SENDER_EMAIL 
    # Add all subscribers to the BCC field
    message["Bcc"] = ", ".join(recipient_list)

    message.attach(MIMEText(html_content, "html"))

    print(f"Connecting to SMTP server to send email to {len(recipient_list)} recipients...")
    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        # The sendmail method correctly handles the To and Bcc fields
        server.send_message(message)
        server.quit()
        print("Email sent successfully!")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

# This block allows you to run this file manually
if __name__ == '__main__':
    try:
        with open('daily_digest.html', 'r', encoding='utf-8') as f:
            html = f.read()
        send_digest_email(html)
    except FileNotFoundError:
        print("Error: 'daily_digest.html' not found. You must run generate_email.py first.")