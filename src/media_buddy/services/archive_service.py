import logging
import asyncio
from typing import List, Optional
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re
import time
from .article_service import ArticleService, Article, ArticleFetchError

class ArchiveService(ArticleService):
    """Archive.is implementation for fetching full article content when direct scraping fails."""
    
    def __init__(self):
        # Common selectors for article content (same as GoogleNewsService for consistency)
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
        
        # Archive.is URL patterns to try
        self.archive_patterns = [
            "https://archive.is/newest/{url}",
            "https://archive.today/newest/{url}",
            "https://web.archive.org/web/{url}"  # Wayback as fallback
        ]
    
    def get_service_name(self) -> str:
        return "Archive.is+Playwright"
    
    def fetch_articles(self, query: str, max_articles: int = 10, **kwargs) -> List[Article]:
        """
        Archive service doesn't search - it takes URLs from kwargs.
        
        Args:
            query: Not used in archive service (kept for interface compatibility)
            max_articles: Maximum number of articles to return
            **kwargs: Must contain 'urls' key with list of URLs to archive
        """
        urls = kwargs.get('urls', [])
        if not urls:
            raise ArticleFetchError("Archive service requires 'urls' parameter with list of URLs")
        
        logging.info(f"Archive service fetching {len(urls)} URLs through archive.is")
        
        try:
            articles = asyncio.run(self._fetch_archived_content(urls[:max_articles]))
            
            # Validate articles
            valid_articles = []
            for article in articles:
                if self.validate_article(article):
                    valid_articles.append(article)
                    logging.info(f"✅ Archive success: {article.title} ({len(article.content)} chars)")
                else:
                    logging.warning(f"❌ Archive validation failed: {article.title}")
            
            logging.info(f"Archive service successfully retrieved {len(valid_articles)}/{len(urls)} articles")
            return valid_articles
            
        except Exception as e:
            raise ArticleFetchError(f"Error fetching from Archive.is: {e}")
    
    async def _fetch_archived_content(self, urls: List[str]) -> List[Article]:
        """Fetch full article content from archive.is for each URL."""
        articles = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            
            for url in urls:
                logging.info(f"🏛️  Attempting to fetch archived version of: {url}")
                article = await self._fetch_single_archived_article(context, url)
                if article:
                    articles.append(article)
                else:
                    logging.error(f"❌ Failed to retrieve archived version of: {url}")
                
                # Be respectful with requests
                await asyncio.sleep(2)
            
            await browser.close()
        
        return articles
    
    async def _fetch_single_archived_article(self, context, original_url: str) -> Optional[Article]:
        """Try to fetch a single article from various archive services."""
        
        for pattern in self.archive_patterns:
            archive_url = pattern.format(url=original_url)
            logging.info(f"🔍 Trying archive URL: {archive_url}")
            
            try:
                page = await context.new_page()
                
                # Navigate to archive URL
                logging.info(f"📡 Navigating to: {archive_url}")
                response = await page.goto(archive_url, wait_until='domcontentloaded', timeout=15000)
                
                if not response or response.status != 200:
                    logging.warning(f"⚠️  Archive returned status {response.status if response else 'None'}")
                    await page.close()
                    continue
                
                # Wait for content to load
                await page.wait_for_timeout(3000)
                
                # Check if we actually got to the archived page (not an error page)
                page_content = await page.content()
                if self._is_archive_error_page(page_content, archive_url):
                    logging.warning(f"⚠️  Archive error page detected for: {archive_url}")
                    await page.close()
                    continue
                
                # Extract article metadata
                title = await self._extract_title(page)
                if not title:
                    logging.warning(f"⚠️  Could not extract title from: {archive_url}")
                    await page.close()
                    continue
                
                # Extract main content
                content = await self._extract_content_from_page(page)
                if not content or len(content.strip()) < 500:
                    logging.warning(f"⚠️  Insufficient content extracted from: {archive_url} ({len(content) if content else 0} chars)")
                    await page.close()
                    continue
                
                # Success! Create article object
                article = Article(
                    url=original_url,  # Use original URL, not archive URL
                    title=title,
                    content=content,
                    source=self._extract_source_from_url(original_url),
                    published_at=None,  # Archive doesn't preserve this reliably
                    author=None
                )
                
                logging.info(f"✅ Successfully extracted from archive: {title} ({len(content)} chars)")
                await page.close()
                return article
                
            except Exception as e:
                logging.error(f"❌ Error processing {archive_url}: {e}")
                try:
                    await page.close()
                except:
                    pass
                continue
        
        logging.error(f"❌ All archive attempts failed for: {original_url}")
        return None
    
    def _is_archive_error_page(self, page_content: str, archive_url: str) -> bool:
        """Check if we got an archive error page instead of the actual content."""
        error_indicators = [
            "page not found",
            "not archived",
            "no archives",
            "404 not found",
            "this url has not been archived",
            "wayback machine hasn't archived that url"
        ]
        
        content_lower = page_content.lower()
        for indicator in error_indicators:
            if indicator in content_lower:
                return True
        
        # Also check if the page is suspiciously short (likely an error)
        if len(page_content.strip()) < 1000:
            return True
        
        return False
    
    async def _extract_title(self, page) -> Optional[str]:
        """Extract article title from the page."""
        title_selectors = [
            'h1',
            'title',
            '.headline',
            '.article-title',
            '[data-testid="headline"]'
        ]
        
        for selector in title_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    title = await element.inner_text()
                    if title and len(title.strip()) > 5:
                        return title.strip()
            except:
                continue
        
        return None
    
    async def _extract_content_from_page(self, page) -> str:
        """Extract main article content from the archived page."""
        
        # Strategy 1: Try specific content selectors
        for selector in self.content_selectors:
            try:
                elements = await page.query_selector_all(selector)
                if elements:
                    content_parts = []
                    for element in elements:
                        text = await element.inner_text()
                        if text and len(text.strip()) > 50:
                            content_parts.append(text.strip())
                    
                    if content_parts:
                        content = '\n\n'.join(content_parts)
                        content = self._clean_extracted_content(content)
                        if len(content) > 500:
                            logging.debug(f"✅ Content extracted using selector: {selector}")
                            return content
            except Exception as e:
                logging.debug(f"Selector {selector} failed: {e}")
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
                content = self._clean_extracted_content(content)
                logging.debug("✅ Content extracted using paragraph fallback")
                return content
        except Exception as e:
            logging.debug(f"Paragraph extraction failed: {e}")
        
        # Strategy 3: Last resort - get body text
        try:
            body_text = await page.locator('body').inner_text()
            content = self._clean_extracted_content(body_text)
            logging.debug("✅ Content extracted using body text fallback")
            return content
        except Exception as e:
            logging.debug(f"Body text extraction failed: {e}")
        
        return ""
    
    def _clean_extracted_content(self, content: str) -> str:
        """Clean up extracted content by removing archive and website clutter."""
        if not content:
            return ""
        
        # Remove excessive whitespace
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        content = re.sub(r'[ \t]+', ' ', content)
        
        # Remove archive-specific clutter
        archive_patterns = [
            r'Archived from.*?on.*?\d{4}',
            r'Archive\.is.*?snapshot',
            r'This page was archived.*?\d{4}',
            r'Wayback Machine.*?archived',
            r'Internet Archive.*?snapshot'
        ]
        
        for pattern in archive_patterns:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE)
        
        # Remove common website navigation/footer text patterns (same as GoogleNewsService)
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
            if len(line) > 10:
                cleaned_lines.append(line)
        
        return '\n\n'.join(cleaned_lines).strip()
    
    def _extract_source_from_url(self, url: str) -> str:
        """Extract source name from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Remove www. if present
            if domain.startswith('www.'):
                domain = domain[4:]
            
            # Map common domains to readable names
            domain_mapping = {
                'npr.org': 'NPR',
                'bbc.com': 'BBC',
                'bbc.co.uk': 'BBC',
                'reuters.com': 'Reuters',
                'ap.org': 'Associated Press',
                'apnews.com': 'Associated Press',
                'cnn.com': 'CNN',
                'nytimes.com': 'New York Times',
                'washingtonpost.com': 'Washington Post',
                'wsj.com': 'Wall Street Journal'
            }
            
            return domain_mapping.get(domain, domain.title())
        except:
            return 'Unknown'
    
    def validate_article(self, article: Article) -> bool:
        """Enhanced validation for archived articles."""
        if not article.url or not article.title:
            logging.warning(f"Article missing URL or title")
            return False
            
        if not article.content or len(article.content.strip()) < 500:
            logging.warning(f"Article '{article.title}' has insufficient content ({len(article.content)} chars)")
            return False
        
        # Check for archive-specific error patterns
        content_lower = article.content.lower()
        archive_error_phrases = [
            "page not found",
            "not archived",
            "404 error",
            "access denied",
            "this url has not been archived"
        ]
        
        for phrase in archive_error_phrases:
            if phrase in content_lower:
                logging.warning(f"Article '{article.title}' appears to be an archive error page")
                return False
        
        # Check for good content indicators
        good_indicators = ["published", "author", "reporter", "story", "news", "said", "according to", "breaking"]
        has_good_indicators = any(indicator in content_lower for indicator in good_indicators)
        
        if len(article.content) > 2000:
            logging.info(f"Article '{article.title}' passed validation (long content: {len(article.content)} chars)")
            return True
            
        if not has_good_indicators and len(article.content) < 1500:
            logging.warning(f"Article '{article.title}' lacks typical news content indicators")
            return False
            
        logging.info(f"Article '{article.title}' passed validation ({len(article.content)} chars)")
        return True 