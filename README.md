# Media Buddy

**A Flask-based AI pipeline that transforms news articles into personalized, voiced content using sophisticated prompt engineering and vector embeddings.**

Media Buddy fetches full news articles (not just snippets), processes them through multiple AI stages, and outputs content that authentically matches your personal writing style.

## 🎯 Project Purpose

Media Buddy solves the **"AI voice adoption problem"** that most systems struggle with. Instead of generic AI-generated content, it:

- **Learns Your Voice**: Uses 70KB+ of personal writing samples to understand your unique style, tone, and perspective
- **Separates Style from Content**: Sophisticated prompt engineering that captures _how_ you write, not _what_ you write about
- **Fetches Full Articles**: Uses Google News + Playwright scraping to get complete article content (4,000-8,900 characters vs 214-character snippets)
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
4. **Playwright** (for web scraping full articles)
   - Automatically installs browser binaries on first use

### Hardware Recommendations

- **GPU**: CUDA-compatible GPU recommended for faster embedding generation (automatically falls back to CPU)
- **RAM**: 8GB+ recommended (AI models and vector processing are memory-intensive)
- **Storage**: 2GB+ for models and generated content
- **Network**: Stable internet connection for news scraping (some sites implement bot detection)

### Development Environment

**IMPORTANT**: This project is developed and tested on **Windows PowerShell**. All command examples use PowerShell syntax (`$env:VARIABLE = "value"`). Thompson (the primary user) prefers to execute all terminal commands himself rather than having AI assistants run them.

## 🚀 Quick Start

### 1. Clone and Setup

```powershell
git clone <your-repo-url>
cd media-buddy

# Create and activate virtual environment (Windows PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (required for news scraping)
playwright install
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

# Article Service Configuration
ARTICLE_SERVICE=googlenews  # Options: 'newsapi' or 'googlenews'

# Optional: Hugging Face for additional models
HF_API_KEY=your_huggingface_key_here
```

### 4. Database Setup

```powershell
# Initialize database and create tables
flask init-db

# This creates all tables including vector column for embeddings
# Requires pgvector extension to be installed in PostgreSQL
```

## 📖 Usage

### End-to-End Pipeline (NEW!)

The complete pipeline now runs with a single command using our new modular architecture:

```powershell
# Set Google News service and run complete pipeline
$env:ARTICLE_SERVICE = "googlenews"
flask process-story --query "artificial intelligence breakthroughs" --theme "retro_anime_80s" --length 125
```

This command:

1. **Fetches** full articles from Google News (not snippets!)
2. **Generates** voiced summary directly from full content (bypasses problematic BART step)
3. **Creates** visual timeline with scene descriptions
4. **Sources** and generates raw images for each scene
5. **Stylizes** images with chosen theme
6. **Outputs** final script and images to `instance/output/{article_id}/`

### Individual Pipeline Commands

For step-by-step processing or debugging:

```powershell
# 1. Fetch news articles (now gets full content, not snippets)
flask fetch-news "artificial intelligence"

# 2. Generate summaries and vector embeddings
flask process-articles

# 3. Convert summaries to your personal voice
flask generate-voiced-summary --article-id 1 --length 125

# 4. Create visual timeline from voiced content
flask generate-timeline --article-id 1

# 5. Generate images for each scene
flask source-images --article-id 1
flask generate-raw-images --article-id 1
flask stylize-images --article-id 1 --theme retro_anime_80s
```

### Voice Processing Examples

```powershell
# Test voice adoption on custom text
flask generate-voice --text "Your original text here" --length 125

# Generate embeddings for similarity search
flask generate-embedding --text "Some text to embed"

# Process existing database records
flask voice-process-db --record-id 1 --length 125
```

## 🧠 How It Works

### The Complete Pipeline Architecture

**NEW**: The pipeline now uses a modular service architecture that eliminates the problematic "snippet limitation" entirely:

1. **Google News RSS Discovery**: Finds articles from 100+ quality sources with reliability rankings
2. **Playwright Content Extraction**: Gets full 4,000-8,900 character articles (20-40x more than snippets)
3. **Direct Voice Generation**: Bypasses BART summarization, goes straight from full content to Thompson's voice
4. **Timeline Creation**: Converts voiced content to visual scene descriptions
5. **Image Generation**: Uses Replicate API with FLUX models and theme stylization
6. **Asset Assembly**: Outputs script + stylized images ready for multimedia use

### The Content Acquisition Breakthrough

Previous systems were limited to 214-character snippets from APIs. Media Buddy now uses:

1. **Google News RSS**: Discovers articles from diverse, high-quality sources
2. **Intelligent Source Filtering**: Prioritizes reliable news sources with quality rankings
3. **Playwright Web Scraping**: Extracts full article content (4,000-8,900 characters)
4. **Bot Detection Handling**: Gracefully handles CAPTCHA and anti-bot measures with 60% success rate

This provides 20-40x more content than snippet-based systems while maintaining source diversity.

### The Voice Adoption System

Most AI voice systems fail because they either lack sufficient training data or mix style with content. Media Buddy solves this with:

1. **Massive Training Data**: Your personal writing samples (50KB+ recommended)
2. **Smart Prompt Engineering**: Separates STYLE from CONTENT
3. **Style Learning**: Captures and learns from your edits to improve consistency
4. **Direct Processing**: No intermediate summarization step to lose nuance

This prevents AI from injecting irrelevant personal details while capturing your authentic voice.

### The Technical Stack

- **Content Acquisition**: Google News RSS + Playwright web scraping
- **Voice Processing**: Gemini API with sophisticated prompts
- **Embeddings**: sentence-transformers with `all-MiniLM-L6-v2` model
- **Vector Storage**: PostgreSQL with pgvector extension (384 dimensions)
- **Image Generation**: Replicate API with FLUX models
- **Performance**: Lazy loading, caching, GPU acceleration where available

## 🔍 Key Features

### 1. **End-to-End Pipeline**

- **Single Command Execution**: Complete pipeline from query to final assets
- **Modular Architecture**: Each step can be run independently for debugging
- **Service Abstraction**: Easy switching between content sources via environment variables
- **Error Recovery**: Graceful handling of bot detection and content extraction failures

### 2. **Full-Content News Acquisition**

- **Google News Integration**: Discovers articles from 100+ quality sources
- **Web Scraping**: Extracts complete article text using Playwright
- **Source Quality Ranking**: Prioritizes reliable sources (Reuters, AP, BBC, etc.)
- **Bot Detection Resilience**: Handles anti-scraping measures gracefully
- **Fallback Support**: Automatically switches between NewsAPI and Google News

### 3. **Voice Adoption System**

- Reads personal writing samples from `private/writing_style_samples/`
- Uses Gemini API with carefully crafted prompts
- Maintains authentic voice while writing about any topic
- Separates writing style from specific content
- **Style Learning**: Captures improvements from your edits

### 4. **Semantic Embeddings**

- Generates 384-dimensional vectors using sentence-transformers
- Enables similarity search and content clustering
- Stored in PostgreSQL with pgvector for efficient querying
- Supports cosine distance calculations

### 5. **Visual Timeline Generation**

- Converts text into structured scene descriptions
- Optimized for text-to-image generation
- Automatically detects user-focused vs. general scenes
- Outputs clean JSON for multimedia applications

### 6. **Image Generation & Stylization**

- **Multiple Themes**: 15+ visual styles from cinematic to retro anime
- **Two-Stage Process**: Raw generation → theme stylization
- **Scene Intelligence**: Detects user-focused vs general scenes
- **Asset Management**: Organized output structure for final assembly

## 🛠️ Advanced Configuration

### Article Service Selection

Switch between content sources via environment variable (PowerShell syntax):

```powershell
# Use Google News + Playwright (recommended for full content)
$env:ARTICLE_SERVICE = "googlenews"

# Use NewsAPI (faster but limited to snippets)
$env:ARTICLE_SERVICE = "newsapi"
```

### Content Quality Tuning

The Google News service includes intelligent filtering:

- **Source Rankings**: Tier 1 (Reuters, AP) to Tier 4 (smaller outlets)
- **Content Validation**: Automatically detects and skips CAPTCHA/bot pages
- **Success Rate**: ~60% of articles successfully extracted with full content
- **Fallback Handling**: Graceful degradation when scraping fails

### Voice Generation Optimization

For different use cases, adjust the length parameter:

```powershell
# 60-second audio (recommended)
--length 125

# 90-second audio
--length 175

# 2-minute audio
--length 250
```

**Speaking pace**: ~150-175 words per minute average conversational pace.

### Custom Embedding Models

```python
# In your environment or config
EMBEDDING_MODEL="all-mpnet-base-v2"  # Higher quality, larger model
# or
EMBEDDING_MODEL="all-MiniLM-L6-v2"   # Default, good balance
```

### GPU Acceleration

The system automatically detects and uses CUDA if available:

```powershell
# Check GPU availability
python -c "import torch; print(torch.cuda.is_available())"
```

## 🎨 Available Themes

Choose from 15+ visual styles for image generation:

- `default` - Cinematic, dramatic lighting
- `retro_anime_80s` - 80s sci-fi anime style
- `holographic_glitch` - Neon cyberpunk aesthetics
- `modern_noir` - High-contrast black and white
- `van_gogh` - Impressionist painting style
- `pixel_art` - 16-bit retro game style
- `cosmic_horror` - Lovecraftian atmosphere
- And many more...

## 🔧 Troubleshooting

### Common Issues

1. **CUDA Errors**: Usually caused by BART trying to process CAPTCHA pages instead of real articles. The new pipeline bypasses this issue.

2. **Service Configuration**: Ensure `ARTICLE_SERVICE` environment variable is set correctly in PowerShell:

   ```powershell
   $env:ARTICLE_SERVICE = "googlenews"
   ```

3. **Content Extraction Failures**: Normal with ~60% success rate. Google News provides multiple article sources automatically.

4. **PowerShell vs Bash**: All examples use PowerShell syntax. Do not use Linux/Mac command formats.

## 📊 Performance Metrics

- **Content Quality**: 4,000-8,900 characters per article (20-40x improvement over snippets)
- **Success Rate**: 60% extraction success with substantial content
- **Source Diversity**: 100+ news sources with quality rankings
- **Voice Authenticity**: Sophisticated prompt engineering captures writing style nuances
- **Pipeline Speed**: Complete end-to-end processing in under 10 minutes

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
