import logging
import random
import replicate
import os
import requests
from .config import USER_PROMPT
from typing import Optional

# The user-provided template for generating high-quality prompts.
PROMPT_TEMPLATE = "photorealistic cinematic photo of {subject}, dynamic camera angle, shot by FujifilmXT, 85mm, f/2.2"

def generate_rich_image_prompt(scene_description: str) -> str:
    """
    Generates a rich, detailed image prompt using a predefined template.
    
    Args:
        scene_description (str): The core subject of the prompt.
        
    Returns:
        str: A fully formatted, detailed prompt for an image generator.
    """
    return PROMPT_TEMPLATE.format(subject=scene_description)

def generate_themed_image_prompt(scene_description: str, theme_style: str) -> str:
    """
    Generates a rich image prompt with theme integration for direct generation.
    This avoids the expensive kontext step by building the theme into the initial prompt.
    
    Args:
        scene_description (str): The core visual concept
        theme_style (str): The theme styling to integrate
        
    Returns:
        str: A themed prompt ready for direct image generation
    """
    # Blend the theme naturally into the scene description
    themed_prompt = f"{scene_description}, {theme_style}"
    return themed_prompt

def generate_concept_image(
    concept_description: str, 
    theme: Optional[str] = None,
    article_id: int = 0, 
    scene_number: int = 0, 
    is_user_scene: bool = False,
    use_kontext: bool = True
) -> str | None:
    """
    Generates images using concept-based descriptions with optional theme integration.
    
    Args:
        concept_description: Rich visual description of the concept
        theme: Optional theme name to integrate
        article_id: Article ID for file organization
        scene_number: Scene number for file naming
        is_user_scene: Whether this features the user personally
        use_kontext: Whether to use expensive kontext styling (default True for backwards compatibility)
        
    Returns:
        Path to generated image or None if failed
    """
    logging.info(f"Generating concept image for article {article_id}, scene {scene_number}")
    
    output_dir = os.path.join('instance', 'images', str(article_id))
    os.makedirs(output_dir, exist_ok=True)
    
    if theme and not use_kontext:
        # Direct theme integration - cost-effective approach
        from .themes import FLUX_THEMES
        theme_style = FLUX_THEMES.get(theme, "")
        final_prompt = generate_themed_image_prompt(concept_description, theme_style)
        output_path = os.path.join(output_dir, f"scene_{scene_number}_themed.png")
        
        logging.info(f"Using direct theme integration: {theme}")
    else:
        # Standard generation (with potential kontext styling later)
        final_prompt = concept_description
        output_path = os.path.join(output_dir, f"scene_{scene_number}.webp")
    
    model_name = "black-forest-labs/flux-dev"
    input_payload = {
        "prompt": final_prompt,
        "aspect_ratio": "4:5",
        "guidance": 3.5,
        "output_format": "png" if theme and not use_kontext else "webp"
    }

    if is_user_scene:
        logging.info("User-centric scene detected. Switching to specialized model.")
        user_trigger = USER_PROMPT
        
        if theme and not use_kontext:
            # Integrate user trigger with themed prompt
            final_prompt = f"{user_trigger}, {final_prompt}"
        else:
            # Standard user prompt with template
            final_prompt = PROMPT_TEMPLATE.format(subject=f"{user_trigger} {concept_description}")

        model_name = "thompsonplyler/thompsonplyler_flux_v3_thmpsnplylr:e45e257ecbf18f9fb4484009c86b6a759e3529eaeae3d4fb90636adbb6e00b2e"
        input_payload["prompt"] = final_prompt
        input_payload["lora_scale"] = 1
        input_payload["guidance_scale"] = 3
        input_payload["num_inference_steps"] = 28

    try:
        logging.info(f"Generating image with prompt: {final_prompt}")
        
        output = replicate.run(model_name, input=input_payload)
        
        if isinstance(output, list) and len(output) > 0:
            image_url = output[0]
        else:
            image_url = output
        
        response = requests.get(image_url)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        logging.info(f"Successfully saved image to {output_path}")
        return output_path
        
    except Exception as e:
        logging.error(f"Error generating concept image: {e}")
        return None

def source_image_for_scene(scene_description: str) -> dict:
    """
    For a given scene description, either finds a suitable existing image via
    a simulated web search, or generates a rich prompt for an AI image generator.
    
    Args:
        scene_description (str): The description of the scene.
        
    Returns:
        dict: A dictionary containing either a 'found_image_url' or a 
              'generated_image_prompt'.
    """
    logging.info(f"Scouting for image for scene: '{scene_description[:50]}...'")
    
    # Placeholder logic to simulate searching vs. generating.
    # We'll simulate a 30% chance of "finding" a suitable image online.
    if random.random() < 0.3:
        logging.info("Simulating a successful image search.")
        return {"found_image_url": f"https://picsum.photos/seed/{random.randint(1, 1000)}/400/600"}
    else:
        logging.info("Image search failed or below threshold. Generating a rich prompt.")
        prompt = generate_rich_image_prompt(scene_description)
        return {"generated_image_prompt": prompt}

def generate_raw_image(prompt: str, article_id: int, scene_number: int, is_user_scene: bool = False) -> str | None:
    """
    Generates a 'raw' content-focused image using Replicate.
    This image is meant for a later styling pass.
    """
    logging.info(f"Generating image for article {article_id}, scene {scene_number} with prompt: '{prompt}'")
    
    output_dir = os.path.join('instance', 'images', str(article_id))
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"scene_{scene_number}.webp")

    # The final prompt is just the scene description
    final_prompt = prompt
    
    model_name = "black-forest-labs/flux-dev"
    input_payload = {
        "prompt": final_prompt,
        "aspect_ratio": "4:5",
        "guidance": 3.5
    }

    if is_user_scene:
        logging.info("User-centric scene detected. Switching to specialized model.")
        user_trigger = USER_PROMPT
        # The PROMPT_TEMPLATE expects a {subject}, so we format it correctly
        final_prompt = PROMPT_TEMPLATE.format(subject=f"{user_trigger} {prompt}")

        model_name = "thompsonplyler/thompsonplyler_flux_v3_thmpsnplylr:e45e257ecbf18f9fb4484009c86b6a759e3529eaeae3d4fb90636adbb6e00b2e"
        input_payload["prompt"] = final_prompt
        input_payload["lora_scale"] = 1
        input_payload["guidance_scale"] = 3
        input_payload["num_inference_steps"] = 28


    try:
        logging.info(f"Running model {model_name} with final prompt: '{final_prompt}'")
        
        image_urls = replicate.run(
            model_name,
            input=input_payload
        )
        
        first_image_url = next(iter(image_urls), None)

        if not first_image_url:
            logging.error("Replicate API did not return an image URL.")
            return None

        response = requests.get(first_image_url, stream=True)
        response.raise_for_status()

        with open(output_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        
        logging.info(f"Successfully saved image to {output_path}")
        return output_path

    except Exception as e:
        logging.error(f"An error occurred while generating the raw image: {e}")
        print(f"DEBUG: An error occurred in generate_raw_image: {e}")
        return None

def apply_style_to_image(image_path_or_url: str, style_prompt: str, article_id: int, scene_number: int) -> str | None:
    """
    Applies a consistent style to an existing image file.
    """
    logging.info(f"Applying style to image for article {article_id}, scene {scene_number} from path: {image_path_or_url}")

    output_dir = os.path.join('instance', 'images', str(article_id))
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"scene_{scene_number}_styled.png")

    try:
        with open(image_path_or_url, "rb") as image_file:
            input_payload = {
                "prompt": style_prompt,
                "input_image": image_file,
                "output_format": "png"
            }

            # The output is a single file-like object, not an iterator
            output_file_object = replicate.run(
                "black-forest-labs/flux-kontext-pro",
                input=input_payload
            )
        
        # Write the binary content to the output file
        with open(output_path, "wb") as file:
            file.write(output_file_object.read())
        
        logging.info(f"Successfully saved stylized image to {output_path}")
        return output_path

    except Exception as e:
        logging.error(f"An error occurred during image style application: {e}")
        print(f"DEBUG: An error occurred in apply_style_to_image: {e}")
        return None

if __name__ == '__main__':
    test_description = "The new center will be based in Washington, DC, with a focus on AI safety and standards."
    
    print("--- Testing Upgraded Image Scout (run multiple times to see different outcomes) ---")
    for i in range(5):
        result = source_image_for_scene(test_description)
        print(f"\nRun {i+1}:")
        print(f"  Scene Description: {test_description}")
        print(f"  Result: {result}") 