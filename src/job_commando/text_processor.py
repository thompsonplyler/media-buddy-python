import logging
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
from sentence_transformers import SentenceTransformer
import torch

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
                _models[model_name_or_path] = pipeline(task, model=model, tokenizer=tokenizer)
            elif task == 'sentence-similarity':
                 _models[model_name_or_path] = SentenceTransformer(model_name_or_path)
            else:
                _models[model_name_or_path] = pipeline(task, model=model_name_or_path)
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