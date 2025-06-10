import os
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from dateutil import parser

load_dotenv()
app = Flask(__name__)

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
    """Fetches trending AI news from the NewsAPI."""
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key: return []
    excluded_domains = "wired.com,wsj.com,nytimes.com,bloomberg.com,ft.com,thetimes.co.uk"
    url = f"https://newsapi.org/v2/everything?q=(Artificial Intelligence OR AI OR LLM)&language=en&sortBy=popularity&excludeDomains={excluded_domains}&apiKey={api_key}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json().get('articles', [])[:5]
    except requests.exceptions.RequestException as e:
        print(f"Error fetching trending news: {e}")
        return []

def generate_email_content():
    """Queries the DB for recent articles and generates an HTML file."""
    print("Fetching live trending news...")
    trending_articles = fetch_trending_news()
    
    print("Connecting to database for analyzed articles...")
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cut_off_date = datetime.now(timezone.utc) - timedelta(days=1)
    
    # Use %s for PostgreSQL placeholders
    cur.execute('SELECT * FROM articles WHERE created_at >= %s ORDER BY category, published_at DESC', (cut_off_date,))
    db_articles = cur.fetchall()
    cur.close()
    conn.close()
    print(f"Found {len(db_articles)} new analyzed articles from the last 24 hours.")

    if not db_articles and not trending_articles:
        print("No new content to report. No email will be generated.")
        return

    with app.app_context():
        html_output = render_template(
            'email_template.html', 
            articles=db_articles, 
            trending_articles=trending_articles,
            today=datetime.now().strftime('%B %d, %Y')
        )

    with open('daily_digest.html', 'w', encoding='utf-8') as f:
        f.write(html_output)
    print("Successfully generated 'daily_digest.html'. Please review it before sending.")

if __name__ == '__main__':
    generate_email_content()