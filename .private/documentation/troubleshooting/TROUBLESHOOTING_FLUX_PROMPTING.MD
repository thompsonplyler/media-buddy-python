## **Complete Flux Prompting & Image Generation Guide**

This guide provides comprehensive best practices for T5-style image generation with Flux.1, creative image conversion techniques, and Kontext-based editing. It consolidates all prompting knowledge for Media Buddy's image generation pipeline.

### **Quick Reference**

- **T5 Prompting:** Natural language descriptions, not keyword lists
- **Single Concept Rule:** One subject per image, no composites
- **Kontext Editing:** Text-based image modification for style transfer
- **Creative Conversion:** Advanced techniques for artistic transformations

---

## **Part 1: Core T5 Prompting for Flux.1**

### **The Core Difference: Natural Language vs. Keywords**

The most significant shift from CLIP to T5 is the emphasis on **natural, descriptive language over a "bag of keywords."**

- **CLIP (e.g., Stable Diffusion):** Responds well to a series of keywords, artist names, and style tags. The order can matter, but the model is primarily looking for distinct concepts to combine.
  - _Example:_ masterpiece, best quality, 1girl, solo, cat ears, green hair, magical forest, by greg rutkowski, artgerm, trending on artstation
- **T5 (Flux.1):** Understands grammar, sentence structure, and the relationships between objects and actions. It performs best when you describe the scene as if you were explaining it to a person.
  - _Example:_ A cinematic, full-body portrait of a young woman with vibrant green hair and cat ears, standing alone in a magical, misty forest. The style should be reminiscent of a digital painting, with soft, ethereal lighting.

### **The DO's of Flux Prompting**

#### **✅ DO: Write in Complete, Descriptive Sentences**

Treat the prompt like a detailed set of instructions. The more specific and clear your description, the better the result.

- **Instead of:** A car, red, fast, on a road
- **Try:** A photograph of a cherry-red sports car speeding down a winding coastal highway at sunset, with motion blur indicating its high speed.

#### **✅ DO: Structure Your Prompt Logically**

For complex scenes, describe the elements in a hierarchical order. This helps the model understand the composition of the image. A good structure is:

1. **Subject:** The main focus of the image.
2. **Action/Pose:** What the subject is doing.
3. **Setting/Background:** The environment around the subject.
4. **Composition & Framing:** The camera shot type (e.g., close-up, wide shot, overhead view).
5. **Lighting:** The mood and style of the lighting (e.g., soft morning light, dramatic backlighting, neon glow).
6. **Style:** The overall aesthetic (e.g., photorealistic, 3D Pixar-style animation, vintage comic book art).
7. **Technical Details (for photorealism):** Camera and lens information (e.g., shot on a DSLR with a 50mm lens, f/1.8).

#### **✅ DO: Use Active and Dynamic Language**

Use verbs to describe actions and interactions within the scene. This creates more dynamic and engaging images.

- **Instead of:** A knight and a dragon.
- **Try:** A knight in shining silver armor is bravely fighting a massive, fire-breathing dragon on a rocky cliffside.

#### **✅ DO: Be Explicit About Text**

Flux.1 is excellent at rendering text. Be very specific about the text you want to appear in the image.

- **Example:** A photograph of a rustic wooden sign in a forest. The sign has the words "Whispering Pines Trail" elegantly carved into it.

#### **✅ DO: Describe Layered Compositions**

Clearly define the foreground, middle ground, and background to create depth and complex scenes.

- **Example:** In the foreground, a small wooden boat is tied to a dock. In the middle ground, a calm lake reflects the sky. In the background, a dense pine forest lines the shore under a cloudy sky.

### **The DON'Ts of Flux Prompting**

#### **❌ DON'T: Use Keyword "Spam"**

Avoid simply listing keywords. T5 will try to find relationships between them, which can lead to confusing or messy results.

- **Avoid:** girl, forest, magic, glowing, mushrooms, night, stars, ethereal, beautiful
- **Instead:** A girl is walking through a magical forest at night, surrounded by glowing mushrooms. The sky above is filled with stars, creating an ethereal and beautiful scene.

#### **❌ DON'T: Use Prompt Weights or Special Syntax**

Flux.1 does not support weighting syntax like (word:1.2) or \[word\]. To emphasize something, use natural language.

- **Avoid:** A field of flowers with a (single red rose:1.5).
- **Instead:** A field of flowers, with a strong emphasis on a single, vibrant red rose that stands out from the others.

#### **❌ DON'T: Rely on Vague or Subjective Terms**

Words like "beautiful," "amazing," or "stunning" are subjective. Instead, describe _what_ makes the scene beautiful.

- **Avoid:** A beautiful landscape.
- **Instead:** A landscape painting of a serene valley with a crystal-clear river, rolling green hills, and a dramatic, colorful sunset.

#### **❌ DON'T: Expect a Negative Prompt to Fix Everything**

Flux.1 does not use a dedicated negative prompt field in the same way as many Stable Diffusion interfaces. To exclude something, phrase it as a positive instruction.

- **Instead of a negative prompt like:** ugly, deformed hands
- **Add to your positive prompt:** ...with perfectly formed, elegant hands. or ...her hands are not visible in the shot.

#### **❌ DON'T: Assume Artist Names Work as Magic Style Modifiers**

While T5 has knowledge of artists, simply adding "by greg rutkowski" is less effective than describing the _style_ you want to achieve.

- **Instead of:** A portrait of a queen, by greg rutkowski.
- **Try:** A portrait of a queen in the style of a digital oil painting, with dramatic, high-contrast lighting, textured brushstrokes, and a focus on realistic yet epic fantasy themes.

---

## **Part 2: Media Buddy Single-Concept Guidelines**

### **Critical Rules for Timeline Images**

#### **✅ Single Focus Requirements**

- **ONE subject per image:** One person, one object, one location, one action
- **NO composites:** Never combine multiple elements (no "A and B", no "while", no "with")
- **Complete sentences:** Write as if explaining the scene to a person, not keyword lists
- **Active language:** Use verbs to describe actions and interactions

#### **✅ Examples of Good Single-Focus Descriptions**

- "A middle-aged businessman sits at his desk, rubbing his temples with both hands in frustration."
- "A red arrow points sharply downward on a stock market graph displayed on a computer screen."
- "An empty boardroom table reflects the overhead fluorescent lighting in a corporate office."
- "A person walks alone down a rain-soaked city street at night under dim streetlights."

#### **❌ Examples of Banned Composite Descriptions**

- "A man at his desk while graphs show declining performance"
- "People arguing around a conference table with charts in the background"
- "A businessman reviewing documents and checking his phone"
- "Multiple politicians debating while crowds watch"

### **Media Buddy Implementation Pattern**

```python
# For user scenes, naturally integrate user trigger
if is_user_scene:
    user_trigger = "thmpsnplylr, a white man in his mid-40s with messy brown hair"
    if description.startswith("A person"):
        final_prompt = description.replace("A person", user_trigger)
    else:
        final_prompt = f"{user_trigger} {description.lower()}"

# Add photorealistic instruction naturally
final_prompt = f"{final_prompt} The image should be a photorealistic cinematic photograph."
```

---

## **Part 3: Flux.1 Kontext - Text-Based Image Editing**

FLUX.1 Kontext is a state-of-the-art image editing model from Black Forest Labs that allows you to edit images using text prompts. It's the best in class for text-guided image editing.

### **Available Models**

- **FLUX.1 Kontext [pro]:** State-of-the-art performance with high-quality outputs, great prompt following, and consistent results
- **FLUX.1 Kontext [max]:** Premium model with maximum performance and improved typography generation
- **FLUX.1 Kontext [dev]:** Open-weight distilled version (coming soon)

### **What Kontext Excels At**

- **Style Transfer:** Convert photos to different art styles (watercolor, oil painting, sketches)
- **Object/Clothing Changes:** Modify hairstyles, add accessories, change colors
- **Text Editing:** Replace text in signs, posters, and labels
- **Background Swapping:** Change environments while preserving subjects
- **Character Consistency:** Maintain identity across multiple edits

### **Kontext Prompting Best Practices**

#### **Be Specific**

- Use clear, detailed language with exact colors and descriptions
- Avoid vague terms like "make it better"
- Name subjects directly: "the woman with short black hair" vs. "she"

#### **Preserve Intentionally**

- Specify what should stay the same: "while keeping the same facial features"
- Use "maintain the original composition" to preserve layout
- For background changes: "Change the background to a beach while keeping the person in the exact same position"

#### **Text Editing Tips**

- Use quotation marks: "replace 'old text' with 'new text'"
- Stick to readable fonts
- Match text length when possible to preserve layout

#### **Style Transfer**

- Be specific about artistic styles: "impressionist painting" not "artistic"
- Reference known movements: "Renaissance" or "1960s pop art"
- Describe key traits: "visible brushstrokes, thick paint texture"

#### **Complex Edits**

- Break into smaller steps for better results
- Start simple and iterate
- Use descriptive action verbs instead of "transform" for more control

---

## **Part 4: Creative Image Conversion Techniques**

### **Advanced Prompting for Artistic Transformations**

#### **Core Principles**

1. **Go Beyond Simple Style Transfer:** Move past "anime" or "oil painting" to deeper, multi-layered instructions
2. **Embrace the Abstract and Surreal:** AI models excel at non-literal interpretations
3. **Incorporate Mood, Atmosphere, and Emotion:** Think about the feeling the image should evoke
4. **Consider Unconventional Materials/Textures:** Glass, smoke, tangled wires, etc.
5. **Play with Lighting and Color Palettes:** Powerful tools for mood transformation
6. **Suggest Narrative or Thematic Elements:** Subtle story suggestions enrich output

#### **Prompt Structure Components**

**Base Transformation:**

- "make it look like," "convert to," "reimagine as," "render in the style of"

**Artistic Style/Era/Movement:**

- "Impressionist painting," "Art Deco poster," "1980s synthwave," "Baroque oil painting"

**Material/Texture Transformation:**

- "made entirely of melted wax," "as if carved from granite," "woven from silk"

**Lighting and Atmosphere:**

- "bathed in ethereal moonlight," "illuminated by neon signs," "harsh chiaroscuro lighting"

**Color Palette:**

- "monochromatic sepia tones," "vibrant psychedelic colors," "muted pastel palette"

**Narrative/Thematic Elements:**

- "a scene from a forgotten fairy tale," "part of a post-apocalyptic diorama"

#### **Examples of Creative Conversion Prompts**

- "Convert this image into a gothic cathedral, where every architectural detail is constructed from swirling storm clouds and lightning, under a perpetually moonlit sky with a hint of dark purple."

- "Reimagine this scene as a highly detailed diorama crafted entirely from intricate paper cutouts, lit by miniature stage lights, evoking a whimsical, storybook atmosphere."

- "Transform this image into a living tapestry, where every object and figure is woven from shimmering, iridescent insect wings, glowing with internal bioluminescence."

---

## **Part 5: Cost Optimization Strategies**

### **Direct Theme Integration vs. Kontext Styling**

#### **Cost-Effective Approach (Direct Theme Integration)**

```python
# Blend theme naturally into the scene description
themed_prompt = f"{scene_description}, {theme_style}"
```

- **Cost:** ~50% less (no kontext step)
- **Use case:** When theme can be integrated directly into initial generation

#### **Premium Approach (Kontext Styling)**

```python
# Generate basic image first, then apply theme
raw_image = generate_raw_image(basic_prompt)
styled_image = apply_style_to_image(raw_image, theme_style)
```

- **Cost:** Full price (two-step process)
- **Use case:** When precise style control is needed

### **Media Buddy Implementation**

```python
if theme and not use_kontext:
    # Direct theme integration - cost-effective
    final_prompt = f"{description} The scene is styled with {theme_style}"
    generation_mode = 'direct_theme_integration'
else:
    # Standard generation for kontext styling
    final_prompt = f"{description} The image should be a photorealistic cinematic photograph."
    generation_mode = 'standard_with_kontext'
```

---

## **Part 6: Quality Validation & Troubleshooting**

### **Common Issues and Solutions**

#### **Composite Detection**

```python
# Validate single-concept requirement
if ' and ' in description or ' with ' in description or ' while ' in description:
    logging.warning(f"Scene has composite description: {description}")
```

#### **Prompt Quality Checklist**

- [ ] Single subject focus (no "A and B")
- [ ] Complete sentences (not keyword lists)
- [ ] Active language with verbs
- [ ] Specific details (avoid "beautiful", "amazing")
- [ ] Proper user integration (natural replacement)
- [ ] Theme integration (natural language blending)

#### **Troubleshooting Steps**

1. **Check prompt format:** T5 natural language vs. keywords
2. **Verify single concept rule:** No composites or multi-element descriptions
3. **Validate API inputs:** Correct model, parameters, authentication
4. **Test with known good prompts:** Establish baseline functionality
5. **Check quotas and limits:** API availability and rate limits

---

**Remember:** The goal is to create clear, descriptive prompts that explain scenes like you're talking to a person, while maintaining the single-concept focus required for effective visual storytelling.
