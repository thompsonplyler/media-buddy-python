#!/usr/bin/env python3
"""
Test script to verify source filtering and prioritization in GoogleNews service.
"""

import os
import sys
import logging

# Setup logging to see filtering details
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from media_buddy.services.article_factory import ArticleServiceFactory

def test_source_filtering():
    """Test source filtering and prioritization."""
    
    print("=== Testing Source Filtering & Priority System ===\n")
    
    # Create GoogleNews service
    try:
        service = ArticleServiceFactory.create_service('googlenews')
        print(f"✅ Created service: {service.get_service_name()}\n")
        
        # Show source rankings
        print("📊 Source Reliability Rankings:")
        for source, score in sorted(service.source_rankings.items(), key=lambda x: x[1], reverse=True):
            status = "🚫 BLOCKED" if score == 0 else f"⭐ {score}/100"
            print(f"  {source}: {status}")
        print(f"\n🎯 Minimum reliability threshold: {service.min_reliability_score}\n")
        
    except Exception as e:
        print(f"❌ Failed to create service: {e}")
        return
    
    # Test with a query that should return diverse sources
    test_query = "breaking news today"
    max_articles = 10
    
    print(f"🔍 Testing source filtering with query: '{test_query}'")
    print("📝 Watch for source filtering logs...\n")
    print("-" * 80)
    
    try:
        articles = service.fetch_articles(test_query, max_articles)
        
        print("-" * 80)
        print(f"\n🎯 RESULTS:")
        print(f"✅ {len(articles)} articles passed all filters\n")
        
        # Show which sources made it through
        sources_found = {}
        for article in articles:
            source = article.source or "Unknown"
            sources_found[source] = sources_found.get(source, 0) + 1
        
        print("📰 Sources that made it through:")
        for source, count in sorted(sources_found.items(), key=lambda x: x[1], reverse=True):
            score = service._get_source_reliability(source)
            print(f"  {source}: {count} article(s) (reliability: {score}/100)")
        
        print(f"\n📊 Source diversity: {len(sources_found)} different sources")
        print("🔍 Check logs above to see which sources were filtered out")
        
        if len(articles) > 0:
            print(f"\n📄 Sample article from top source:")
            top_article = articles[0]
            print(f"  Title: {top_article.title[:60]}...")
            print(f"  Source: {top_article.source}")
            print(f"  Content: {len(top_article.content)} chars")
            print(f"  URL: {top_article.url}")
        
    except Exception as e:
        print(f"❌ Error during fetch: {e}")
        return

if __name__ == "__main__":
    test_source_filtering() 