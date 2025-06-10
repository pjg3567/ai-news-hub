import sqlite3
import requests
import os
from collections import defaultdict
from dateutil import parser
from datetime import timezone
from flask import Flask, render_template, request, redirect, url_for, flash

# --- START OF ADDED CODE ---

def setup_database():
    """Creates the SQLite database and tables if they don't exist."""
    conn = sqlite3.connect('news.db')
    cursor = conn.cursor()
    # Create the articles table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT UNIQUE, title TEXT, 
            source_name TEXT, published_at DATETIME, summary TEXT, 
            innovation TEXT, impact TEXT, future TEXT, key_info TEXT, 
            category TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Create the subscribers table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    print("Database tables verified and set up.")

# --- END OF ADDED CODE ---


app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_very_secret_and_random_string_for_production'

# --- ADDED THIS LINE TO CALL THE FUNCTION AT STARTUP ---
setup_database()
# ----------------------------------------------------


def get_db_connection():
    """Establishes a connection to the database."""
    conn = sqlite3.connect('news.db')
    conn.row_factory = sqlite3.Row
    return conn

def fetch_trending_news():
    """Fetches trending AI news from the NewsAPI."""
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        print("NEWS_API_KEY not found in .env file.")
        return []
    
    excluded_domains = "wsj.com,nytimes.com,bloomberg.com,ft.com,thetimes.co.uk,wired.com"

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

@app.route('/')
def index():
    """The main route of the web application."""
    conn = get_db_connection()
    # Your original query had a bug, this is the corrected one for sorting
    db_articles = conn.execute('''
        SELECT * FROM articles 
        ORDER BY
            CASE
                WHEN category = 'New Research Paper' THEN 0
                WHEN category = 'New Model Release' THEN 1
                ELSE 2
            END,
            published_at DESC
    ''').fetchall()
    conn.close()

    grouped_articles = defaultdict(list)
    for article in db_articles:
        grouped_articles[article['category']].append(article)

    trending_articles = fetch_trending_news()

    return render_template('index.html', grouped_articles=grouped_articles, trending_articles=trending_articles)

@app.route('/subscribe', methods=['POST'])
def subscribe():
    email = request.form.get('email')
    if not email:
        flash('Email is required!', 'error')
        return redirect(url_for('index'))

    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO subscribers (email) VALUES (?)', (email,))
        conn.commit()
        flash('Thank you for subscribing!', 'success')
    except sqlite3.IntegrityError:
        flash('This email address is already subscribed.', 'info')
    except Exception as e:
        flash(f'An error occurred: {e}', 'error')
    finally:
        conn.close()

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)