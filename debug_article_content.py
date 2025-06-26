#!/usr/bin/env python3
"""
Debug script to check what content was actually extracted from articles.
"""

import sys
import os
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_recent_articles():
    """Check the content length of recently fetched articles."""
    print("=== Checking Recent Article Content ===")
    
    try:
        from src.media_buddy.extensions import db
        from src.media_buddy.models import NewsArticle
        from src.media_buddy import create_app
        
        app = create_app()
        
        with app.app_context():
            # Get the most recent articles
            recent_articles = NewsArticle.query.order_by(NewsArticle.id.desc()).limit(5).all()
            
            if not recent_articles:
                print("No articles found in database")
                return
            
            print(f"Found {len(recent_articles)} recent articles:")
            print("-" * 80)
            
            for i, article in enumerate(recent_articles, 1):
                print(f"\nArticle {i}:")
                print(f"  ID: {article.id}")
                print(f"  Title: {article.title[:60]}...")
                print(f"  URL: {article.url}")
                print(f"  Raw content length: {len(article.raw_content)} chars")
                print(f"  Content preview: {repr(article.raw_content[:100])}")
                
                if len(article.raw_content) < 500:
                    print(f"  ⚠️  PROBLEM: Content too short!")
                else:
                    print(f"  ✅ Content looks substantial")
                
                print("-" * 40)
    
    except Exception as e:
        print(f"Error checking articles: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_recent_articles() 