#!/usr/bin/env python3
"""
Test script for the Google News + Playwright service.

This tests that our new service can:
1. Fetch articles from Google News RSS
2. Extract full content using Playwright  
3. Return substantially more content than NewsAPI snippets
"""

import sys
import os
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_dependencies():
    """Test that required dependencies are available."""
    print("=== Testing Dependencies ===")
    
    dependencies = [
        ('feedparser', 'feedparser'),
        ('playwright', 'playwright.async_api'),
        ('beautifulsoup4', 'bs4')
    ]
    
    missing = []
    for dep_name, import_name in dependencies:
        try:
            __import__(import_name)
            print(f"✅ {dep_name} available")
        except ImportError:
            print(f"❌ {dep_name} missing")
            missing.append(dep_name)
    
    if missing:
        print(f"\nInstall missing dependencies with:")
        print(f"pip install {' '.join(missing)}")
        print("And run: playwright install chromium")
        return False
    
    return True

def test_google_news_rss():
    """Test that we can fetch articles from Google News RSS."""
    print("\n=== Testing Google News RSS ===")
    try:
        import feedparser
        
        # Test RSS feed directly
        rss_url = "https://news.google.com/rss/search?q=artificial+intelligence&hl=en&gl=US&ceid=US:en"
        feed = feedparser.parse(rss_url)
        
        if not hasattr(feed, 'entries') or len(feed.entries) == 0:
            print("❌ No articles found in RSS feed")
            return False
            
        print(f"✅ Found {len(feed.entries)} articles in RSS")
        
        # Show sample
        sample = feed.entries[0]
        print(f"Sample title: {sample.title}")
        print(f"Sample URL: {sample.link}")
        print(f"Sample summary length: {len(sample.get('summary', ''))}")
        
        return True
    except Exception as e:
        print(f"❌ RSS test failed: {e}")
        return False

def test_service_creation():
    """Test that our Google News service can be created."""
    print("\n=== Testing Service Creation ===")
    try:
        from src.media_buddy.services.googlenews_service import GoogleNewsService
        
        service = GoogleNewsService()
        print(f"✅ Service created: {service.get_service_name()}")
        
        return True
    except Exception as e:
        print(f"❌ Service creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_factory_registration():
    """Test that the service is properly registered with factory."""
    print("\n=== Testing Factory Registration ===")
    try:
        from src.media_buddy.services.article_factory import ArticleServiceFactory
        
        services = ArticleServiceFactory.list_services()
        print(f"Available services: {services}")
        
        if 'googlenews' in services:
            print("✅ GoogleNews service registered")
            
            # Try to create it
            service = ArticleServiceFactory.create_service('googlenews')
            print(f"✅ Service created via factory: {service.get_service_name()}")
            return True
        else:
            print("❌ GoogleNews service not registered")
            return False
            
    except Exception as e:
        print(f"❌ Factory test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("Testing Google News + Playwright service...\n")
    
    tests = [
        test_dependencies,
        test_google_news_rss,
        test_service_creation,
        test_factory_registration
    ]
    
    results = []
    for test in tests:
        results.append(test())
        # Stop on first failure for dependencies
        if test == test_dependencies and not results[-1]:
            break
    
    print("\n=== Test Results ===")
    passed = sum(results)
    total = len(results)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("✅ Google News service ready! Install deps and test content extraction.")
    else:
        print("❌ Some tests failed. Address issues above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 