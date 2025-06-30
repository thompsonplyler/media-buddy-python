"""
Collaborative Writing Service for Media Buddy

Handles the collaborative writing workflow where users provide their perspective/take
on news content, and AI enhances it while preserving the user's authentic voice.
"""

import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path
import google.generativeai as genai

logger = logging.getLogger(__name__)

class CollaborativeWritingService:
    """Service for managing collaborative writing workflow."""
    
    def __init__(self):
        """Initialize the collaborative writing service."""
        if not os.getenv('GEMINI_API_KEY'):
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        self.model = genai.GenerativeModel('gemini-1.5-pro-latest')
    
    def create_user_contribution_prompt(self, article_content: str, article_title: str) -> str:
        """
        Create a prompt template for user to contribute their perspective.
        
        Args:
            article_content: Full article content from news source
            article_title: Article title
            
        Returns:
            Formatted prompt template for user input
        """
        prompt_template = f"""# Your Take: {article_title}

## Original Article Summary
{article_content[:500]}...

## Your Perspective
Write your take on this story. This will be expanded by AI while preserving your voice and perspective.

Consider:
- What's your angle on this story?
- What connections do you see to broader themes?
- What's your authentic reaction or insight?
- What would you want people to understand about this?

Your contribution:
"""
        return prompt_template
    
    def enhance_user_contribution(self, 
                                user_contribution: str, 
                                original_article: str,
                                target_length: int = 200,
                                style_context: Optional[str] = None) -> str:
        """
        Enhance user's contribution while preserving their authentic voice.
        
        Args:
            user_contribution: User's original perspective/take
            original_article: Full original article content
            target_length: Target word count for enhanced version
            style_context: Optional style context from previous writings
            
        Returns:
            Enhanced version that expands user's voice
        """
        
        style_instruction = ""
        if style_context:
            style_instruction = f"""
CRITICAL: Maintain this user's established writing style and voice patterns:
{style_context}
"""
        
        prompt = f"""You are a writing enhancement specialist. Your task is to expand and enhance the user's original perspective while ABSOLUTELY PRESERVING their authentic voice, tone, and style.

{style_instruction}

CORE PRINCIPLE: This is NOT rewriting - this is EXPANDING. The user's original voice, opinions, and style must remain completely intact and dominant throughout.

ORIGINAL ARTICLE CONTEXT:
{original_article}

USER'S ORIGINAL CONTRIBUTION:
{user_contribution}

ENHANCEMENT INSTRUCTIONS:
1. Keep the user's exact phrasing, tone, and perspective as the foundation
2. Add supporting details, context, and elaboration that match their voice
3. Expand their insights with additional examples or connections they might make
4. Maintain their emotional tone and attitude throughout
5. Target approximately {target_length} words
6. DO NOT change their conclusions, opinions, or core message
7. DO NOT make it more formal or academic than their original style

Enhanced version that expands their voice:"""

        try:
            response = self.model.generate_content(prompt)
            enhanced_content = response.text.strip()
            
            logger.info(f"Enhanced user contribution from {len(user_contribution.split())} to {len(enhanced_content.split())} words")
            return enhanced_content
            
        except Exception as e:
            logger.error(f"Error enhancing user contribution: {e}")
            # Fallback: return original if enhancement fails
            return user_contribution
    
    def save_contribution(self, article_id: int, user_contribution: str) -> str:
        """
        Save user contribution to file system.
        
        Args:
            article_id: Database ID of the article
            user_contribution: User's written contribution
            
        Returns:
            Path to saved file
        """
        # Create directory structure
        contrib_dir = Path('private') / 'writing_style_samples' / 'input' / str(article_id)
        contrib_dir.mkdir(parents=True, exist_ok=True)
        
        # Save contribution
        contrib_file = contrib_dir / 'user_contribution.txt'
        with open(contrib_file, 'w', encoding='utf-8') as f:
            f.write(user_contribution)
        
        logger.info(f"Saved user contribution to: {contrib_file}")
        return str(contrib_file)
    
    def load_contribution(self, article_id: int) -> Optional[str]:
        """
        Load existing user contribution for an article.
        
        Args:
            article_id: Database ID of the article
            
        Returns:
            User contribution text if exists, None otherwise
        """
        contrib_file = Path('private') / 'writing_style_samples' / 'input' / str(article_id) / 'user_contribution.txt'
        
        if contrib_file.exists():
            with open(contrib_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                logger.info(f"Loaded user contribution from: {contrib_file}")
                return content
        
        return None
    
    def get_style_context(self) -> Optional[str]:
        """
        Extract style context from user's previous writings for consistency.
        
        Returns:
            Style context string or None if no samples available
        """
        # Look for recent style samples
        samples_dir = Path('private') / 'writing_style_samples'
        
        if not samples_dir.exists():
            return None
        
        # Collect recent samples (limit to prevent prompt overflow)
        sample_files = []
        for pattern in ['test/*.md', 'input/*/user_contribution.txt']:
            sample_files.extend(samples_dir.glob(pattern))
        
        # Get most recent 3 samples for style context
        recent_samples = sorted(sample_files, key=lambda x: x.stat().st_mtime, reverse=True)[:3]
        
        if not recent_samples:
            return None
        
        style_context = "USER'S WRITING STYLE PATTERNS:\n"
        for sample_file in recent_samples:
            try:
                with open(sample_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Extract just the writing, not metadata
                    if '---' in content:
                        parts = content.split('---')
                        if len(parts) >= 3:
                            writing = parts[2].strip()
                        else:
                            writing = content
                    else:
                        writing = content
                    
                    # Limit length to prevent prompt overflow
                    if len(writing) > 500:
                        writing = writing[:500] + "..."
                    
                    style_context += f"\nSample: {writing}\n"
            except Exception as e:
                logger.warning(f"Could not read style sample {sample_file}: {e}")
                continue
        
        return style_context if len(style_context) > 50 else None 