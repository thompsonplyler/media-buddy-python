"""
Image extraction from news articles.
Placeholder for future enhancement - currently just logs potential images.
"""

import logging
import re
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

def extract_article_images(article_url: str, article_content: str) -> List[Dict]:
    """
    Extract images from article content for future use.
    Currently just identifies potential images - doesn't download.
    
    Args:
        article_url: URL of the article (for resolving relative URLs)
        article_content: Raw HTML or text content of the article
        
    Returns:
        List of image metadata dictionaries
    """
    images = []
    
    try:
        # Try to parse as HTML to find img tags
        soup = BeautifulSoup(article_content, 'html.parser')
        img_tags = soup.find_all('img')
        
        for img in img_tags:
            src = img.get('src')
            if not src:
                continue
                
            # Resolve relative URLs
            if src.startswith('//'):
                src = 'https:' + src
            elif src.startswith('/'):
                src = urljoin(article_url, src)
            elif not src.startswith('http'):
                src = urljoin(article_url, src)
            
            # Extract metadata
            image_info = {
                'url': src,
                'alt': img.get('alt', ''),
                'title': img.get('title', ''),
                'width': img.get('width'),
                'height': img.get('height'),
                'class': img.get('class', []),
                'type': 'article_image'
            }
            
            # Skip obvious non-content images
            classes = ' '.join(image_info['class']).lower()
            if any(skip in classes for skip in ['logo', 'icon', 'avatar', 'button', 'social']):
                continue
                
            # Skip tiny images (likely icons/spacers)
            try:
                if image_info['width'] and int(image_info['width']) < 100:
                    continue
                if image_info['height'] and int(image_info['height']) < 100:
                    continue
            except (ValueError, TypeError):
                pass
            
            images.append(image_info)
            
    except Exception as e:
        logging.debug(f"Could not parse HTML for images: {e}")
    
    # Also look for image URLs in text content
    url_pattern = r'https?://[^\s]+\.(?:jpg|jpeg|png|gif|webp|svg)(?:\?[^\s]*)?'
    text_image_urls = re.findall(url_pattern, article_content, re.IGNORECASE)
    
    for url in text_image_urls:
        # Skip if we already found this image
        if any(img['url'] == url for img in images):
            continue
            
        images.append({
            'url': url,
            'alt': '',
            'title': '',
            'width': None,
            'height': None,
            'class': [],
            'type': 'text_extracted'
        })
    
    # Log what we found for future reference
    if images:
        logging.info(f"Found {len(images)} potential images in article")
        for i, img in enumerate(images[:3]):  # Show first 3
            logging.debug(f"  Image {i+1}: {img['url']}")
    else:
        logging.debug("No images found in article content")
    
    return images

def get_article_featured_image(article_url: str, article_content: str) -> Optional[Dict]:
    """
    Try to identify the main/featured image for an article.
    
    Args:
        article_url: URL of the article
        article_content: Article content
        
    Returns:
        Dictionary with featured image info, or None
    """
    images = extract_article_images(article_url, article_content)
    
    if not images:
        return None
    
    # Score images to find the most likely featured image
    for img in images:
        score = 0
        classes = ' '.join(img['class']).lower()
        
        # Higher score for featured/hero/main classes
        if any(keyword in classes for keyword in ['featured', 'hero', 'main', 'lead']):
            score += 10
            
        # Higher score for larger images
        try:
            if img['width'] and int(img['width']) > 400:
                score += 5
            if img['height'] and int(img['height']) > 200:
                score += 3
        except (ValueError, TypeError):
            pass
        
        # Higher score for descriptive alt text
        if img['alt'] and len(img['alt']) > 10:
            score += 2
            
        img['feature_score'] = score
    
    # Return highest scoring image
    featured = max(images, key=lambda x: x.get('feature_score', 0))
    logging.info(f"Selected featured image (score: {featured.get('feature_score', 0)}): {featured['url']}")
    
    return featured

# Placeholder for future image downloading/processing
def download_article_image(image_url: str, save_path: str) -> bool:
    """
    Placeholder for downloading images from articles.
    Currently just logs the intent.
    
    Args:
        image_url: URL of image to download
        save_path: Where to save the image
        
    Returns:
        True if successful (currently always False as it's a placeholder)
    """
    logging.info(f"PLACEHOLDER: Would download {image_url} to {save_path}")
    return False 