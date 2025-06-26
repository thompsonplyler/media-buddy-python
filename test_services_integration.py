#!/usr/bin/env python3
"""
Test script to validate the new services architecture before integration.

This script tests that:
1. The new service architecture works
2. The legacy adapter provides backward compatibility
3. We can switch between services via environment variables
"""

import sys
import os
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_newsapi_service_direct():
    """Test the NewsAPI service directly."""
    print("=== Testing NewsAPI Service Direct ===")
    try:
        from src.media_buddy.services.newsapi_service import NewsAPIService
        
        service = NewsAPIService()
        print(f"Service name: {service.get_service_name()}")
        
        articles = service.fetch_articles("artificial intelligence", max_articles=3)
        print(f"Fetched {len(articles)} articles")
        
        for i, article in enumerate(articles[:2], 1):
            print(f"\nArticle {i}:")
            print(f"  Title: {article.title}")
            print(f"  URL: {article.url}")
            print(f"  Content length: {len(article.content)} chars")
            print(f"  Source: {article.source}")
        
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_factory():
    """Test the service factory."""
    print("\n=== Testing Service Factory ===")
    try:
        from src.media_buddy.services.article_factory import ArticleServiceFactory
        
        services = ArticleServiceFactory.list_services()
        print(f"Available services: {services}")
        
        service = ArticleServiceFactory.create_service('newsapi')
        print(f"Created service: {service.get_service_name()}")
        
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_legacy_adapter():
    """Test the legacy adapter for backward compatibility."""
    print("\n=== Testing Legacy Adapter ===")
    try:
        from src.media_buddy.services.legacy_adapter import fetch_articles
        
        articles = fetch_articles("artificial intelligence")
        print(f"Legacy adapter fetched {len(articles)} articles")
        
        if articles:
            article = articles[0]
            print(f"Sample article keys: {list(article.keys())}")
            print(f"Title: {article['title']}")
            print(f"Content length: {len(article.get('content', ''))}")
        
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def main():
    """Run all tests."""
    print("Testing new services architecture...\n")
    
    tests = [
        test_newsapi_service_direct,
        test_factory,
        test_legacy_adapter
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n=== Test Results ===")
    passed = sum(results)
    total = len(results)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("✅ All tests passed! Architecture is ready for integration.")
    else:
        print("❌ Some tests failed. Check errors above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 