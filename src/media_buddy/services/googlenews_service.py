import feedparser
import logging
import asyncio
from typing import List, Optional
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote_plus
import re
from .article_service import ArticleService, Article, ArticleFetchError

class GoogleNewsService(ArticleService):
    """Google News RSS + Playwright implementation for full article content."""
    
    def __init__(self):
        self.google_news_base_url = "https://news.google.com/rss/search"
        # Common selectors for article content - we'll try these in order
        self.content_selectors = [
            'article',
            '[role="main"]',
            '.article-content',
            '.post-content',
            '.entry-content',
            '.content',
            'main',
            # Fallback to paragraphs if specific content areas not found
            'div p, article p, main p'
        ]
        
        # Source reliability ranking (higher = more reliable, 0 = blocked)
        self.source_rankings = {
            # Tier 1: Highest reliability
            'Associated Press': 100, 'AP': 100, 'Reuters': 95, 'BBC': 90,
            
            # Tier 2: High reliability  
            'NPR': 85, 'PBS': 85, 'The Guardian': 80, 'Wall Street Journal': 80,
            'Financial Times': 80, 'The Economist': 80,
            
            # Tier 3: Good reliability
            'New York Times': 75, 'Washington Post': 75, 'CNN': 70,
            'ABC News': 70, 'CBS News': 70, 'NBC News': 70,
            
            # Tier 4: Moderate reliability
            'USA Today': 60, 'Time': 60, 'Newsweek': 60, 'CBS Sports': 60, 'Sports Illustrated': 60, 'Yahoo Sports': 60,
            
            # Tier 5: Lower priority but not blocked
            'Daily Mail': 40, 'New York Post': 40, 'Fox News': 30, 'Entertainment Weekly': 30,
            
            # Tier 0: Blocked sources
            'RT': 0, 'Sputnik': 0, 'Breitbart': 0
        }
        
        # Minimum reliability score to include (set to 0 to allow all non-blocked)
        self.min_reliability_score = 25
    
    def get_service_name(self) -> str:
        return "GoogleNews+Playwright"
    
    def fetch_articles(self, query: str, max_articles: int = 10, **kwargs) -> List[Article]:
        """
        Fetch articles from Google News RSS and extract full content with Playwright.
        
        Args:
            query: Search term for articles
            max_articles: Maximum number of articles to return
            **kwargs: Additional parameters (language, etc.)
        """
        try:
            # Step 1: Get URLs from Google News RSS
            rss_urls = self._fetch_google_news_urls(query, max_articles, **kwargs)
            if not rss_urls:
                logging.warning(f"No RSS URLs found for query: {query}")
                return []
            
            # Step 2: Extract full content using Playwright
            articles = asyncio.run(self._extract_full_content(rss_urls))
            
            # Step 3: Validate and filter articles
            valid_articles = []
            for article in articles:
                if self.validate_article(article):
                    valid_articles.append(article)
                else:
                    logging.debug(f"Skipping invalid article: {article.title}")
            
            logging.info(f"Successfully fetched {len(valid_articles)} valid articles from Google News")
            return valid_articles[:max_articles]
            
        except Exception as e:
            raise ArticleFetchError(f"Error fetching from Google News: {e}")
    
    def _fetch_google_news_urls(self, query: str, max_articles: int, **kwargs) -> List[dict]:
        """Fetch article URLs and metadata from Google News RSS."""
        params = {
            'q': quote_plus(query),  # URL encode the query
            'hl': kwargs.get('language', 'en'),
            'gl': kwargs.get('country', 'US'),
            'ceid': f"{kwargs.get('country', 'US')}:{kwargs.get('language', 'en')}"
        }
        
        # Build RSS URL
        param_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        rss_url = f"{self.google_news_base_url}?{param_string}"
        
        logging.info(f"Fetching RSS from Google News: {query}")
        logging.debug(f"RSS URL: {rss_url}")
        
        try:
            # Add headers to look like a legitimate browser request
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/rss+xml, application/xml, text/xml',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate',
                'Cache-Control': 'no-cache'
            }
            
            feed = feedparser.parse(rss_url, request_headers=headers)
            
            # feedparser automatically follows redirects, but let's be more permissive about status codes
            if hasattr(feed, 'status') and feed.status not in [200, 301, 302]:
                raise ArticleFetchError(f"RSS feed returned status {feed.status}")
            
            # Check if we actually got content
            if not hasattr(feed, 'entries'):
                raise ArticleFetchError("No entries found in RSS feed response")
            
            if len(feed.entries) == 0:
                logging.warning("RSS feed returned 0 entries")
                return []
            
            articles_data = []
            filtered_count = 0
            
            for entry in feed.entries[:max_articles * 3]:  # Get more since we're filtering
                source_name = entry.get('source', {}).get('title', '')
                
                # Check source reliability
                reliability_score = self._get_source_reliability(source_name)
                if reliability_score < self.min_reliability_score:
                    logging.info(f"Filtered out article from '{source_name}' (reliability: {reliability_score})")
                    filtered_count += 1
                    continue
                
                articles_data.append({
                    'url': entry.link,
                    'title': entry.title,
                    'published': entry.get('published', ''),
                    'source': source_name,
                    'summary': entry.get('summary', ''),
                    'reliability_score': reliability_score
                })
            
            # Sort by reliability score (highest first)
            articles_data.sort(key=lambda x: x['reliability_score'], reverse=True)
            
            logging.info(f"Found {len(articles_data)} articles from RSS feed (filtered out {filtered_count} unreliable sources)")
            return articles_data[:max_articles * 2]  # Return top articles for scraping
            
        except Exception as e:
            raise ArticleFetchError(f"Error parsing RSS feed: {e}")
    
    async def _extract_full_content(self, rss_articles: List[dict]) -> List[Article]:
        """Extract full article content using Playwright."""
        articles = []
        
        async with async_playwright() as p:
            # Use headless browser for scraping
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            
            for article_data in rss_articles:
                try:
                    page = await context.new_page()
                    
                    # Navigate to article
                    await page.goto(article_data['url'], wait_until='domcontentloaded', timeout=10000)
                    
                    # Wait a bit for dynamic content to load
                    await page.wait_for_timeout(2000)
                    
                    # Extract content using multiple strategies
                    content = await self._extract_content_from_page(page)
                    
                    if content and len(content.strip()) > 200:  # Ensure we got substantial content
                        article = Article(
                            url=article_data['url'],
                            title=article_data['title'],
                            content=content,
                            source=article_data.get('source'),
                            published_at=article_data.get('published'),
                            author=None  # Could extract this later if needed
                        )
                        articles.append(article)
                        logging.debug(f"Extracted {len(content)} chars from: {article_data['title']}")
                    else:
                        logging.warning(f"Insufficient content extracted from: {article_data['url']}")
                    
                    await page.close()
                    
                except Exception as e:
                    logging.error(f"Error extracting content from {article_data['url']}: {e}")
                    # Continue with other articles even if one fails
                    continue
            
            await browser.close()
        
        return articles
    
    async def _extract_content_from_page(self, page) -> str:
        """Extract main article content from the page using multiple strategies."""
        
        # Strategy 1: Try specific content selectors
        for selector in self.content_selectors:
            try:
                elements = await page.query_selector_all(selector)
                if elements:
                    content_parts = []
                    for element in elements:
                        text = await element.inner_text()
                        if text and len(text.strip()) > 50:  # Only substantial text blocks
                            content_parts.append(text.strip())
                    
                    if content_parts:
                        content = '\n\n'.join(content_parts)
                        # Clean up the content
                        content = self._clean_extracted_content(content)
                        if len(content) > 500:  # Good substantial content
                            return content
            except Exception:
                continue
        
        # Strategy 2: Fallback - get all paragraph text
        try:
            paragraphs = await page.query_selector_all('p')
            paragraph_texts = []
            for p in paragraphs:
                text = await p.inner_text()
                if text and len(text.strip()) > 30:
                    paragraph_texts.append(text.strip())
            
            if paragraph_texts:
                content = '\n\n'.join(paragraph_texts)
                return self._clean_extracted_content(content)
        except Exception:
            pass
        
        # Strategy 3: Last resort - get all text content
        try:
            body_text = await page.locator('body').inner_text()
            return self._clean_extracted_content(body_text)
        except Exception:
            return ""
    
    def _clean_extracted_content(self, content: str) -> str:
        """Clean up extracted content by removing common website clutter."""
        if not content:
            return ""
        
        # Remove excessive whitespace
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        content = re.sub(r'[ \t]+', ' ', content)
        
        # Remove common website navigation/footer text patterns
        patterns_to_remove = [
            r'Sign up for.*?newsletter',
            r'Subscribe to.*?for',
            r'Follow us on.*?social media',
            r'Share this.*?article',
            r'Advertisement\s*',
            r'Related Articles?.*',
            r'More from.*?section',
            r'Copyright.*?\d{4}',
            r'All rights reserved',
            r'Terms of Service',
            r'Privacy Policy',
        ]
        
        for pattern in patterns_to_remove:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE)
        
        # Remove very short lines that are likely navigation
        lines = content.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if len(line) > 10:  # Keep substantial lines
                cleaned_lines.append(line)
        
        return '\n\n'.join(cleaned_lines).strip()
    
    def validate_article(self, article: Article) -> bool:
        """
        Enhanced validation to detect bot detection pages and ensure quality content.
        
        Args:
            article: Article to validate
            
        Returns:
            True if article is valid, False otherwise
        """
        if not article.url or not article.title:
            return False
            
        if not article.content or len(article.content.strip()) < 500:
            logging.warning(f"Article '{article.title}' has insufficient content ({len(article.content)} chars)")
            return False
        
        # Check for bot detection patterns
        content_lower = article.content.lower()
        bot_detection_phrases = [
            "please verify you are human",
            "confirm that you're human", 
            "not a robot",
            "please click",
            "captcha",
            "verification required",
            "unusual traffic",
            "suspicious activity",
            "please complete",
            "security check",
            "verify your identity",
            "access denied",
            "403 forbidden",
            "blocked by",
            "enable javascript",
            "turn off your ad blocker"
        ]
        
        for phrase in bot_detection_phrases:
            if phrase in content_lower:
                logging.warning(f"Article '{article.title}' appears to be a bot detection page (contains: '{phrase}')")
                return False
        
        # Check for actual article indicators - good signs
        good_indicators = ["published", "author", "reporter", "story", "news", "said", "according to", "breaking", "today", "yesterday"]
        has_good_indicators = any(indicator in content_lower for indicator in good_indicators)
        
        # If content is long enough, we don't need indicators
        if len(article.content) > 2000:
            logging.info(f"Article '{article.title}' passed validation (long content: {len(article.content)} chars)")
            return True
            
        # For shorter content, we need good indicators
        if not has_good_indicators and len(article.content) < 1500:
            logging.warning(f"Article '{article.title}' lacks typical news content indicators")
            return False
            
        logging.info(f"Article '{article.title}' passed validation ({len(article.content)} chars)")
        return True
    
    def _get_source_reliability(self, source_name: str) -> int:
        """
        Get reliability score for a news source.
        
        Args:
            source_name: Name of the news source
            
        Returns:
            Reliability score (0-100, where 0 means blocked)
        """
        if not source_name:
            return 50  # Default for unknown sources
        
        # Check exact match first
        if source_name in self.source_rankings:
            return self.source_rankings[source_name]
        
        # Check partial matches (case insensitive)
        source_lower = source_name.lower()
        for known_source, score in self.source_rankings.items():
            if known_source.lower() in source_lower or source_lower in known_source.lower():
                logging.debug(f"Matched '{source_name}' to '{known_source}' (score: {score})")
                return score
        
        # Default score for unknown sources
        logging.debug(f"Unknown source '{source_name}', using default score: 50")
        return 50 