import os
import feedparser
import trafilatura
import google.generativeai as genai
import json5 as json
import sqlite3
import requests
from datetime import datetime, timedelta, timezone
from dateutil import parser
# Just after your imports
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
from dotenv import load_dotenv

# --- Step 1: Configuration ---
# Load environment variables from .env file
load_dotenv()

# Configure the Gemini API client
try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
except TypeError:
    print("ERROR: GOOGLE_API_KEY not found. Please ensure it is set in your .env file.")
    exit()

# --- Step 2: Function to Fetch and Extract Article ---
def fetch_and_extract_article(article_url):
    """Fetches a single article and extracts its main text."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}
    try:
        print(f"Downloading content from: {article_url}")
        response = requests.get(article_url, headers=headers, timeout=10)
        response.raise_for_status()
        html_content = response.text
    except requests.exceptions.RequestException as e:
        print(f"Error downloading content. Reason: {e}")
        return None, None, None, None # Return four Nones to match expected output

    main_text = trafilatura.extract(html_content, include_comments=False, include_tables=False)
    print("Content extraction complete.")
    
    # This function is now simpler, it doesn't need to return metadata we already have
    return main_text, article_url, None, None

# --- Step 3: Function to Analyze Text with Gemini ---
def analyze_with_gemini(text_to_analyze):
    """Sends text to Gemini API for summary and analysis."""
    # Safeguard for very long texts to avoid exceeding API limits
    if len(text_to_analyze) > 100000:
        print("Warning: Input text is very long, truncating to 100,000 characters.")
        text_to_analyze = text_to_analyze[:100000]

    # Initialize the Gemini model
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
    
    try:
        print("Sending text to Gemini for analysis...")
        response = model.generate_content(prompt_template)
        # The Gemini API often wraps the JSON in ```json ... ```, so we clean it.
        cleaned_json = response.text.strip().lstrip("```json").rstrip("```")
        return cleaned_json
    except Exception as e:
        print(f"An error occurred while calling the Gemini API: {e}")
        return None

# --- Step 4: Setup Database ---
def setup_database():
    """Creates the SQLite database and articles table if they don't exist."""
    conn = sqlite3.connect('news.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            title TEXT,
            source_name TEXT,
            published_at DATETIME,
            summary TEXT,
            innovation TEXT,
            impact TEXT,
            future TEXT,
            key_info TEXT,
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    print("Database is set up.")

def save_analysis_to_db(article_url, title, published_date, source_name, analysis_dict):
    """Saves a single article's analysis to the database."""
    conn = sqlite3.connect('news.db')
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO articles (url, title, published_at, source_name, summary, innovation, impact, future, key_info, category)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            article_url,
            title,
            published_date,
            source_name,
            analysis_dict.get('executive_summary'),
            analysis_dict.get('bulleted_analysis', {}).get('core_innovation'),
            analysis_dict.get('bulleted_analysis', {}).get('impacted_parties'),
            analysis_dict.get('bulleted_analysis', {}).get('future_advancements'),
            json.dumps(analysis_dict.get('key_information')),
            analysis_dict.get('categorize')
        ))
        conn.commit()
        print(f"Successfully saved analysis for {article_url} to the database.")
    except sqlite3.IntegrityError:
        print(f"Article from {article_url} is already in the database.")
    except Exception as e:
        print(f"Failed to save to database: {e}")
    finally:
        conn.close()

# --- Step 5: Main Execution Block ---
if __name__ == "__main__":
    setup_database()

    # --- CONFIGURATION ---
    TIME_WINDOW_DAYS = 3
    MAX_ARTICLES_PER_SOURCE = 5 # Our new "safety brake"

    cut_off_date = datetime.now(timezone.utc) - timedelta(days=TIME_WINDOW_DAYS)

    for source_name, rss_url in SOURCES.items():
        print(f"\n{'='*20}\nProcessing source: {source_name}\n{'='*20}")

        new_articles_from_source_count = 0 # Counter for our safety brake

        feed = feedparser.parse(rss_url)
        if not feed.entries:
            print(f"No entries found for {source_name}.")
            continue

        for entry in feed.entries:
            # Stop processing this source if we've hit our max
            if new_articles_from_source_count >= MAX_ARTICLES_PER_SOURCE:
                print(f"Max article limit ({MAX_ARTICLES_PER_SOURCE}) reached for {source_name}. Moving to next source.")
                break

            published_date_str = entry.get('published', entry.get('updated', None))
            if not published_date_str:
                continue

            try:
                published_date_dt = parser.parse(published_date_str)
            except (ValueError, TypeError):
                continue

            if published_date_dt.tzinfo is None:
                published_date_dt = published_date_dt.replace(tzinfo=timezone.utc)

            if published_date_dt >= cut_off_date:
                conn = sqlite3.connect('news.db')
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM articles WHERE url = ?", (entry.link,))
                if cursor.fetchone():
                    conn.close()
                    continue # Skip article if already in DB
                conn.close()

                print(f"Found new article: {entry.title}")
                main_text, _, _, _ = fetch_and_extract_article(entry.link)

                if main_text:
                    analysis_json_str = analyze_with_gemini(main_text)
                    if analysis_json_str:
                        try:
                            analysis_data = json.loads(analysis_json_str)
                            save_analysis_to_db(entry.link, entry.title, published_date_str, source_name, analysis_data)
                            new_articles_from_source_count += 1 # Increment counter on success
                        except ValueError as e:
                            print(f"!!! JSON PARSING FAILED for article: {entry.title}. Error: {e}")
            else:
                print("Older articles found, moving to next source.")
                break

    print("\nAll sources processed.")