import sqlite3
import os
import requests # <-- ADDED IMPORT
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template
from dateutil import parser
from dotenv import load_dotenv

# This script uses Flask's templating engine outside of a web context
# to generate the HTML for our email.
app = Flask(__name__)
load_dotenv() # Load .env variables


# --- START OF ADDED/MODIFIED CODE ---

def format_date(date_string):
    """Parses a date string and formats it nicely."""
    if not date_string:
        return "No Date Provided"
    try:
        dt_aware = parser.parse(date_string)
        return dt_aware.strftime('%B %d, %Y')
    except (ValueError, TypeError):
        return date_string

app.jinja_env.filters['format_date'] = format_date

def fetch_trending_news():
    """Fetches trending AI news from the NewsAPI."""
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        print("NEWS_API_KEY not found in .env file.")
        return []
    
    # List of domains known for hard paywalls to exclude
    excluded_domains = "wsj.com,nytimes.com,bloomberg.com,ft.com,thetimes.co.uk"
    
    url = (
        "https://newsapi.org/v2/everything?"
        "q=(Artificial Intelligence OR AI OR LLM OR OpenAI OR DeepMind OR Anthropic)&"
        "language=en&"
        "sortBy=popularity&"
        f"excludeDomains={excluded_domains}&"
        "apiKey=" + api_key
    )
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data.get('articles', [])[:5]
    except requests.exceptions.RequestException as e:
        print(f"Error fetching trending news: {e}")
        return []

# --- END OF ADDED/MODIFIED CODE ---


def get_db_connection():
    conn = sqlite3.connect('news.db')
    conn.row_factory = sqlite3.Row
    return conn

def generate_email_content():
    """Queries the DB for recent articles and generates an HTML file."""
    print("Fetching live trending news...")
    trending_articles = fetch_trending_news()

    print("Connecting to database for analyzed articles...")
    conn = get_db_connection()
    
    cut_off_date = datetime.now(timezone.utc) - timedelta(days=1)
    
    db_articles = conn.execute('''
        SELECT * FROM articles 
        WHERE created_at >= ?
        ORDER BY
            CASE
                WHEN category = 'New Research Paper' THEN 0
                WHEN category = 'New Model Release' THEN 1
                ELSE 2
            END,
            category,
            published_at DESC
    ''', (cut_off_date,)).fetchall()
    conn.close()
    print(f"Found {len(db_articles)} new analyzed articles from the last 24 hours.")

    if not db_articles and not trending_articles:
        print("No new content to report. No email will be generated.")
        return

    # --- START OF FIX ---
    # Get today's date and format it as a string
    today_formatted_string = datetime.now().strftime('%B %d, %Y')
    
    with app.app_context():
        # Pass the date string to the template under the variable name 'today'
        html_output = render_template(
            'email_template.html', 
            articles=db_articles, 
            trending_articles=trending_articles,
            today=today_formatted_string 
        )
    # --- END OF FIX ---

    with open('daily_digest.html', 'w', encoding='utf-8') as f:
        f.write(html_output)

    print("Successfully generated 'daily_digest.html'. Please review it before sending.")

if __name__ == '__main__':
    generate_email_content()