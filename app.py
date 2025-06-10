import sqlite3
import requests
import os
from collections import defaultdict
from dateutil import parser
from datetime import timezone
from flask import Flask, render_template

app = Flask(__name__)

def get_db_connection():
    """Establishes a connection to the database."""
    conn = sqlite3.connect('news.db')
    # This allows you to access columns by name
    conn.row_factory = sqlite3.Row
    return conn

def fetch_trending_news():
    """Fetches trending AI news from the NewsAPI."""
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        print("NEWS_API_KEY not found in .env file.")
        return []
    
    # List of domains known for hard paywalls to exclude
    excluded_domains = "wsj.com,nytimes.com,bloomberg.com,ft.com,thetimes.co.uk"

    # Construct the NewsAPI URL
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
        # Return only the top 5 trending articles
        return data.get('articles', [])[:5]
    except requests.exceptions.RequestException as e:
        print(f"Error fetching trending news: {e}")
        return []
    
def format_date(date_string):
    """Parses a date string and formats it nicely."""
    if not date_string:
        return "No Date Provided"
    try:
        # Parse the date string into a timezone-aware datetime object
        dt_aware = parser.parse(date_string)
        # Format it into a more readable string
        return dt_aware.strftime('%B %d, %Y')
    except (ValueError, TypeError):
        # If parsing fails, return the original string
        return date_string

# Register the function so templates can use it
app.jinja_env.filters['format_date'] = format_date
@app.route('/')
def index():
    """The main route of the web application."""
    conn = get_db_connection()
    db_articles = conn.execute('''
        SELECT * FROM articles ORDER BY published_at DESC
    ''').fetchall()
    conn.close()

    # Group articles by category
    grouped_articles = defaultdict(list)
    for article in db_articles:
        grouped_articles[article['category']].append(article)

    trending_articles = fetch_trending_news()

    return render_template('index.html', grouped_articles=grouped_articles, trending_articles=trending_articles)

if __name__ == '__main__':
    app.run(debug=True)