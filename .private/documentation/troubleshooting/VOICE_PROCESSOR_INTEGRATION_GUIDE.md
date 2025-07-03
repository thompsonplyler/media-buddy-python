# Voice Processor Integration Guide

This guide shows you how to integrate the voice processing system from Media Buddy into any Flask project.

## What You're Getting

The voice processor gives you **two main capabilities**:

1. **Voice Adoption**: Rewrite any text in your specific writing style using AI
2. **Text Embeddings**: Generate 384-dimensional vectors for semantic similarity/search

## Quick Setup (5 minutes)

### 1. Copy the Files

Copy these files to your new Flask project:

- `voice_processor_package.py` - The main voice processor class
- `voice_processor_requirements.txt` - Dependencies

### 2. Install Dependencies

```bash
pip install -r voice_processor_requirements.txt
```

### 3. Copy Your Writing Samples

Create this directory structure in your new project:

```
your-flask-project/
├── private/
│   └── writing_style_samples/
│       ├── POV.md          # Copy from media-buddy
│       └── reddit.md       # Copy from media-buddy
└── voice_processor_package.py
```

### 4. Set Environment Variable

```bash
export GEMINI_API_KEY="your-gemini-api-key-here"
```

### 5. Basic Integration

```python
from flask import Flask, request, jsonify
from voice_processor_package import VoiceProcessor, register_voice_commands

app = Flask(__name__)

# Initialize the voice processor
voice_processor = VoiceProcessor(
    writing_samples_dir="private/writing_style_samples"
)

# Register CLI commands (optional)
register_voice_commands(app, voice_processor)

@app.route('/api/voice-convert', methods=['POST'])
def voice_convert():
    data = request.get_json()
    original_text = data['text']
    target_length = data.get('length', 250)

    # Convert text to your voice
    voiced_text = voice_processor.generate_voiced_text(original_text, target_length)

    # Generate embedding for similarity search
    embedding = voice_processor.generate_embedding(voiced_text)

    return jsonify({
        'original_text': original_text,
        'voiced_text': voiced_text,
        'embedding_dimensions': len(embedding),
        'embedding_preview': embedding[:5]  # First 5 dimensions
    })

if __name__ == '__main__':
    app.run(debug=True)
```

## Advanced Integration

### Database Integration with PostgreSQL + pgvector

If you want to store embeddings in a database (for similarity search):

1. **Install additional dependencies:**

```bash
pip install pgvector psycopg2-binary flask-sqlalchemy
```

2. **Create a model:**

```python
from flask_sqlalchemy import SQLAlchemy
from pgvector.sqlalchemy import Vector

db = SQLAlchemy()

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_content = db.Column(db.Text, nullable=False)
    voiced_content = db.Column(db.Text, nullable=True)
    # 384 dimensions for all-MiniLM-L6-v2 model
    embedding = db.Column(Vector(384))
```

3. **Use with database:**

```python
@app.route('/api/process-article', methods=['POST'])
def process_article():
    data = request.get_json()
    original_content = data['content']

    # Generate voiced version
    voiced_content = voice_processor.generate_voiced_text(original_content)

    # Generate embedding
    embedding = voice_processor.generate_embedding(voiced_content)

    # Save to database
    article = Article(
        original_content=original_content,
        voiced_content=voiced_content,
        embedding=embedding
    )
    db.session.add(article)
    db.session.commit()

    return jsonify({'id': article.id, 'status': 'processed'})

@app.route('/api/find-similar/<int:article_id>')
def find_similar(article_id):
    # Find articles similar to this one using vector similarity
    target_article = Article.query.get(article_id)
    if not target_article:
        return jsonify({'error': 'Article not found'}), 404

    # PostgreSQL vector similarity search
    similar_articles = db.session.query(Article).filter(
        Article.id != article_id
    ).order_by(
        Article.embedding.cosine_distance(target_article.embedding)
    ).limit(5).all()

    return jsonify([{
        'id': a.id,
        'voiced_content': a.voiced_content[:200] + '...'
    } for a in similar_articles])
```

## CLI Commands

The integration includes these Flask CLI commands:

```bash
# Convert text to your voice
flask generate-voice --text "Your original text here" --length 300

# Generate embedding for text
flask generate-embedding --text "Some text to embed"

# Process database records (if you set up the DB integration)
flask voice-process-db --record-id 1 --length 250
```

## Key Features

### 1. Voice Adoption

- Uses your 70KB+ of writing samples from `POV.md` and `reddit.md`
- Sophisticated prompt engineering that separates STYLE from CONTENT
- Maintains your authentic voice while writing about any topic

### 2. Embeddings System

- Uses sentence-transformers `all-MiniLM-L6-v2` model
- Generates 384-dimensional vectors
- Compatible with PostgreSQL pgvector for similarity search
- Lazy loading for performance

### 3. Timeline Generation (Bonus)

- Converts text into visual scene descriptions
- Useful for generating image prompts or storyboards
- Automatically detects user-focused vs. general scenes

## How It Works

The **key breakthrough** in your system is the prompt engineering:

```
**CRITICAL INSTRUCTION: Distinguish between STYLE and CONTENT.**
- **DO** analyze the author's writing style: tone, sentence structure, cadence, vocabulary
- **DO NOT** copy specific, unrelated proper nouns or topics from the style guide
```

This prevents the AI from inserting irrelevant personal details (like "Krispy Kreme" or "Marine Corps") while still capturing your authentic voice patterns.

## Troubleshooting

### Common Issues

1. **"Writing style samples directory not found"**

   - Make sure you copied the `private/writing_style_samples/` directory
   - Check the path in your VoiceProcessor initialization

2. **"Gemini API key required"**

   - Set the `GEMINI_API_KEY` environment variable
   - Or pass it directly: `VoiceProcessor(gemini_api_key="your-key")`

3. **PyTorch/CUDA issues**

   - The system automatically falls back to CPU if CUDA isn't available
   - For better performance, install CUDA-compatible PyTorch

4. **Memory issues with large writing samples**
   - The writing samples are cached after first load for performance
   - If memory is tight, consider splitting large sample files

### Performance Tips

- Embeddings model loads lazily (only when first used)
- Writing samples are cached after first read
- Use `torch.cuda.is_available()` to check GPU availability
- Consider using `sentence-transformers` models on GPU for faster embedding generation

## What Makes This Special

Your system solves the **"AI voice adoption problem"** that most people struggle with:

1. **Enough training data**: 70KB+ of authentic writing samples
2. **Smart prompt engineering**: Separates style from content
3. **Robust architecture**: Handles errors gracefully, caches for performance
4. **Proven results**: You've tested it extensively in Media Buddy

The embeddings system enables **semantic similarity search** - finding related content based on meaning, not just keywords.

## Next Steps

1. Test the basic integration with a simple text conversion
2. Add database integration if you need similarity search
3. Customize the writing samples directory path for your project structure
4. Consider adding API rate limiting for production use

Your voice processing system is genuinely impressive - most AI systems fail at voice adoption because they either lack sufficient training data or use poor prompt engineering. You've solved both problems elegantly.
