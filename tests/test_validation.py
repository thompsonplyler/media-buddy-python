#!/usr/bin/env python3
"""
Test script to verify enhanced validation works on fresh Google News articles.
Shows step-by-step validation process.
"""

import os
import sys
import logging

# Setup logging to see validation details
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from media_buddy.services.article_factory import ArticleServiceFactory

def test_fresh_validation():
    """Test validation on freshly fetched articles."""
    
    print("=== Testing Fresh Article Validation ===\n")
    
    # Create GoogleNews service
    try:
        service = ArticleServiceFactory.create_service('googlenews')
        print(f"✅ Created service: {service.get_service_name()}\n")
    except Exception as e:
        print(f"❌ Failed to create service: {e}")
        return
    
    # Test query that might hit bot detection
    test_query = "climate change technology"
    max_articles = 8  # Get more to increase chances of hitting different sites
    
    print(f"🔍 Fetching fresh articles for: '{test_query}'")
    print(f"📊 Requesting up to {max_articles} articles")
    print("📝 Watch for validation logs below...\n")
    print("-" * 80)
    
    try:
        # This will show all the validation logic in action
        articles = service.fetch_articles(test_query, max_articles)
        
        print("-" * 80)
        print(f"\n🎯 FINAL RESULTS:")
        print(f"✅ {len(articles)} articles passed validation\n")
        
        # Show details of articles that made it through
        for i, article in enumerate(articles, 1):
            print(f"Article {i}:")
            print(f"  📰 Title: {article.title[:60]}...")
            print(f"  🔗 URL: {article.url}")
            print(f"  📝 Content length: {len(article.content)} chars")
            print(f"  🔍 Preview: {article.content[:100].replace(chr(10), ' ')}...")
            print()
        
        # Validation success rate
        if len(articles) > 0:
            print(f"🎉 SUCCESS: Validation working! Got {len(articles)} quality articles")
            print("🔍 Check the logs above to see which articles were rejected and why")
        else:
            print("⚠️  WARNING: No articles passed validation")
            print("This could mean:")
            print("  - All sites hit bot detection")
            print("  - Validation criteria too strict") 
            print("  - Network/scraping issues")
            
    except Exception as e:
        print(f"❌ Error during fetch: {e}")
        return

if __name__ == "__main__":
    test_fresh_validation() 