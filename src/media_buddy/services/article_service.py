from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import logging

class ArticleFetchError(Exception):
    """Raised when there's an error fetching articles from any service."""
    pass

class Article:
    """Standardized article representation across all services."""
    
    def __init__(self, url: str, title: str, content: str, source: Optional[str] = None, 
                 published_at: Optional[str] = None, author: Optional[str] = None):
        self.url = url
        self.title = title
        self.content = content
        self.source = source
        self.published_at = published_at
        self.author = author
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for database storage compatibility."""
        return {
            'url': self.url,
            'title': self.title,
            'content': self.content,
            'source': self.source,
            'published_at': self.published_at,
            'author': self.author
        }

class ArticleService(ABC):
    """Abstract base class for article fetching services."""
    
    @abstractmethod
    def fetch_articles(self, query: str, max_articles: int = 10, **kwargs) -> List[Article]:
        """
        Fetch articles based on a search query.
        
        Args:
            query: Search term for articles
            max_articles: Maximum number of articles to return
            **kwargs: Service-specific parameters
            
        Returns:
            List of Article objects
            
        Raises:
            ArticleFetchError: If fetching fails
        """
        pass
    
    @abstractmethod
    def get_service_name(self) -> str:
        """Return the name of this service for logging/debugging."""
        pass
    
    def validate_article(self, article: Article) -> bool:
        """
        Validate that an article has the minimum required content.
        
        Args:
            article: Article to validate
            
        Returns:
            True if article is valid, False otherwise
        """
        if not article.url or not article.title:
            return False
            
        if not article.content or len(article.content.strip()) < 100:
            logging.warning(f"Article '{article.title}' has insufficient content ({len(article.content)} chars)")
            return False
            
        return True 