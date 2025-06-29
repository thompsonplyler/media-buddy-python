import logging
import os
from huggingface_hub import login
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
from sentence_transformers import SentenceTransformer
import torch
import google.generativeai as genai
from .models import NewsArticle

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
    Parses a block of text and divides it into a sequence of visually descriptive
    prompts suitable for a text-to-image model.

    Args:
        text (str): The voiced summary to process.

    Returns:
        list[dict]: A list of scene dictionaries formatted as image prompts, e.g.,
                    [{"scene": 1, "description": "A quiet town at dusk, cinematic lighting."},
                     {"scene": 2, "description": "A mysterious figure in a long coat appears under a streetlamp."}]
    """
    import json

    try:
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-pro-latest')

        prompt = f"""
        You are an expert AI image prompt engineer. Your task is to read the following text and break it down into a sequence of visually descriptive scenes that can be used as prompts for a text-to-image generator like Midjourney or FLUX.

        Your output MUST be a valid JSON array of objects. Do not include any text, markdown, or explanations outside of the JSON block. Each object in the array should represent one scene and have three keys:
        1. "scene": An integer representing the scene number (starting from 1).
        2. "description": A visually rich, concrete description of the scene.
        3. "is_user_scene": A boolean value (`true` or `false`). Set this to `true` if the scene is clearly describing the author of the text (using "I", "me", "my"). Otherwise, set it to `false`.

        **CRITICAL RULES FOR DESCRIPTIONS:**
        - **BE VISUAL:** Describe what can be SEEN. Avoid abstract concepts, emotions, or intentions. Instead of "She was sad," write "A single tear rolls down her cheek." Instead of "He was angry," write "His knuckles are white as he clenches his fist."
        - **BE SELF-CONTAINED:** Each description must stand completely on its own. DO NOT use pronouns (he, she, they, it) that refer to subjects in previous scenes. If the same person appears, describe them again (e.g., "A man in a red coat...", "The man in the red coat now walks...").
        - **BE CONCRETE:** Do not describe abstract ideas like "skepticism" or "innovation". Describe the physical manifestation of those ideas. For example, instead of "a center for innovation," you might describe "gleaming servers in a modern data center" or "scientists collaborating around a futuristic interface."

        **Example:**

        ORIGINAL TEXT: "The CEO felt the pressure. The board was unhappy with the slow progress on the new AI project, which they felt was falling behind competitors. I decided to take a walk to clear my head."

        CORRECT OUTPUT:
        [
            {{"scene": 1, "description": "A CEO in a sharp business suit sits at a long boardroom table, head in his hands, under the stern gaze of portraits on the wall.", "is_user_scene": false}},
            {{"scene": 2, "description": "A line graph projected on a screen shows a declining trend line next to a competitor's rising line.", "is_user_scene": false}},
            {{"scene": 3, "description": "A man with messy brown hair walks alone on a rain-slicked city street at night, reflected in the puddles on the pavement.", "is_user_scene": true}}
        ]

        Now, please process the following text:
        ---
        {text}
        ---
        """

        response = model.generate_content(prompt)
        
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

def get_writing_style_examples():
    """
    Reads all .md files from the writing style samples directory and concatenates them.
    """
    samples_dir = os.path.join('private', 'writing_style_samples')
    
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
        A voiced summary in Thompson's style
    """
    return generate_voiced_summary_from_raw_content(content, length)

def generate_voiced_summary_from_raw_content(raw_content: str, length: int) -> str:
    """
    Generates Thompson's response to a full news article, as if he read the entire piece.
    This bypasses intermediate summarization to preserve nuance and allow for thoughtful commentary.

    Args:
        raw_content: The complete article text to respond to.
        length: The target word count for the response.

    Returns:
        Thompson's response in his writing voice.
    """
    if not raw_content or len(raw_content.strip()) < 100:
        raise ValueError("Raw content must be substantial for voice response generation.")

    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-pro-latest')

    writing_style = get_writing_style_examples()

    prompt = f"""
    You are Thompson, and you've just finished reading a news article. Your task is to write your response to this article in your distinctive voice and style, as if you're commenting on it or sharing your thoughts about it with others.

    **CRITICAL INSTRUCTION: This is not a summary.**
    - **DO NOT** simply rewrite or summarize the article
    - **DO** respond to it as Thompson would - with your own perspective, analysis, commentary, or reaction
    - **DO** capture Thompson's unique writing style: tone, sentence structure, vocabulary, analogies, and way of thinking
    - **DO** feel free to agree, disagree, add context, or provide your own insights about the topic
    - **DO NOT** copy specific unrelated proper nouns from your style guide unless they're genuinely relevant

    Your response should feel like Thompson just read this article and is now sharing his thoughts about it.

    **Thompson's Writing Style Guide:**
    ---
    {writing_style}
    ---

    **Article Thompson Just Read:**
    ---
    {raw_content}
    ---

    **Your Task:**
    Write Thompson's response to this article in approximately {length} words. This should be his commentary, analysis, or reaction - not a summary. Write as if Thompson is speaking directly to his audience about what he just read.
    """

    response = model.generate_content(prompt)
    return response.text

def generate_voiced_response_from_articles(articles: list, topic: str, length: int) -> str:
    """
    Generates Thompson's response to multiple articles on the same topic.
    Synthesizes insights from all articles rather than responding to just one.

    Args:
        articles: List of NewsArticle objects to synthesize from
        topic: The topic/query these articles relate to  
        length: Target word count for the response

    Returns:
        Thompson's synthesized response across all articles
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
    You are Thompson, and you're about to record a 60-second spoken summary about "{topic}". This is a script to be read aloud, so it should sound natural and conversational when spoken.

    **CRITICAL INSTRUCTIONS:**
    - **DO NOT** mention articles, sources, or reading anything - speak about the situation directly
    - **DO** synthesize all the key information into one cohesive narrative about the situation
    - **DO** write in Thompson's distinctive voice and style from the style guide
    - **DO** make it sound like Thompson is speaking directly to his audience about what's happening
    - **DO** keep it to approximately 150-180 words (60 seconds of speaking)
    - **DO NOT** use phrases like "according to reports" or "articles suggest" - speak as if you know what's happening
    - **DO NOT** copy specific unrelated proper nouns from your style guide

    This should sound like Thompson giving his take on the current situation regarding "{topic}" - informed, conversational, and in his unique voice.

    **Thompson's Writing Style Guide:**
    ---
    {writing_style}
    ---

    **Current Situation Information:**
    ---
    {combined_content}
    ---

    **Your Task:**
    Write Thompson's 60-second spoken script about the "{topic}" situation in approximately 150-180 words. This should be his direct commentary on what's happening, written to be read aloud naturally. Focus on the key developments and Thompson's perspective on the situation.
    """

    response = model.generate_content(prompt)
    return response.text

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