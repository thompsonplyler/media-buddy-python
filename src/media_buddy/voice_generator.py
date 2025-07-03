import os
import glob

def get_writing_style_samples():
    """
    Reads all .md files from the writing_style_samples directory
    and returns their concatenated content.
    """
    # This path is relative to the project root.
    # It assumes the script is run from the project root.
    path = ".private/writing_style_samples/*.md"
    
    # Using glob to find all text files in the directory
    sample_files = glob.glob(path)
    
    if not sample_files:
        print("Warning: No writing style samples found in .private/writing_style_samples/")
        return ""

    # Read and concatenate the content of each file
    full_sample_text = ""
    for file_path in sample_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            full_sample_text += f.read() + "\n\n"
            
    return full_sample_text

def generate_voiced_summary(base_summary: str, word_count: int) -> str:
    """
    Generates a new summary in a specific voice, based on writing samples.
    
    This is a placeholder for now. It will eventually call an LLM.
    """
    print("--- Running Voice Generator ---")
    writing_style = get_writing_style_samples()
    
    if not writing_style:
        # If no style samples are found, just return the base summary.
        return base_summary

    # Placeholder logic for now.
    # In the future, this will be a prompt to an LLM like Gemini.
    prompt = f"""
    Based on the following writing style:
    ---
    {writing_style}
    ---
    
    Please rewrite the following summary to match that style, aiming for a length of approximately {word_count} words:
    
    ---
    {base_summary}
    ---
    """
    
    print("Generated Prompt (for LLM):")
    print(prompt)
    
    # In a real implementation, you would send this prompt to the LLM API
    # and return the result. For now, we'll return a modified version of the summary.
    
    return f"[VOICED SUMMARY PLACEHOLDER] {base_summary}" 