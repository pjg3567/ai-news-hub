# main.py - FINAL PostgreSQL VERSION
import os
import requests
import feedparser
import trafilatura
import json5 as json
import psycopg2
import google.generativeai as genai # <-- THE MISSING IMPORT
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from dateutil import parser

# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION ---
SOURCES = {
    "arXiv: AI": "https://arxiv.org/rss/cs.AI",
    "arXiv: Computation and Language": "https://arxiv.org/rss/cs.CL",
    "arXiv: Machine Learning": "https://arxiv.org/rss/cs.LG",
    "Google AI Blog": "https://blog.google/technology/ai/rss/",
    "DeepMind Blog": "https://deepmind.google/blog/rss/",
    "OpenAI Blog": "https://openai.com/blog/rss.xml",
    "Microsoft AI Blog": "https://blogs.microsoft.com/ai/feed/",
    "Meta AI Blog": "https://ai.meta.com/blog/rss/",
    "Anthropic Blog": "https://www.anthropic.com/news/rss.xml",
    "VentureBeat AI": "https://feeds.feedburner.com/venturebeat/SZYF"
}
TIME_WINDOW_DAYS = 3
MAX_ARTICLES_PER_SOURCE = 5

# --- DATABASE FUNCTIONS (PostgreSQL Version) ---

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    return conn

def setup_database():
    """Creates tables in the PostgreSQL database if they don't exist."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id SERIAL PRIMARY KEY,
            url TEXT UNIQUE,
            title TEXT,
            source_name TEXT,
            published_at TIMESTAMPTZ,
            summary TEXT,
            innovation TEXT,
            impact TEXT,
            future TEXT,
            key_info TEXT,
            category TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
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
    print("Database tables verified and set up.")

def save_analysis_to_db(cursor, conn, article_url, title, published_date, source_name, analysis_dict):
    """Saves a single article's analysis to the database using an existing cursor."""
    try:
        cursor.execute('''
            INSERT INTO articles (url, title, published_at, source_name, summary, innovation, impact, future, key_info, category)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            article_url, title, published_date, source_name,
            analysis_dict.get('executive_summary'),
            analysis_dict.get('bulleted_analysis', {}).get('core_innovation'),
            analysis_dict.get('bulleted_analysis', {}).get('impacted_parties'),
            analysis_dict.get('bulleted_analysis', {}).get('future_advancements'),
            json.dumps(analysis_dict.get('key_information')),
            analysis_dict.get('categorize')
        ))
        conn.commit()
        print(f"Successfully saved analysis for {article_url}")
    except psycopg2.IntegrityError:
        print(f"Article from {article_url} is already in the database.")
        conn.rollback()
    except Exception as e:
        print(f"Failed to save to database: {e}")
        conn.rollback()


# --- CORE LOGIC FUNCTIONS ---

def fetch_and_extract_article(article_url):
    """Fetches a single article and extracts its main text."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}
    try:
        print(f"Downloading content from: {article_url}")
        response = requests.get(article_url, headers=headers, timeout=15)
        response.raise_for_status()
        html_content = response.text
    except requests.exceptions.RequestException as e:
        print(f"Error downloading content. Reason: {e}")
        return None
    main_text = trafilatura.extract(html_content)
    print("Content extraction complete.")
    return main_text

def analyze_with_gemini(text_to_analyze):
    """Sends text to Gemini API for summary and analysis."""
    if not text_to_analyze or len(text_to_analyze) < 50:
        print("Text too short to analyze, skipping.")
        return None
        
    if len(text_to_analyze) > 100000:
        print("Warning: Input text is very long, truncating.")
        text_to_analyze = text_to_analyze[:100000]

    try:
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        model = genai.GenerativeModel('models/gemini-1.5-pro-latest')
        
        prompt_template = f"""
        **Role:** You are an expert AI researcher and analyst.

        **Task:** Analyze the following text from an AI news article/research paper. Provide a thorough summary and analysis structured in the following JSON format.

        **Instructions:**
        1.  Read the entire text carefully.
        2.  Provide a one-paragraph **executive_summary** that captures the core announcement or finding.
        3.  Generate a **bulleted_analysis** object covering the key implications:
            * **core_innovation**: What is the core innovation? (e.g., new architecture, new technique, new dataset)
            * **impacted_parties**: Who does this impact? (e.g., researchers, developers, specific industries)
            * **future_advancements**: What are the potential future advancements this could enable?
        4.  Extract **key_information** as a list of strings:
            * Name of the new model(s), if any.
            * Names of key researchers or organizations.
            * Any specific metrics or benchmarks mentioned (e.g., "achieved 95% on MMLU").
        5.  **categorize** the content as one of the following: "New Model Release", "New Research Paper", "Industry News", "Ethical Analysis", or "Community Update".

        **Input Text:**
        {text_to_analyze}

        **Output:**
        """
        
        response = model.generate_content(prompt_template)
        return response.text.strip().lstrip("```json").rstrip("```")
    except Exception as e:
        print(f"An error occurred while calling the Gemini API: {e}")
        return None


# --- MAIN EXECUTION BLOCK ---

if __name__ == '__main__':
    setup_database()
    cut_off_date = datetime.now(timezone.utc) - timedelta(days=TIME_WINDOW_DAYS)

    conn = get_db_connection()
    cur = conn.cursor()

    for source_name, rss_url in SOURCES.items():
        print(f"\n{'='*20}\nProcessing source: {source_name}\n{'='*20}")
        new_articles_count = 0
        try:
            feed = feedparser.parse(rss_url)
            if not feed.entries:
                print(f"No entries found for {source_name}.")
                continue
        except Exception as e:
            print(f"Could not parse RSS feed. Error: {e}")
            continue

        sorted_entries = sorted(
            feed.entries, 
            key=lambda e: e.get('published_parsed', e.get('updated_parsed', (0,0,0,0,0,0))), 
            reverse=True
        )

        for entry in sorted_entries:
            if new_articles_count >= MAX_ARTICLES_PER_SOURCE:
                print(f"Max article limit reached for {source_name}.")
                break
            
            published_date_str = entry.get('published', entry.get('updated'))
            if not published_date_str: continue

            try:
                published_date_dt = parser.parse(published_date_str)
                if published_date_dt.tzinfo is None:
                    published_date_dt = published_date_dt.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue
            
            if published_date_dt < cut_off_date:
                break

            cur.execute("SELECT id FROM articles WHERE url = %s", (entry.link,))
            if cur.fetchone():
                continue
            
            print(f"Found new article: {entry.title}")
            main_text = fetch_and_extract_article(entry.link)
            if main_text:
                analysis_json_str = analyze_with_gemini(main_text)
                if analysis_json_str:
                    try:
                        analysis_data = json.loads(analysis_json_str)
                        save_analysis_to_db(cur, conn, entry.link, entry.title, published_date_str, source_name, analysis_data)
                        new_articles_count += 1
                    except ValueError as e:
                        print(f"!!! JSON PARSING FAILED for article: {entry.title}. Error: {e}")

    cur.close()
    conn.close()
    print("\nAll sources processed.")