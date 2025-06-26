import os
import requests
import logging
from typing import List
from .article_service import ArticleService, Article, ArticleFetchError

class NewsAPIService(ArticleService):
    """NewsAPI implementation of ArticleService (provides snippets only)."""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("NEWS_API_KEY")
        if not self.api_key:
            raise ValueError("NEWS_API_KEY not found in environment")
        
        self.base_url = "https://newsapi.org/v2/everything"
    
    def get_service_name(self) -> str:
        return "NewsAPI"
    
    def fetch_articles(self, query: str, max_articles: int = 10, **kwargs) -> List[Article]:
        """
        Fetch articles from NewsAPI.
        
        Note: NewsAPI only provides snippets, not full article content.
        """
        params = {
            'q': query,
            'language': kwargs.get('language', 'en'),
            'apiKey': self.api_key,
            'sortBy': kwargs.get('sort_by', 'relevancy'),
            'pageSize': min(max_articles, 100)  # NewsAPI max is 100
        }
        
        if 'from_date' in kwargs:
            params['from'] = kwargs['from_date']
        
        logging.info(f"Fetching articles from NewsAPI with query: '{query}'")
        
        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            articles_data = data.get('articles', [])
            
            articles = []
            for article_data in articles_data:
                # NewsAPI provides limited content (snippets)
                content = article_data.get('content', '') or ''
                
                article = Article(
                    url=article_data['url'],
                    title=article_data['title'],
                    content=content,
                    source=article_data.get('source', {}).get('name'),
                    published_at=article_data.get('publishedAt'),
                    author=article_data.get('author')
                )
                
                if self.validate_article(article):
                    articles.append(article)
                else:
                    logging.warning(f"Skipping invalid article: {article.title}")
            
            logging.info(f"Successfully fetched {len(articles)} valid articles from NewsAPI")
            return articles
            
        except requests.exceptions.RequestException as e:
            raise ArticleFetchError(f"Error fetching from NewsAPI: {e}")
        except Exception as e:
            raise ArticleFetchError(f"Unexpected error in NewsAPI service: {e}") 