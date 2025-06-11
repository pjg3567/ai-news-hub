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
    """Fetches trending AI news from the NewsAPI."""
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        print("NEWS_API_KEY not found in .env file.")
        return []
    
    excluded_domains = "wsj.com,nytimes.com,bloomberg.com,ft.com,thetimes.co.uk,wired.com"
    url = f"https://newsapi.org/v2/everything?q=(Artificial Intelligence OR AI OR LLM)&language=en&sortBy=popularity&excludeDomains={excluded_domains}&apiKey={api_key}"
    
    try:
        response = requests.get(url, timeout=10) # Added a timeout
        response.raise_for_status()
        data = response.json()
        return data.get('articles', [])[:5]
    except requests.exceptions.RequestException as e:
        print(f"Error fetching trending news: {e}")
        return []

@app.route('/')
def index():
    """The main route of the web application."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    # The correct, advanced sorting query
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

    # --- START OF DEBUG BLOCK ---
    if db_articles:
        # Get the very first article from the sorted list
        first_article = db_articles[0]
        print("\n--- DEBUG: RAW DATA FOR LATEST ARTICLE ---")
        print(f"  Title: {first_article['title']}")
        print(f"  Source: {first_article['source_name']}")
        print(f"  PUBLISHED_AT from DB: {first_article['published_at']}")
        print(f"  CREATED_AT from DB:   {first_article['created_at']}")
        print("--------------------------------------------\n")
    # --- END OF DEBUG BLOCK ---

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