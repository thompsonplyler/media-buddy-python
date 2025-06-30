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

**IMPORTANT**: This project is developed and tested on **Windows PowerShell**. All command examples use PowerShell syntax (`$env:VARIABLE = "value"`).

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

### Collaborative Writing Workflow (NEW!)

Media Buddy now features a sophisticated collaborative writing workflow that combines human perspective with AI enhancement:

```powershell
# 1. Discover and create articles with full content (not snippets!)
flask discover-story "artificial intelligence breakthroughs"
flask create-article --query "artificial intelligence breakthroughs" --auto

# 2. Initialize workflow state management
flask workflow-init --article-id 1

# 3. Add your unique perspective to the story
flask contribute-take --article-id 1

# 4. AI enhances your contribution while preserving your voice
flask enhance-writing --article-id 1 --length 200

# 5. Generate visual timeline from enhanced content
flask generate-enhanced-timeline --article-id 1

# 6. Create images and assemble final assets
flask process-visuals --article-id 1 --theme retro_anime_80s
flask assemble-final --article-id 1
```

**Key Benefits:**

- **Human-AI Collaboration**: Your unique perspective + AI enhancement
- **Full Content**: 4,000-8,900 character articles via Archive.is fallback
- **Workflow State Management**: Persistent state across CLI commands
- **Modular Design**: Each phase can be run independently

### 🚀 Streamlined Turnkey Workflow (NEWEST!)

For maximum efficiency, use the new 5-command turnkey workflow that takes you from story idea to final video:

```powershell
# 1. Create story from your preliminary text + 3 reliable news articles
flask story-create --story-file "my_story.txt" --news-query "AI breakthroughs" --title "My AI Analysis"

# 2. Generate Thompson's enhanced script with timeline and duration estimates
flask script-generate --article-id 123 --length 200

# 3. Review complete timeline and generate styled images (shows full text + visuals)
flask timeline-approve --article-id 123 --theme retro_anime_80s

# 4. Final video composition (video on TOP, images on BOTTOM)
flask video-compose --article-id 123 --video-file "my_recording.mov"

# 5. Track progress and manage workflows
flask story-status --article-id 123
```

**Key Features:**

- **Complete Visibility**: Step 3 shows the entire timeline with text content and visual descriptions
- **Duration Analysis**: Automatic timing estimates (150 words/minute) for precise video planning
- **Video Layout Control**: Recorded video prominently displayed on top with slideshow images below
- **Story-First Approach**: Your preliminary story drives the narrative, enhanced with relevant news context
- **Turnkey Process**: Each command tells you exactly what to run next

**⚠️ Voice Generation Setup**: Since `private/writing_style_samples/` is gitignored, you must:

1. **Create the directory**: `mkdir -p private/writing_style_samples`
2. **Add your writing samples**: Save personal essays, blog posts, and writing samples as `.md` files
3. **Aim for 50KB+ total content**: More samples = better voice adoption
4. **Include diverse content**: Political opinions, reviews, personal reflections for authentic voice capture

### Archive.is Enhancement (Breakthrough!)

For maximum content quality, use the Archive.is enhancement pipeline:

```powershell
# Automatically enhance snippet articles with full content from Archive.is
flask archive-enhance "breaking news topic" --count 3 --verbose
```

This command discovers articles, identifies snippets, and uses Archive.is/Wayback Machine to retrieve full content, often increasing article length by 20-40x.

### Legacy Pipeline Commands

For traditional automated processing:

```powershell
# Complete automated pipeline (bypasses collaborative workflow)
flask process-story --query "topic" --theme "retro_anime_80s" --length 200

# Individual legacy commands
flask fetch-news "artificial intelligence"
flask process-articles
flask generate-voiced-summary --article-id 1 --length 125
flask generate-timeline --article-id 1
```

### Development and Testing Commands

```powershell
# Test image generation with custom prompts
flask test-image --prompt "A futuristic cityscape at sunset"

# Test Archive.is content extraction
flask test-archive --verbose

# Check workflow status
flask workflow-status --article-id 1
flask workflow-status --list-all

# Video generation (requires FFmpeg)
flask create-video --article-id 1
flask compose-video --input-dir "instance/output/1" --width 1080 --height 1920
```

## 🧠 How It Works

### Collaborative Writing Workflow Architecture

Media Buddy implements a sophisticated 6-phase collaborative workflow that combines human insight with AI enhancement:

**Phase 1: Discovery**

- **Google News RSS**: Discovers articles from 100+ quality sources
- **Archive.is Integration**: Retrieves full content when initial sources provide only snippets
- **Content Validation**: Ensures substantial article content (4,000-8,900 characters)

**Phase 2: User Contribution**

- **Human Perspective**: User adds their unique take, analysis, or opinion
- **Flexible Input**: Write directly or load from files
- **Content Templates**: Guided prompts help structure contributions

**Phase 3: AI Enhancement**

- **Voice Preservation**: AI enhances content while maintaining user's authentic voice
- **Style Context**: Uses personal writing samples for consistency
- **Length Control**: Configurable output length for different media formats

**Phase 4: Timeline Generation**

- **Scene Breakdown**: Converts enhanced content into visual scene descriptions
- **Narrative Structure**: Maintains story flow and pacing
- **Image Optimization**: Descriptions optimized for text-to-image generation

**Phase 5: Visual Processing**

- **Multi-stage Image Generation**: Raw generation → theme stylization
- **15+ Visual Themes**: From cinematic to retro anime aesthetics
- **Scene Intelligence**: Differentiates user-focused vs. general scenes

**Phase 6: Final Assembly**

- **Asset Organization**: Structured output for multimedia production
- **Metadata Tracking**: Complete workflow history and statistics
- **Export Ready**: Optimized for video composition and social media

### The Content Acquisition Breakthrough

Traditional systems were limited to 214-character snippets. Media Buddy's multi-tier approach provides:

1. **Primary Discovery**: Google News RSS with source quality rankings
2. **Archive.is Fallback**: Retrieves full content from archived versions
3. **Wayback Machine**: Secondary fallback for maximum content coverage
4. **Bot Detection Resilience**: Graceful handling of anti-scraping measures

**Result**: 20-40x more content than snippet-based systems with 60%+ success rate.

### Workflow State Management

Each article progresses through tracked phases with persistent state:

- **Database-Driven**: State restored from article data across CLI commands
- **Phase Validation**: Prevents out-of-order execution
- **Recovery Support**: Workflows can be resumed from any point
- **Progress Tracking**: Clear visibility into completion status

### The Technical Stack

- **Content Acquisition**: Google News RSS + Archive.is + Wayback Machine via Playwright
- **Workflow Orchestration**: PipelineOrchestrator with database-driven state management
- **AI Enhancement**: Gemini API with collaborative writing prompts
- **Embeddings**: sentence-transformers with `all-MiniLM-L6-v2` model (384 dimensions)
- **Vector Storage**: PostgreSQL with pgvector extension for semantic search
- **Image Generation**: Replicate API with FLUX models and theme stylization
- **Video Composition**: FFmpeg integration for multimedia assembly
- **Performance**: GPU acceleration, lazy loading, modular service architecture

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
