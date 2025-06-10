# run_daily_digest.py
from generate_email import generate_email_html
from send_email import send_digest_email

print("--- Starting Daily Digest Process ---")

# Step 1: Generate the HTML content
email_html = generate_email_html()

# Step 2: If content exists, send it.
if email_html:
    print("Content generated, proceeding to send email.")
    send_digest_email(email_html)
else:
    print("No new content found. No email will be sent.")

print("--- Daily Digest Process Finished ---")