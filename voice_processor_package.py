# Voice Processing Package - Extracted from Media Buddy
# This module provides voice adoption and embeddings functionality
# that can be dropped into any Flask project

import os
import logging
import json
from typing import List, Dict, Optional
import google.generativeai as genai
from sentence_transformers import SentenceTransformer
import torch

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] - %(message)s')

class VoiceProcessor:
    """
    A portable voice processing system that can adopt a specific writing style
    and generate embeddings for text similarity.
    """
    
    def __init__(self, 
                 writing_samples_dir: str = "private/writing_style_samples",
                 embedding_model: str = "all-MiniLM-L6-v2",
                 gemini_api_key: Optional[str] = None):
        """
        Initialize the voice processor.
        
        Args:
            writing_samples_dir: Path to directory containing .md writing samples
            embedding_model: SentenceTransformer model name for embeddings
            gemini_api_key: Gemini API key (or will use GEMINI_API_KEY env var)
        """
        self.writing_samples_dir = writing_samples_dir
        self.embedding_model_name = embedding_model
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
        # Initialize Gemini
        api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            self.gemini_model = genai.GenerativeModel('gemini-1.5-pro-latest')
        else:
            raise ValueError("Gemini API key required. Set GEMINI_API_KEY environment variable or pass as parameter.")
        
        # Load embedding model (lazy loading)
        self._embedding_model = None
        self._writing_style_cache = None
        
    @property
    def embedding_model(self):
        """Lazy load the embedding model."""
        if self._embedding_model is None:
            logging.info(f"Loading embedding model: {self.embedding_model_name}")
            self._embedding_model = SentenceTransformer(self.embedding_model_name, device=self.device)
        return self._embedding_model
    
    def get_writing_style_examples(self) -> str:
        """
        Reads all .md files from the writing style samples directory and concatenates them.
        Results are cached for performance.
        """
        if self._writing_style_cache is not None:
            return self._writing_style_cache
            
        if not os.path.isdir(self.writing_samples_dir):
            raise FileNotFoundError(f"Writing style samples directory not found at: {self.writing_samples_dir}")

        all_samples = []
        # sorted() ensures consistent order for prompts
        for filename in sorted(os.listdir(self.writing_samples_dir)):
            if filename.endswith(".md"):
                filepath = os.path.join(self.writing_samples_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    # Add a header to each sample for clarity
                    all_samples.append(f"--- START OF SAMPLE FROM {filename} ---\n\n{f.read()}\n\n--- END OF SAMPLE FROM {filename} ---")

        if not all_samples:
            raise FileNotFoundError(f"No .md writing samples found in {self.writing_samples_dir}")
        
        self._writing_style_cache = "\n\n".join(all_samples)
        return self._writing_style_cache

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generates a vector embedding for a given block of text.

        Args:
            text: The text to embed.

        Returns:
            The embedding vector as a list of floats, or empty list if error occurs.
        """
        try:
            embedding = self.embedding_model.encode(text)
            return embedding.tolist()
        except Exception as e:
            logging.error(f"Error during embedding generation: {e}")
            return []

    def generate_voiced_text(self, original_text: str, target_length: int = 250) -> str:
        """
        Generates a new version of the text in the specific writing voice 
        based on the writing style samples.

        Args:
            original_text: The text to rewrite in the target voice
            target_length: Target word count for the output

        Returns:
            The text rewritten in the target voice
        """
        if not original_text:
            raise ValueError("Original text cannot be empty.")

        writing_style = self.get_writing_style_examples()

        prompt = f"""
        You are a master of literary impersonation. Your task is to rewrite text in the specific, unique voice of a particular author. I will provide you with a collection of the author's writings to use as a style guide, the original text to be rewritten, and a target word count.

        **CRITICAL INSTRUCTION: Distinguish between STYLE and CONTENT.**
        - **DO** analyze the author's writing style: their tone (e.g., witty, analytical, passionate), sentence structure (e.g., short and punchy, long and flowing), cadence, vocabulary, and their tendency to use personal analogies or historical comparisons.
        - **DO NOT** copy specific, unrelated proper nouns or topics from the style guide. For example, the author may mention "Krispy Kreme" or "Marine Corps drill instructors," but you must **IGNORE** these specific content details and not insert them into the new text unless the text itself is about those topics. Your goal is to write *as if* the author were writing about the *new subject*.

        Your final output must ONLY be the rewritten text. Do not include any preambles, apologies, or explanations.

        **Author's Style Guide (learn the style, ignore the specific content):**
        ---
        {writing_style}
        ---

        **Original Text to Rewrite:**
        ---
        {original_text}
        ---

        **Your Task:**
        Rewrite the "Original Text" in the voice and style of the author from the "Style Guide". The rewritten text should be approximately {target_length} words long. Remember to capture the *how* of the writing, not the *what*.
        """

        try:
            response = self.gemini_model.generate_content(prompt)
            return response.text
        except Exception as e:
            logging.error(f"Error during voice generation: {e}")
            return original_text  # Fallback to original

    def generate_timeline(self, text: str) -> List[Dict]:
        """
        Parses a block of text and divides it into a sequence of scenes for multimedia production.
        Each scene contains both the text content (for voiceover timing) and visual description (for image generation).

        Args:
            text: The voiced text to process into scenes.

        Returns:
            A list of scene dictionaries with text content and visual descriptions.
        """
        try:
            prompt = f"""
            You are an expert AI content analyzer. Your task is to read the following text and break it down into a sequence of scenes for multimedia production. Each scene needs both the actual text content (for voiceover timing) and a visual description (for image generation).

            Your output MUST be a valid JSON array of objects. Do not include any text, markdown, or explanations outside of the JSON block. Each object in the array should represent one scene and have four keys:
            1. "scene": An integer representing the scene number (starting from 1).
            2. "text": The actual text/script content from the original text that corresponds to this scene. This should be the exact words that will be spoken during this visual scene.
            3. "description": A visually rich, concrete description of the scene for image generation.
            4. "is_user_scene": A boolean value (`true` or `false`). Set this to `true` if the scene is clearly describing the author of the text (using "I", "me", "my"). Otherwise, set it to `false`.

            **CRITICAL RULES FOR TEXT SEGMENTATION:**
            - **COMPLETE THOUGHTS:** Each scene should contain complete sentences or thoughts, not fragments.
            - **NATURAL BREAKS:** Break at logical narrative points (topic changes, new subjects, transitions).
            - **SPEAKING PACE:** Aim for 15-25 words per scene (roughly 3-5 seconds of speech at normal pace).
            - **PRESERVE ORIGINAL:** Use the exact words from the original text - don't paraphrase or summarize.

            **CRITICAL RULES FOR DESCRIPTIONS:**
            - **BE VISUAL:** Describe what can be SEEN. Avoid abstract concepts, emotions, or intentions. Instead of "She was sad," write "A single tear rolls down her cheek." Instead of "He was angry," write "His knuckles are white as he clenches his fist."
            - **BE SELF-CONTAINED:** Each description must stand completely on its own. DO NOT use pronouns (he, she, they, it) that refer to subjects in previous scenes. If the same person appears, describe them again (e.g., "A man in a red coat...", "The man in the red coat now walks...").
            - **BE CONCRETE:** Do not describe abstract ideas like "skepticism" or "innovation". Describe the physical manifestation of those ideas.

            Now, please process the following text:
            ---
            {text}
            ---
            """

            response = self.gemini_model.generate_content(prompt)
            
            # Clean the response to ensure it's valid JSON
            clean_response = response.text.strip().replace("```json", "").replace("```", "")
            
            timeline = json.loads(clean_response)
            
            logging.info(f"Successfully generated a timeline with {len(timeline)} scenes.")
            return timeline

        except json.JSONDecodeError as e:
            logging.error(f"Failed to decode JSON from LLM response: {e}")
            logging.error(f"Raw response was: {response.text}")
            return []
        except Exception as e:
            logging.error(f"An error occurred during timeline generation: {e}")
            return []


# Flask CLI integration example
def register_voice_commands(app, voice_processor, db_model_class=None):
    """
    Register Flask CLI commands for voice processing.
    
    Args:
        app: Flask application instance
        voice_processor: VoiceProcessor instance
        db_model_class: Your SQLAlchemy model class (should have 'content' and 'voiced_content' fields)
    """
    import click
    from flask.cli import with_appcontext
    
    @app.cli.command('generate-voice')
    @click.option('--text', required=True, help='Text to convert to target voice')
    @click.option('--length', default=250, help='Target word count')
    def generate_voice_command(text, length):
        """Generate text in the target voice."""
        try:
            voiced_text = voice_processor.generate_voiced_text(text, length)
            click.echo("--- VOICED TEXT ---")
            click.echo(voiced_text)
            click.echo("--- END ---")
        except Exception as e:
            click.echo(f"Error: {e}")
    
    @app.cli.command('generate-embedding')
    @click.option('--text', required=True, help='Text to generate embedding for')
    def generate_embedding_command(text):
        """Generate embedding for text."""
        try:
            embedding = voice_processor.generate_embedding(text)
            click.echo(f"Generated {len(embedding)}-dimensional embedding")
            click.echo(f"First 5 dimensions: {embedding[:5]}")
        except Exception as e:
            click.echo(f"Error: {e}")
    
    if db_model_class:
        @app.cli.command('voice-process-db')
        @click.option('--record-id', required=True, type=int, help='Database record ID to process')
        @click.option('--length', default=250, help='Target word count')
        @with_appcontext
        def voice_process_db_command(record_id, length):
            """Process a database record through voice conversion."""
            try:
                record = db_model_class.query.get(record_id)
                if not record:
                    click.echo(f"Record {record_id} not found")
                    return
                
                # Assuming your model has 'content' and 'voiced_content' fields
                if not hasattr(record, 'content'):
                    click.echo("Model must have 'content' field")
                    return
                    
                voiced_text = voice_processor.generate_voiced_text(record.content, length)
                
                if hasattr(record, 'voiced_content'):
                    record.voiced_content = voiced_text
                    from flask import current_app
                    current_app.extensions['sqlalchemy'].session.commit()
                    click.echo(f"Updated record {record_id} with voiced content")
                else:
                    click.echo("--- VOICED CONTENT ---")
                    click.echo(voiced_text)
                    click.echo("--- END ---")
                    
            except Exception as e:
                click.echo(f"Error: {e}")


# Example usage in a Flask app
"""
from flask import Flask
from voice_processor_package import VoiceProcessor, register_voice_commands

app = Flask(__name__)

# Initialize voice processor
voice_processor = VoiceProcessor(
    writing_samples_dir="path/to/your/writing/samples",
    embedding_model="all-MiniLM-L6-v2"
)

# Register CLI commands
register_voice_commands(app, voice_processor)

# Use in your routes
@app.route('/api/voice-convert', methods=['POST'])
def voice_convert():
    data = request.get_json()
    original_text = data.get('text', '')
    length = data.get('length', 250)
    
    voiced_text = voice_processor.generate_voiced_text(original_text, length)
    embedding = voice_processor.generate_embedding(voiced_text)
    
    return {
        'original_text': original_text,
        'voiced_text': voiced_text,
        'embedding': embedding
    }
""" 