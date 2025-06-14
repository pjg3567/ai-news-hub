# generate_email.py - FINAL VERSION
import os
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from dateutil import parser
from collections import defaultdict

load_dotenv()
app = Flask(__name__)

# --- HELPER FUNCTIONS COPIED FROM APP.PY ---

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    return conn

def format_date(date_string):
    """Parses a date string and formats it nicely."""
    if not date_string: return "No Date Provided"
    try:
        if hasattr(date_string, 'strftime'):
            return date_string.strftime('%B %d, %Y')
        return parser.parse(date_string).strftime('%B %d, %Y')
    except (ValueError, TypeError):
        return str(date_string)

app.jinja_env.filters['format_date'] = format_date

def fetch_trending_news():
    """
    Fetches trending AI news from the last 24 hours, ensuring a diversity of sources.
    """
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        print("NEWS_API_KEY not found in .env file.")
        return []

    # --- NEW: Date Filtering Logic ---
    from datetime import datetime, timedelta
    # Get yesterday's date in the required format (YYYY-MM-DD)
    yesterday = datetime.now() - timedelta(days=1)
    from_date_str = yesterday.strftime('%Y-%m-%d')
    # --- END OF NEW LOGIC ---
    
    excluded_domains = "wired.com,wsj.com,nytimes.com,bloomberg.com,ft.com,thetimes.co.uk"
    
    url = (
        "https://newsapi.org/v2/everything?"
        "q=(Artificial Intelligence OR AI OR LLM OR OpenAI OR DeepMind OR Anthropic)&"
        "language=en&"
        "sortBy=popularity&"
        f"from={from_date_str}&"  # <-- ADDED DATE FILTER
        "pageSize=40&"
        f"excludeDomains={excluded_domains}&"
        "apiKey=" + api_key
    )
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        all_articles = response.json().get('articles', [])
        
        # Source Diversification Logic
        diverse_articles = []
        used_sources = set()

        for article in all_articles:
            source_name = article.get('source', {}).get('name')
            if source_name and source_name not in used_sources:
                diverse_articles.append(article)
                used_sources.add(source_name)
            
            if len(diverse_articles) >= 5:
                break
        
        print(f"Found {len(diverse_articles)} fresh trending articles.")
        return diverse_articles

    except requests.exceptions.RequestException as e:
        print(f"Error fetching trending news: {e}")
        return []

# --- MAIN FUNCTION ---

def generate_email_html():
    """Queries the DB, groups articles, and returns the email content as an HTML string, or None."""
    print("Fetching news for email digest...")
    trending_articles = fetch_trending_news()
    
    print("Connecting to database for analyzed articles...")
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cut_off_date = datetime.now(timezone.utc) - timedelta(days=1)
    
    # --- THIS IS THE CORRECTED QUERY ---
    cur.execute('''
        SELECT * FROM articles 
        WHERE created_at >= %s
        ORDER BY
            CASE
                WHEN category = 'New Research Paper' THEN 0
                WHEN category = 'New Model Release' THEN 1
                ELSE 2
            END,
            published_at DESC
    ''', (cut_off_date,))
    # --- END OF CORRECTION ---
    db_articles = cur.fetchall()
    cur.close()
    conn.close()
    
    if not db_articles and not trending_articles:
        print("No new content to report.")
        return None

    # This logic correctly groups the sorted articles
    grouped_articles = defaultdict(list)
    for article in db_articles:
        grouped_articles[article['category']].append(dict(article))

    print(f"Found {len(db_articles)} analyzed articles and {len(trending_articles)} trending articles.")
    with app.app_context():
        html_output = render_template(
            'email_template.html', 
            grouped_articles=grouped_articles, # Pass the grouped dictionary
            trending_articles=trending_articles,
            today=datetime.now().strftime('%B %d, %Y'),
            webapp_url=os.getenv("RENDER_URL", "http://127.0.0.1:5000")
        )
    return html_output

    # --- NEW: Group articles by category, just like in app.py ---
    grouped_articles = defaultdict(list)
    for article in db_articles:
        grouped_articles[article['category']].append(dict(article))
    # -----------------------------------------------------------

    print(f"Found {len(db_articles)} analyzed articles and {len(trending_articles)} trending articles.")
    with app.app_context():
        html_output = render_template(
            'email_template.html', 
            grouped_articles=grouped_articles, # Pass the grouped dictionary
            trending_articles=trending_articles,
            today=datetime.now().strftime('%B %d, %Y'),
            webapp_url=os.getenv("RENDER_URL", "http://127.0.0.1:5000") # Pass the web app URL
        )
    return html_output

# This block lets you run this file manually to create the preview file
if __name__ == '__main__':
    html = generate_email_html()
    if html:
        with open('daily_digest.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("Successfully generated 'daily_digest.html' for review.")