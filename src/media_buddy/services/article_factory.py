import os
import logging
from typing import Dict, Type
from .article_service import ArticleService
from .newsapi_service import NewsAPIService
from .googlenews_service import GoogleNewsService
from .archive_service import ArchiveService

class ArticleServiceFactory:
    """Factory for creating and managing article services."""
    
    _services: Dict[str, Type[ArticleService]] = {
        'newsapi': NewsAPIService,
        'googlenews': GoogleNewsService,
        'archive': ArchiveService,
    }
    
    @classmethod
    def register_service(cls, name: str, service_class: Type[ArticleService]):
        """Register a new article service."""
        cls._services[name] = service_class
        logging.info(f"Registered article service: {name}")
    
    @classmethod
    def create_service(cls, service_name: str = None) -> ArticleService:
        """
        Create an article service instance.
        
        Args:
            service_name: Name of service to create. If None, uses environment default.
            
        Returns:
            ArticleService instance
            
        Raises:
            ValueError: If service name is not registered or service creation fails
        """
        if not service_name:
            service_name = os.environ.get('ARTICLE_SERVICE', 'newsapi')
        
        if service_name not in cls._services:
            available = ', '.join(cls._services.keys())
            raise ValueError(f"Unknown article service '{service_name}'. Available: {available}")
        
        try:
            service_class = cls._services[service_name]
            service = service_class()
            logging.info(f"Created article service: {service.get_service_name()}")
            return service
        except Exception as e:
            raise ValueError(f"Failed to create service '{service_name}': {e}")
    
    @classmethod
    def list_services(cls) -> list:
        """Return list of available service names."""
        return list(cls._services.keys()) 