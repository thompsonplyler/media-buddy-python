import requests
import logging
import os
import sys
from src.job_commando import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] - %(message)s')

BASE_URL = "https://newsapi.org/v2/everything"

def fetch_articles(query: str, from_date: str = None, language: str = 'en'):
    """
    Fetches news articles from the NewsAPI based on a query.

    Args:
        query (str): The search term for articles.
        from_date (str, optional): The start date to search from (YYYY-MM-DD). Defaults to None.
        language (str, optional): The language of the articles. Defaults to 'en'.

    Returns:
        list: A list of articles, or an empty list if an error occurs.
    """
    if not config.NEWS_API_KEY:
        logging.error("NEWS_API_KEY not found in environment. Cannot fetch articles.")
        return []

    params = {
        'q': query,
        'language': language,
        'apiKey': config.NEWS_API_KEY,
        'sortBy': 'relevancy' # Or 'popularity', 'publishedAt'
    }
    if from_date:
        params['from'] = from_date

    logging.info(f"Fetching articles with query: '{query}'")

    try:
        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
        
        data = response.json()
        articles = data.get('articles', [])
        
        logging.info(f"Successfully fetched {len(articles)} articles.")
        return articles

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching articles from NewsAPI: {e}")
        return []
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return []

if __name__ == '__main__':
    # This block needs the path correction to run standalone
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    from src.job_commando.news_client import fetch_articles

    test_articles = fetch_articles(query="artificial intelligence")
    if test_articles:
        for article in test_articles[:2]: # Print first 2 articles
            print(f"  - Title: {article.get('title')}")
            print(f"    Source: {article.get('source', {}).get('name')}")
            print(f"    URL: {article.get('url')}") 