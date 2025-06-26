"""
Legacy adapter to maintain compatibility with existing news_client.py interface
while transitioning to the new services architecture.
"""

from typing import List, Dict
from .article_factory import ArticleServiceFactory

def fetch_articles(query: str, from_date: str = None, language: str = 'en') -> List[Dict]:
    """
    Legacy-compatible wrapper around the new article service architecture.
    
    This function maintains the same interface as the original news_client.fetch_articles()
    but uses the new service architecture under the hood.
    
    Args:
        query: Search term for articles
        from_date: Optional start date (YYYY-MM-DD)
        language: Language code (default: 'en')
        
    Returns:
        List of article dictionaries in the legacy format
    """
    try:
        # Create service instance
        service = ArticleServiceFactory.create_service()
        
        # Fetch articles using new service
        kwargs = {'language': language}
        if from_date:
            kwargs['from_date'] = from_date
            
        articles = service.fetch_articles(query, max_articles=10, **kwargs)
        
        # Convert to legacy format for backward compatibility
        legacy_articles = []
        for article in articles:
            legacy_article = {
                'url': article.url,
                'title': article.title,
                'content': article.content,
                'source': {'name': article.source} if article.source else {'name': None},
                'publishedAt': article.published_at,
                'author': article.author
            }
            legacy_articles.append(legacy_article)
        
        return legacy_articles
        
    except Exception as e:
        # Log error but return empty list to maintain legacy behavior
        import logging
        logging.error(f"Error in legacy adapter: {e}")
        return [] 