import logging
import os
import json
from huggingface_hub import login
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
from sentence_transformers import SentenceTransformer
import torch
import google.generativeai as genai
from .models import NewsArticle
from .config import USER, USER_PROMPT
from typing import List, Dict, Optional

# --- Hugging Face Authentication ---
# Check for the API key in the environment and log in if it exists.
hf_token = os.environ.get("HF_API_KEY")
if hf_token:
    print("Found Hugging Face API key. Logging in...")
    login(token=hf_token)
else:
    print("Hugging Face API key not found. Proceeding without authentication.")

# --- Device Configuration ---
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"Device set to use {device}")

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] - %(message)s')

# --- Model Loading ---
# We use a singleton pattern to ensure models are loaded only once.
_models = {}

def get_model(model_name_or_path, task):
    """
    Loads a model from Hugging Face and caches it.
    """
    if model_name_or_path not in _models:
        logging.info(f"Loading model for {task}: '{model_name_or_path}'...")
        try:
            if task == 'summarization':
                tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)
                model = AutoModelForSeq2SeqLM.from_pretrained(model_name_or_path)
                _models[model_name_or_path] = pipeline(task, model=model, tokenizer=tokenizer, device=device)
            elif task == 'sentence-similarity':
                 _models[model_name_or_path] = SentenceTransformer(model_name_or_path, device=device)
            else:
                _models[model_name_or_path] = pipeline(task, model=model_name_or_path, device=device)
            logging.info(f"Model '{model_name_or_path}' loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to load model '{model_name_or_path}': {e}")
            return None
    return _models[model_name_or_path]

# --- Public Functions ---

def generate_summary(text: str, model_name: str = "facebook/bart-large-cnn") -> str:
    """
    Generates a summary for a given block of text.
    
    Args:
        text (str): The text to summarize.
        model_name (str): The name of the summarization model to use.

    Returns:
        str: The generated summary, or an empty string if an error occurs.
    """
    try:
        summarizer = get_model(model_name, 'summarization')
        if not summarizer:
            return ""
            
        # The default BART model has a max length of 1024 tokens. We'll truncate.
        summary = summarizer(text, max_length=150, min_length=40, do_sample=False)
        return summary[0]['summary_text']
    except Exception as e:
        logging.error(f"Error during summarization: {e}")
        return ""

def generate_embedding(text: str, model_name: str = "all-MiniLM-L6-v2") -> list[float]:
    """
    Generates a vector embedding for a given block of text.

    Args:
        text (str): The text to embed.
        model_name (str): The name of the sentence-transformer model to use.

    Returns:
        list[float]: The embedding vector, or an empty list if an error occurs.
    """
    try:
        model = get_model(model_name, 'sentence-similarity')
        if not model:
            return []
            
        embedding = model.encode(text)
        return embedding.tolist()
    except Exception as e:
        logging.error(f"Error during embedding generation: {e}")
        return []

def generate_timeline(text: str) -> list[dict]:
    """
    Parses a block of text and divides it into a sequence of scenes for multimedia production.
    Each scene contains both the text content (for voiceover timing) and visual description (for image generation).

    Args:
        text (str): The voiced summary or enhanced content to process.

    Returns:
        list[dict]: A list of scene dictionaries with text and visual information, e.g.,
                    [{"scene": 1, "text": "The CEO felt the pressure.", "description": "A man at a desk with his head in his hands.", "is_user_scene": false, "image_prompt": "photorealistic cinematic photo of A man at a desk with his head in his hands, dynamic camera angle, shot by FujifilmXT, 85mm, f/2.2"},
                     {"scene": 2, "text": "I decided to take action.", "description": "A person walking confidently down a hallway.", "is_user_scene": true, "image_prompt": "photorealistic cinematic photo of thmpsnplylr, a white man in his mid-40s with messy brown hair A person walking confidently down a hallway, dynamic camera angle, shot by FujifilmXT, 85mm, f/2.2"}]
    """
    
    try:
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-pro-latest')

        prompt = f"""
        You are creating a visual timeline for multimedia production. Divide the text into short, meaningful scenes (15-25 words each) suitable for voiceover timing.

        Your output MUST be a valid JSON array of scene objects with these keys:
        1. "scene": Scene number (integer)
        2. "text": The exact text from the original that corresponds to this scene
        3. "description": T5-style natural language description optimized for Flux image generation
        4. "is_user_scene": Boolean (true if using "I", "me", "my")
        5. "duration_seconds": Estimated duration based on word count
        6. "word_count": Number of words in the text

        **SEGMENTATION RULES:**
        - Aim for 15-25 words per scene (approximately 4-7 seconds)
        - Break at natural sentence boundaries when possible
        - Ensure each scene can stand alone visually
        - Preserve speaker perspective throughout each scene

        **VISUAL DESCRIPTION RULES (T5/FLUX OPTIMIZED):**
        - **COMPLETE SENTENCES**: Write as if explaining the scene to a person, not keyword lists
        - **SINGLE SUBJECT FOCUS**: One person, one object, one location per scene
        - **NO COMPOSITES**: Never combine multiple elements (no "A and B", no "while", no "with")
        - **ACTIVE LANGUAGE**: Use verbs to describe actions and interactions
        - **SPECIFIC DETAILS**: Avoid vague terms like "beautiful" - describe what makes it so
        - **NO KEYWORD SPAM**: Don't list adjectives - integrate them into natural sentences

        **EXAMPLES OF GOOD T5/FLUX DESCRIPTIONS:**
        ✅ "A middle-aged businessman sits at his desk, rubbing his temples with both hands in frustration."
        ✅ "A red arrow points sharply downward on a stock market graph displayed on a computer screen."
        ✅ "An empty boardroom table reflects the overhead fluorescent lighting in a corporate office."
        ✅ "A person walks alone down a rain-soaked city street at night under dim streetlights."

        **EXAMPLES OF BAD KEYWORD-STYLE DESCRIPTIONS:**
        ❌ "businessman, frustrated, desk, corporate, professional, tired, stressed"
        ❌ "graph, declining, red arrow, stocks, finance, market crash, economy"
        ❌ "boardroom, empty chairs, corporate meeting, business, conference table"
        ❌ "rainy street, night, person walking, urban, city lights, atmospheric"

        **CONTENT TO PROCESS:**
        {text}
        """

        response = model.generate_content(prompt)
        clean_response = response.text.strip().replace("```json", "").replace("```", "")
        
        timeline = json.loads(clean_response)
        
        # Add duration calculations and image prompts
        words_per_minute = 150
        for scene in timeline:
            # Calculate duration
            if 'word_count' not in scene:
                scene['word_count'] = len(scene.get('text', '').split())
            duration = (scene['word_count'] / words_per_minute) * 60
            scene['duration_seconds'] = round(duration, 1)
            
            # Generate image prompts using T5-style natural language
            description = scene.get('description', '')
            is_user_scene = scene.get('is_user_scene', False)
            
            if is_user_scene:
                user_trigger = USER_PROMPT
                # For user scenes, naturally integrate the user trigger
                if description.startswith("A person") or description.startswith("A man"):
                    # Replace generic person reference with specific user trigger
                    final_prompt = description.replace("A person", user_trigger).replace("A man", user_trigger)
                else:
                    # Prepend user trigger naturally
                    final_prompt = f"{user_trigger} {description.lower()}"
                # Add photorealistic instruction naturally
                final_prompt = f"{final_prompt} The image should be a photorealistic cinematic photograph."
            else:
                # For non-user scenes, use the T5 description directly with photo instruction
                final_prompt = f"{description} The image should be a photorealistic cinematic photograph."
            
            scene['image_prompt'] = final_prompt
            scene['generation_mode'] = 'standard_with_kontext'
        
        logging.info(f"Generated timeline with {len(timeline)} scenes")
        return timeline

    except Exception as e:
        logging.error(f"Error generating timeline: {e}")
        return []

def get_writing_style_examples():
    """
    Reads all .md files from the writing style samples directory and concatenates them.
    """
    samples_dir = os.path.join('.private', 'writing_style_samples')
    
    if not os.path.isdir(samples_dir):
        raise FileNotFoundError(f"Writing style samples directory not found at: {samples_dir}")

    all_samples = []
    # sorted() ensures a consistent order for the prompts every time
    for filename in sorted(os.listdir(samples_dir)):
        if filename.endswith(".md"):
            filepath = os.path.join(samples_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                # Add a header to each sample for clarity in the final prompt
                all_samples.append(f"--- START OF SAMPLE FROM {filename} ---\n\n{f.read()}\n\n--- END OF SAMPLE FROM {filename} ---")

    if not all_samples:
        raise FileNotFoundError(f"No .md writing samples found in {samples_dir}")
        
    return "\n\n".join(all_samples)

def generate_voiced_summary_from_article(article: NewsArticle, length: int) -> str:
    """
    Generates a new summary for a given news article, adopting a specific
    writing voice based on provided examples.

    Args:
        article: The NewsArticle object to summarize.
        length: The target word count for the new summary.

    Returns:
        The newly generated summary in the specified writing voice.
    """
    if not article.summary:
        raise ValueError("Article must have a base summary before generating a voiced version.")

    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-pro-latest')

    writing_style = get_writing_style_examples()

    prompt = f"""
    You are a master of literary impersonation. Your task is to rewrite a news summary in the specific, unique voice of a particular author. I will provide you with a collection of the author's writings to use as a style guide, the original summary to be rewritten, and a target word count.

    **CRITICAL INSTRUCTION: Distinguish between STYLE and CONTENT.**
    - **DO** analyze the author's writing style: their tone (e.g., witty, analytical, passionate), sentence structure (e.g., short and punchy, long and flowing), cadence, vocabulary, and their tendency to use personal analogies or historical comparisons.
    - **DO NOT** copy specific, unrelated proper nouns or topics from the style guide. For example, the author may mention "Krispy Kreme" or "Marine Corps drill instructors," but you must **IGNORE** these specific content details and not insert them into the new summary unless the summary itself is about those topics. Your goal is to write *as if* the author were writing about the *new subject*.

    Your final output must ONLY be the rewritten summary. Do not include any preambles, apologies, or explanations.

    **Author's Style Guide (learn the style, ignore the specific content):**
    ---
    {writing_style}
    ---

    **Original Summary to Rewrite:**
    ---
    {article.summary}
    ---

    **Your Task:**
    Rewrite the "Original Summary" in the voice and style of the author from the "Style Guide". The rewritten summary should be approximately {length} words long. Remember to capture the *how* of the writing, not the *what*.
    """

    response = model.generate_content(prompt)
    return response.text

def generate_voiced_summary_from_content(content: str, length: int) -> str:
    """
    Generates a voiced summary directly from article content, bypassing the base summary step.
    This is the preferred method for our new Google News + Playwright pipeline.
    
    Args:
        content: The full article content to process
        length: Target word count for the voiced summary
        
    Returns:
        A voiced summary in the user's style
    """
    return generate_voiced_summary_from_raw_content(content, length)

def generate_voiced_summary_from_raw_content(raw_content: str, length: int) -> str:
    """
    Generates the user's response to a full news article, as if they read the entire piece.
    This bypasses intermediate summarization to preserve nuance and allow for thoughtful commentary.

    Args:
        raw_content: The complete article text to respond to.
        length: The target word count for the response.

    Returns:
        The user's response in their writing voice.
    """
    if not raw_content or len(raw_content.strip()) < 100:
        raise ValueError("Raw content must be substantial for voice response generation.")

    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-pro-latest')

    writing_style = get_writing_style_examples()

    prompt = f"""
    You are {USER}, and you've just finished reading a news article. Your task is to write your response to this article in your distinctive voice and style, as if you're commenting on it or sharing your thoughts about it with others.

    **CRITICAL INSTRUCTION: This is not a summary.**
    - **DO NOT** simply rewrite or summarize the article
    - **DO** respond to it as {USER} would - with your own perspective, analysis, commentary, or reaction
    - **DO** capture {USER}'s unique writing style: tone, sentence structure, vocabulary, analogies, and way of thinking
    - **DO** feel free to agree, disagree, add context, or provide your own insights about the topic
    - **DO NOT** copy specific unrelated proper nouns from your style guide unless they're genuinely relevant

    Your response should feel like {USER} just read this article and is now sharing his thoughts about it.

    **{USER}'s Writing Style Guide:**
    ---
    {writing_style}
    ---

    **Article {USER} Just Read:**
    ---
    {raw_content}
    ---

    **Your Task:**
    Write {USER}'s response to this article in approximately {length} words. This should be his commentary, analysis, or reaction - not a summary. Write as if {USER} is speaking directly to his audience about what he just read.
    """

    response = model.generate_content(prompt)
    return response.text

def generate_voiced_response_from_articles(articles: list, topic: str, length: int) -> str:
    """
    Generates the user's response to multiple articles on the same topic.
    Synthesizes insights from all articles rather than responding to just one.

    Args:
        articles: List of NewsArticle objects to synthesize from
        topic: The topic/query these articles relate to  
        length: Target word count for the response

    Returns:
        The user's synthesized response across all articles
    """
    if not articles:
        raise ValueError("At least one article required for synthesis.")
    
    # Combine all article content with clear separation
    combined_content = f"TOPIC: {topic}\n\n"
    combined_content += f"SOURCES: {len(articles)} articles\n\n"
    
    for i, article in enumerate(articles, 1):
        combined_content += f"--- ARTICLE {i}: {article.title} ---\n"
        combined_content += f"Source: {article.url}\n\n"
        combined_content += article.raw_content
        combined_content += f"\n\n--- END ARTICLE {i} ---\n\n"
    
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-pro-latest')

    writing_style = get_writing_style_examples()

    prompt = f"""
    You are {USER}, and you're about to record a 60-second spoken summary about "{topic}". This is a script to be read aloud, so it should sound natural and conversational when spoken.

    **CRITICAL INSTRUCTIONS:**
    - **DO NOT** mention articles, sources, or reading anything - speak about the situation directly
    - **DO** synthesize all the key information into one cohesive narrative about the situation
    - **DO** write in {USER}'s distinctive voice and style from the style guide
    - **DO** make it sound like {USER} is speaking directly to his audience about what's happening
    - **DO** keep it to approximately 150-180 words (60 seconds of speaking)
    - **DO NOT** use phrases like "according to reports" or "articles suggest" - speak as if you know what's happening
    - **DO NOT** copy specific unrelated proper nouns from your style guide

    This should sound like {USER} giving his take on the current situation regarding "{topic}" - informed, conversational, and in his unique voice.

    **{USER}'s Writing Style Guide:**
    ---
    {writing_style}
    ---

    **Current Situation Information:**
    ---
    {combined_content}
    ---

    **Your Task:**
    Write {USER}'s 60-second spoken script about the "{topic}" situation in approximately 150-180 words. This should be his direct commentary on what's happening, written to be read aloud naturally. Focus on the key developments and {USER}'s perspective on the situation.
    """

    response = model.generate_content(prompt)
    return response.text

def generate_voiced_story_from_user_and_news(user_story: str, news_content: str, length: int) -> str:
    """
    Generates the user's enhanced story by combining user's preliminary story with news articles.
    This is designed for the streamlined story workflow.

    Args:
        user_story: The user's preliminary story/script
        news_content: Combined content from news articles
        length: Target word count for the enhanced story

    Returns:
        The user's enhanced version combining both sources
    """
    if not user_story or len(user_story.strip()) < 50:
        raise ValueError("User story must be substantial for enhancement.")
    
    if not news_content or len(news_content.strip()) < 100:
        raise ValueError("News content must be substantial for enhancement.")

    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-pro-latest')

    writing_style = get_writing_style_examples()

    prompt = f"""
    You are {USER}, and you're creating an enhanced script by combining your user's preliminary story with relevant news information. Your task is to weave these elements together into a cohesive narrative in your distinctive voice.

    **CRITICAL INSTRUCTIONS:**
    - **DO** use the user's story as the foundation and primary narrative thread
    - **DO** enhance it with relevant details, context, and insights from the news sources  
    - **DO** write in {USER}'s distinctive voice and style from the style guide
    - **DO** create a seamless narrative that sounds like {USER} telling a complete story
    - **DO** maintain the user's core ideas while adding {USER}'s perspective and analysis
    - **DO NOT** simply concatenate the sources - blend them thoughtfully
    - **DO NOT** copy specific unrelated proper nouns from your style guide
    - **DO** make it feel like a cohesive script to be read aloud

    This should sound like {USER} took the user's preliminary ideas and crafted them into a complete, enhanced narrative with supporting context from current events.

    **{USER}'s Writing Style Guide:**
    ---
    {writing_style}
    ---

    **User's Preliminary Story:**
    ---
    {user_story}
    ---

    **Supporting News Context:**
    ---
    {news_content}
    ---

    **Your Task:**
    Create {USER}'s enhanced script in approximately {length} words by thoughtfully combining the user's story with relevant news context. This should be a cohesive narrative that builds on the user's foundation while adding {USER}'s distinctive voice and insights.
    """

    response = model.generate_content(prompt)
    return response.text

def generate_voiced_response_to_query(query: str, context_content: str = None, length: int = 250) -> str:
    """
    Generates the user's response to a query, optionally using context content as background.
    This is designed for standalone voice responses to prompts.

    Args:
        query: The question or prompt to respond to
        context_content: Optional existing user content to use as context
        length: Target word count for the response

    Returns:
        The user's response in their distinctive voice
    """
    if not query or len(query.strip()) < 10:
        raise ValueError("Query must be substantial for response generation.")

    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-pro-latest')

    writing_style = get_writing_style_examples()

    # Build prompt based on whether context is provided
    if context_content and len(context_content.strip()) > 20:
        prompt = f"""
        You are {USER}. You've previously written or said the content provided in the "Context" section below. Now you're being asked a new question or prompt. Your task is to respond to this new query in your distinctive voice, building naturally on your previous thoughts if relevant.

        **CRITICAL INSTRUCTIONS:**
        - **DO** respond to the query as {USER} would - with your perspective, analysis, and distinctive voice
        - **DO** reference your previous context if it's relevant to the current query
        - **DO** write in {USER}'s unique style: tone, sentence structure, vocabulary, analogies, and way of thinking
        - **DO** make this feel like a natural continuation of your thoughts, not a forced connection
        - **DO NOT** copy specific unrelated proper nouns from your style guide unless genuinely relevant
        - **DO NOT** simply repeat the context - build on it to answer the new query
        - **DO** feel free to agree, disagree, add new insights, or take the conversation in new directions

        This should sound like {USER} naturally responding to a new question, informed by his previous thoughts.

        **{USER}'s Writing Style Guide:**
        ---
        {writing_style}
        ---

        **Context ({USER}'s Previous Thoughts):**
        ---
        {context_content}
        ---

        **New Query:**
        ---
        {query}
        ---

        **Your Task:**
        Write {USER}'s response to the query in approximately {length} words. This should be his natural response, building on his previous context where relevant, written in his distinctive voice.
        """
    else:
        prompt = f"""
        You are {USER}, and you're responding to a question or prompt. Your task is to write your response in your distinctive voice and style, as if you're sharing your thoughts with your audience.

        **CRITICAL INSTRUCTIONS:**
        - **DO** respond to the query as {USER} would - with your perspective, analysis, and distinctive voice
        - **DO** write in {USER}'s unique style: tone, sentence structure, vocabulary, analogies, and way of thinking
        - **DO** feel free to agree, disagree, provide insights, or take the conversation in interesting directions
        - **DO NOT** copy specific unrelated proper nouns from your style guide unless genuinely relevant
        - **DO** make this feel like {USER} naturally responding to the prompt

        This should sound like {USER} sharing his authentic thoughts on the topic.

        **{USER}'s Writing Style Guide:**
        ---
        {writing_style}
        ---

        **Query:**
        ---
        {query}
        ---

        **Your Task:**
        Write {USER}'s response to this query in approximately {length} words. This should be his natural response, written in his distinctive voice and style.
        """

    response = model.generate_content(prompt)
    return response.text

def generate_timeline_from_file(filepath: str) -> list[dict]:
    """
    Generates a timeline from any text file containing content.
    This bridges file-based voice outputs to the timeline generation system.

    Args:
        filepath: Path to text file containing the content to convert to timeline

    Returns:
        List of timeline scene dictionaries with text, description, scene number, etc.
    """
    import os
    
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Content file not found: {filepath}")
    
    # Read the file content
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    
    # Extract just the main content if it has markdown headers/metadata
    lines = content.split('\n')
    content_start = 0
    
    # Skip past any markdown headers and metadata
    for i, line in enumerate(lines):
        if line.strip() == '---' and i > 0:  # End of frontmatter
            content_start = i + 1
            break
        elif line.startswith('# ') or line.startswith('**'):  # Headers or bold metadata
            continue
        elif line.strip() and not line.startswith('#') and not line.startswith('**'):
            content_start = i
            break
    
    # Extract the actual content
    main_content = '\n'.join(lines[content_start:]).strip()
    
    if not main_content or len(main_content) < 100:
        raise ValueError(f"File content too short for timeline generation: {len(main_content)} characters")
    
    # Generate timeline using existing function
    timeline = generate_timeline(main_content)
    
    return timeline

def analyze_content_concepts(text: str) -> List[Dict]:
    """
    Analyzes text content to identify key concepts and themes for visual representation.
    This creates a conceptual foundation before segmenting into scenes.
    
    Args:
        text (str): The content to analyze
        
    Returns:
        List[Dict]: List of concept dictionaries with themes and visual elements
    """
    try:
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-pro-latest')

        prompt = f"""
        You are a content analyst specializing in visual storytelling. Your task is to read the following text and identify the key CONCEPTS that would be most effective for visual representation.

        Your output MUST be a valid JSON array of concept objects. Each concept should have:
        1. "concept": A clear, concise name for the concept
        2. "description": What this concept represents in the context
        3. "visual_elements": Specific visual elements that could represent this concept
        4. "emotional_tone": The emotional context (frustrated, analytical, hopeful, etc.)
        5. "key_phrases": Important phrases from the text that relate to this concept

        Focus on concepts that are:
        - CONCRETE and visually representable
        - CENTRAL to the main message
        - EMOTIONALLY resonant
        - DISTINCT from each other

        Examples of good concepts:
        - Political manipulation tactics
        - Democratic process integrity  
        - Media amplification cycles
        - Personal conviction/voting decisions
        - Social progress vs. backlash

        Text to analyze:
        ---
        {text}
        ---
        """

        response = model.generate_content(prompt)
        clean_response = response.text.strip().replace("```json", "").replace("```", "")
        
        concepts = json.loads(clean_response)
        logging.info(f"Analyzed content and identified {len(concepts)} key concepts")
        return concepts

    except Exception as e:
        logging.error(f"Error in concept analysis: {e}")
        return []

def generate_concept_based_timeline(text: str, theme: Optional[str] = None) -> List[Dict]:
    """
    Generates a timeline based on conceptual analysis rather than arbitrary segmentation.
    Creates scenes with single, focused visual concepts and appropriate scene density.
    
    Args:
        text (str): The content to process
        theme (str, optional): Visual theme to integrate into prompts
        
    Returns:
        List[Dict]: Timeline with concept-based scenes and integrated visual prompts
    """
    
    try:
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-pro-latest')

        # First, analyze concepts to understand the content themes
        concepts = analyze_content_concepts(text)
        
        # Get theme styling if provided
        theme_integration = ""
        theme_style = ""
        if theme:
            from .themes import FLUX_THEMES
            theme_style = FLUX_THEMES.get(theme, "")
            theme_integration = f"""
            **THEME INTEGRATION:**
            All visual descriptions must incorporate this style: "{theme_style}"
            Blend the theme seamlessly into each visual description.
            """

        concepts_text = json.dumps(concepts, indent=2) if concepts else "No specific concepts identified"
        
        prompt = f"""
        You are creating a visual timeline for multimedia production. Create scenes that are:
        1. **SINGLE FOCUS**: Each scene shows ONE distinct thing - one person, one object, one location, one action
        2. **APPROPRIATE DENSITY**: Similar scene count to standard method (~15-25 words per scene)
        3. **CONCEPT-INFORMED**: Use the concept analysis to create more meaningful visuals
        4. **FLUX-OPTIMIZED**: Use T5-style natural language descriptions, not keyword lists

        Your output MUST be a valid JSON array of scene objects with these keys:
        1. "scene": Scene number (integer)
        2. "text": The exact text from the original that corresponds to this scene
        3. "concept": Which concept from the analysis this scene represents
        4. "description": SINGLE, focused visual description optimized for Flux T5 prompting
        5. "is_user_scene": Boolean (true if using "I", "me", "my")
        6. "duration_seconds": Estimated duration based on word count
        7. "word_count": Number of words in the text

        **CRITICAL SEGMENTATION RULES:**
        - **TARGET 15-25 words per scene** (don't create long scenes)
        - **Break at natural concept boundaries** but maintain scene density
        - **Each scene = one visual concept** (not multiple ideas combined)
        - **Use concepts to inform better visuals** (not to reduce scene count)

        **CRITICAL VISUAL DESCRIPTION RULES (T5/FLUX OPTIMIZED):**
        - **COMPLETE SENTENCES**: Write as if explaining the scene to a person, not keyword lists
        - **SINGLE SUBJECT FOCUS**: One person, one object, one location per scene
        - **NO COMPOSITES**: Never combine multiple elements (no "A and B", no "while", no "with")
        - **LOGICAL STRUCTURE**: Subject → Action/Pose → Setting → Lighting → Style
        - **ACTIVE LANGUAGE**: Use verbs to describe actions and interactions
        - **SPECIFIC DETAILS**: Avoid vague terms like "beautiful" - describe what makes it so
        - **NO KEYWORD SPAM**: Don't list adjectives - integrate them into natural sentences

        **EXAMPLES OF GOOD T5/FLUX DESCRIPTIONS:**
        ✅ "A middle-aged businessman sits at his desk, rubbing his temples with both hands in frustration."
        ✅ "A red arrow points sharply downward on a stock market graph displayed on a computer screen."
        ✅ "An empty boardroom table reflects the overhead fluorescent lighting in a corporate office."
        ✅ "A person walks alone down a rain-soaked city street at night under dim streetlights."

        **EXAMPLES OF BAD KEYWORD-STYLE DESCRIPTIONS:**
        ❌ "businessman, frustrated, desk, corporate, professional, tired, stressed"
        ❌ "graph, declining, red arrow, stocks, finance, market crash, economy"
        ❌ "boardroom, empty chairs, corporate meeting, business, conference table"
        ❌ "rainy street, night, person walking, urban, city lights, atmospheric"

        **EXAMPLES OF BANNED COMPOSITE DESCRIPTIONS:**
        ❌ "A man at his desk while graphs show declining performance"
        ❌ "People arguing around a conference table with charts in the background"
        ❌ "A businessman reviewing documents and checking his phone"
        ❌ "Multiple politicians debating while crowds watch"

        {theme_integration}

        **CONCEPTS IDENTIFIED:**
        {concepts_text}

        **ORIGINAL TEXT:**
        {text}
        """

        response = model.generate_content(prompt)
        clean_response = response.text.strip().replace("```json", "").replace("```", "")
        
        timeline = json.loads(clean_response)
        
        # Add duration calculations and generate final image prompts
        words_per_minute = 150
        for scene in timeline:
            if 'word_count' not in scene:
                scene['word_count'] = len(scene.get('text', '').split())
            duration = (scene['word_count'] / words_per_minute) * 60
            scene['duration_seconds'] = round(duration, 1)
            
            # Generate the ACTUAL image prompt that will be sent to the API
            description = scene.get('description', '')
            is_user_scene = scene.get('is_user_scene', False)
            
            # Ensure description is singular and focused
            if ' and ' in description or ' with ' in description or ' while ' in description:
                logging.warning(f"Scene {scene.get('scene', '?')} has composite description: {description}")
            
            if theme and theme_style:
                # Direct theme integration with T5-style natural language
                if is_user_scene:
                    user_trigger = USER_PROMPT
                    # For user scenes, naturally integrate the user trigger into the T5 description
                    if description.startswith("A person") or description.startswith("A man"):
                        # Replace generic person reference with specific user trigger
                        final_prompt = description.replace("A person", user_trigger).replace("A man", user_trigger)
                    else:
                        # Prepend user trigger naturally
                        final_prompt = f"{user_trigger} {description.lower()}"
                    # Add theme naturally to the sentence
                    final_prompt = f"{final_prompt} The scene is styled with {theme_style}"
                else:
                    # For non-user scenes, add theme naturally to the description
                    final_prompt = f"{description} The scene is styled with {theme_style}"
                scene['image_prompt'] = final_prompt
                scene['generation_mode'] = 'direct_theme_integration'
            else:
                # Standard generation using T5-style descriptions directly
                if is_user_scene:
                    user_trigger = USER_PROMPT
                    # For user scenes, naturally integrate the user trigger
                    if description.startswith("A person") or description.startswith("A man"):
                        # Replace generic person reference with specific user trigger
                        final_prompt = description.replace("A person", user_trigger).replace("A man", user_trigger)
                    else:
                        # Prepend user trigger naturally
                        final_prompt = f"{user_trigger} {description.lower()}"
                    # Add photorealistic instruction naturally
                    final_prompt = f"{final_prompt} The image should be a photorealistic cinematic photograph."
                else:
                    # For non-user scenes, use the T5 description directly with photo instruction
                    final_prompt = f"{description} The image should be a photorealistic cinematic photograph."
                scene['image_prompt'] = final_prompt
                scene['generation_mode'] = 'standard_with_kontext'
        
        logging.info(f"Generated concept-based timeline with {len(timeline)} scenes")
        return timeline

    except Exception as e:
        logging.error(f"Error in concept-based timeline generation: {e}")
        logging.info("Falling back to standard timeline generation")
        return generate_timeline(text)

def add_image_prompts_to_timeline(timeline: List[Dict], theme: Optional[str] = None) -> List[Dict]:
    """
    Adds final image prompts to an existing timeline based on theme and user scene detection.
    This shows exactly what will be sent to the image generation API using T5-style prompting.
    
    Args:
        timeline: Existing timeline with descriptions
        theme: Optional theme to integrate
        
    Returns:
        Updated timeline with image_prompt fields
    """
    theme_style = ""
    if theme:
        from .themes import FLUX_THEMES
        theme_style = FLUX_THEMES.get(theme, "")
    
    for scene in timeline:
        description = scene.get('description', '')
        is_user_scene = scene.get('is_user_scene', False)
        
        if theme and theme_style:
            # Direct theme integration with T5-style natural language
            if is_user_scene:
                user_trigger = USER_PROMPT
                # For user scenes, naturally integrate the user trigger into the T5 description
                if description.startswith("A person") or description.startswith("A man"):
                    # Replace generic person reference with specific user trigger
                    final_prompt = description.replace("A person", user_trigger).replace("A man", user_trigger)
                else:
                    # Prepend user trigger naturally
                    final_prompt = f"{user_trigger} {description.lower()}"
                # Add theme naturally to the sentence
                final_prompt = f"{final_prompt} The scene is styled with {theme_style}"
            else:
                # For non-user scenes, add theme naturally to the description
                final_prompt = f"{description} The scene is styled with {theme_style}"
            scene['image_prompt'] = final_prompt
            scene['generation_mode'] = 'direct_theme_integration'
        else:
            # Standard generation using T5-style descriptions directly
            if is_user_scene:
                user_trigger = USER_PROMPT
                # For user scenes, naturally integrate the user trigger
                if description.startswith("A person") or description.startswith("A man"):
                    # Replace generic person reference with specific user trigger
                    final_prompt = description.replace("A person", user_trigger).replace("A man", user_trigger)
                else:
                    # Prepend user trigger naturally
                    final_prompt = f"{user_trigger} {description.lower()}"
                # Add photorealistic instruction naturally
                final_prompt = f"{final_prompt} The image should be a photorealistic cinematic photograph."
            else:
                # For non-user scenes, use the T5 description directly with photo instruction
                final_prompt = f"{description} The image should be a photorealistic cinematic photograph."
            scene['image_prompt'] = final_prompt
            scene['generation_mode'] = 'standard_with_kontext'
    
    return timeline

if __name__ == '__main__':
    # Example usage for direct testing
    test_text = (
        "In a landmark decision, the city council has approved a new initiative to "
        "install solar panels on all municipal buildings. The project, which is "
        "expected to be completed by 2026, aims to reduce the city's carbon "
        "footprint by 40%. The council also announced plans for a new public "
        "transportation system powered entirely by renewable energy."
    )

    print("--- Testing Summarization ---")
    summary = generate_summary(test_text)
    print(f"Original: {test_text}")
    print(f"Summary: {summary}")

    print("\n--- Testing Embedding ---")
    embedding = generate_embedding(test_text)
    if embedding:
        print(f"Generated embedding of dimension: {len(embedding)}")
        print(f"First 5 dimensions: {embedding[:5]}")
        
    print("\n--- Testing Timeline Generation ---")
    timeline = generate_timeline(summary)
    if timeline:
        print(f"Generated timeline with {len(timeline)} scenes.")
        print(f"First scene: {timeline[0]}") 