# Media Buddy

**A Flask-based AI pipeline that transforms news articles into personalized, voiced content using sophisticated prompt engineering and vector embeddings.**

Media Buddy fetches news articles, processes them through multiple AI stages, and outputs content that authentically matches your personal writing style.

## 🎯 Project Purpose

Media Buddy solves the **"AI voice adoption problem"** that most systems struggle with. Instead of generic AI-generated content, it:

- **Learns Your Voice**: Uses 70KB+ of personal writing samples to understand your unique style, tone, and perspective
- **Separates Style from Content**: Sophisticated prompt engineering that captures _how_ you write, not _what_ you write about
- **Generates Semantic Embeddings**: Creates 384-dimensional vectors for intelligent content similarity and search
- **Builds Visual Timelines**: Converts text into structured visual scene descriptions for multimedia projects

The core innovation is a 7-step pipeline that transforms raw news into personalized, voiced content while maintaining semantic understanding through vector embeddings.

## 🔧 System Requirements

### Required Software (Must Install First)

1. **Python 3.10+** (Tested on Python 3.10.11)
2. **PostgreSQL 14+** with **pgvector extension**
   - pgvector must be compiled and installed on your system
   - See [pgvector installation guide](https://github.com/pgvector/pgvector#installation)
3. **Git** (for cloning the repository)

### Hardware Recommendations

- **GPU**: CUDA-compatible GPU recommended for faster embedding generation (automatically falls back to CPU)
- **RAM**: 8GB+ recommended (AI models and vector processing are memory-intensive)
- **Storage**: 2GB+ for models and generated content

## 🚀 Quick Start

### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd media-buddy

# Create and activate virtual environment as appropriate for your
# environment. This is for Windows PowerShell commands
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 2. Critical: Setup RAG Component (Writing Style Samples)

**⚠️ Important**: The RAG folder (`private/writing_style_samples/`) is excluded from git for privacy. You must create it manually.

**What to include**:

- Personal essays, blog posts, social media content
- Political opinions, book reviews, personal reflections
- Aim for 50KB+ total content for best voice adoption results
- Save as `.md` files with descriptive names

### 3. Environment Configuration

Create a `.env` file in the project root:

```bash
# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/media_buddy

# API Keys
GEMINI_API_KEY=your_gemini_api_key_here
NEWS_API_KEY=your_news_api_key_here

# Optional: Hugging Face for additional models
HF_API_KEY=your_huggingface_key_here
```

### 4. Database Setup

```bash
# Initialize database and create tables
flask init-db

# This creates all tables including vector column for embeddings
# Requires pgvector extension to be installed in PostgreSQL
```

## 📖 Usage

### Core Pipeline Commands

Media Buddy works as a sequential pipeline. Each command builds on the previous:

```bash
# 1. Fetch news articles from API
flask fetch-news "artificial intelligence"

# 2. Generate summaries and vector embeddings
flask process-articles

# 3. Convert summaries to your personal voice
flask generate-voiced-summary --article-id 1 --length 250

# 4. Create visual timeline from voiced content
flask generate-timeline --article-id 1

# 5. Generate images for each scene (requires additional setup)
flask source-images --article-id 1
flask generate-raw-images --article-id 1
flask stylize-images --article-id 1 --theme cinematic

# 6. Full pipeline (all steps at once)
flask process-story --query "climate change" --theme documentary --length 300
```

### Voice Processing Examples

```bash
# Test voice adoption on custom text
flask generate-voice --text "Your original text here" --length 250

# Generate embeddings for similarity search
flask generate-embedding --text "Some text to embed"

# Process existing database records
flask voice-process-db --record-id 1 --length 250
```

## 🧠 How It Works

### The Voice Adoption Breakthrough

Most AI voice systems fail because they either lack sufficient training data or mix style with content. Media Buddy solves this with:

1. **Massive Training Data**: Your personal writing samples (50KB+ recommended)
2. **Smart Prompt Engineering**: Separates STYLE from CONTENT

This prevents AI from injecting irrelevant personal details while capturing your authentic voice.

### The Technical Stack

- **Voice Processing**: Gemini API with sophisticated prompts
- **Embeddings**: sentence-transformers with `all-MiniLM-L6-v2` model
- **Vector Storage**: PostgreSQL with pgvector extension (384 dimensions)
- **Image Generation**: Replicate API with FLUX models
- **Performance**: Lazy loading, caching, GPU acceleration where available

## 🔍 Key Features

### 1. **Voice Adoption System**

- Reads personal writing samples from `private/writing_style_samples/`
- Uses Gemini API with carefully crafted prompts
- Maintains authentic voice while writing about any topic
- Separates writing style from specific content

### 2. **Semantic Embeddings**

- Generates 384-dimensional vectors using sentence-transformers
- Enables similarity search and content clustering
- Stored in PostgreSQL with pgvector for efficient querying
- Supports cosine distance calculations

### 3. **Visual Timeline Generation**

- Converts text into structured scene descriptions
- Optimized for text-to-image generation
- Automatically detects user-focused vs. general scenes
- Outputs clean JSON for multimedia applications

### 4. **Modular Architecture**

- Each processing step is a separate Flask CLI command
- Idempotent operations (safe to re-run)
- Clear logging and error handling
- Easy to integrate into larger workflows

## 🛠️ Advanced Configuration

### Custom Embedding Models

```python
# In your environment or config
EMBEDDING_MODEL="all-mpnet-base-v2"  # Higher quality, larger model
# or
EMBEDDING_MODEL="all-MiniLM-L6-v2"   # Default, good balance
```

### GPU Acceleration

The system automatically detects and uses CUDA if available:

```bash
# Check GPU availability
python -c "import torch; print(torch.cuda.is_available())"
```

### Performance Tuning

- **Lazy Loading**: Models load only when first used
- **Caching**: Writing samples cached after first read
- **Batch Processing**: Process multiple articles efficiently
- **Memory Management**: Automatic cleanup of large models

## 🔧 Troubleshooting

### Common Issues

1. **"pgvector extension not found"**

   - Install pgvector: `git clone https://github.com/pgvector/pgvector.git && cd pgvector && make && make install`
   - Create extension: `CREATE EXTENSION vector;` in your database

2. **"Writing style samples directory not found"**

   - Create `private/writing_style_samples/` directory
   - Add your personal writing as `.md` files
   - Ensure files contain substantial content (10KB+ each recommended)

3. **"Gemini API key required"**

   - Get API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Set `GEMINI_API_KEY` environment variable

4. **Memory issues during processing**
   - Reduce batch sizes in processing commands
   - Use CPU-only mode: `export CUDA_VISIBLE_DEVICES=""`
   - Consider upgrading RAM or using cloud instance

### Performance Tips

- Use GPU acceleration for faster embedding generation
- Batch process multiple articles together
- Cache frequently used models
- Monitor memory usage during large processing jobs

## 📁 Project Structure

```
media-buddy/
├── src/media_buddy/           # Core application modules
│   ├── text_processor.py     # Voice adoption & embeddings
│   ├── models.py             # Database models
│   ├── routes.py             # Web routes (optional)
│   └── ...
├── private/                   # Excluded from git
│   ├── writing_style_samples/ # Your personal writing (RAG component)
│   ├── customization/        # Project configuration
│   └── ...
├── instance/                  # Runtime data (images, etc.)
├── migrations/               # Database migrations
├── requirements.txt          # Python dependencies
└── run.py                   # Flask application entry point
```

## 🤝 Contributing

This is a personal AI system designed around specific writing samples and use cases. The core voice processing technology (`voice_processor_package.py`) is designed to be portable to other projects.

## 📄 License

MIT

## 🙋 Support

For issues related to:

- **pgvector setup**: See [official pgvector docs](https://github.com/pgvector/pgvector)
- **Voice adoption quality**: Ensure writing samples are substantial and representative
- **Performance**: Check GPU availability and memory usage
- **API keys**: Verify Gemini API key and quotas

---

**Note**: This system requires substantial personal writing samples to function effectively. The voice adoption quality directly correlates with the quantity and authenticity of your training data.
