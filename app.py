import os
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from collections import defaultdict
from dateutil import parser
from datetime import timezone
from flask import Flask, render_template, request, redirect, url_for, flash
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "a_strong_default_secret_key_for_dev")

def setup_database():
    """Creates tables in the PostgreSQL database if they don't exist."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id SERIAL PRIMARY KEY, url TEXT UNIQUE, title TEXT, 
            source_name TEXT, published_at TIMESTAMPTZ, summary TEXT, 
            innovation TEXT, impact TEXT, future TEXT, key_info TEXT, 
            category TEXT, created_at TIMESTAMPTZ DEFAULT NOW()
        );
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS subscribers (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            subscribed_at TIMESTAMPTZ DEFAULT NOW()
        );
    ''')
    conn.commit()
    cur.close()
    conn.close()

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

@app.route('/')
def index():
    """The main route of the web application."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    # The final, correct sorting query
    cur.execute('''
        SELECT * FROM articles 
        ORDER BY
            CASE
                WHEN category = 'New Research Paper' THEN 0
                WHEN category = 'New Model Release' THEN 1
                ELSE 2
            END,
            published_at DESC
    ''')
    db_articles = cur.fetchall()
    cur.close()
    conn.close()

    grouped_articles = defaultdict(list)
    for article in db_articles:
        grouped_articles[article['category']].append(dict(article))

    trending_articles = fetch_trending_news()
    return render_template('index.html', grouped_articles=grouped_articles, trending_articles=trending_articles)

@app.route('/subscribe', methods=['POST'])
def subscribe():
    """Handles the subscription form submission."""
    email = request.form.get('email')
    if not email:
        flash('Email is required!', 'error')
        return redirect(url_for('index'))

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('INSERT INTO subscribers (email) VALUES (%s)', (email,))
        conn.commit()
        flash('Thank you for subscribing!', 'success')
    except psycopg2.IntegrityError:
        conn.rollback()
        flash('This email address is already subscribed.', 'info')
    except Exception as e:
        conn.rollback()
        flash(f'An error occurred: {e}', 'error')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('index'))

# This block ensures setup_database() is called before the first request
# in a development environment or when the app boots on Render.
with app.app_context():
    setup_database()

if __name__ == '__main__':
    app.run(debug=True)