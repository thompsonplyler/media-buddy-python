# Media Buddy

**Transform news articles into personalized, voiced content with AI-powered voice adoption and visual timelines.**

## 1. Overview

Media Buddy is a Flask-based AI pipeline that learns your personal writing style and generates content that authentically matches your voice. It combines news analysis, prompt responses, timeline generation, and multimedia production into a comprehensive content creation system.

### Key Features

- **Voice Adoption**: Uses your personal writing samples to generate content in your authentic style
- **News Analysis**: Fetches full articles (not snippets) to generate your response
- **Custom Prompts**: Responds to any query in your voice, not just news topics
- **Visual Timelines**: Converts text into structured scene descriptions with duration estimates
- **Image Generation**: Creates styled images from timelines using 15+ visual themes
- **Video Production**: Composes final videos with professional layout control

### Core Workflows

1. **News Response**: `flask generate-voice-response "topic"` → Your analysis of current events
2. **Custom Prompts**: `flask voice-respond --query "question"` → Your response to any prompt
3. **Complete Production**: Text → Timeline → Images → Video

## 2. Requirements and Prerequisites

### Software Requirements

- **Python 3.10+** (Tested on Python 3.10.11)
- **PostgreSQL 14+** with **pgvector extension** compiled and installed
- **Git** for repository cloning
- **Windows PowerShell** (All examples use PowerShell syntax)

### Hardware Recommendations

- **RAM**: 8GB+ (AI models are memory-intensive)
- **GPU**: CUDA-compatible GPU recommended (automatically falls back to CPU)
- **Storage**: 2GB+ for models and generated content
- **Network**: Stable internet connection for news scraping

### API Keys Required

_These are notes for current configuration of AI and news services. System will eventually be compatible with OpenAI and Claude_

- **Gemini API Key** (Google AI Studio) - Required for voice generation
- **News API Key** (newsapi.org) - Optional, for alternative news source
- **Replicate API Key** - Required for image generation

### Personal Content Required

You must provide substantial personal writing samples (50KB+ recommended):

- Personal essays, blog posts, social media content
- Political opinions, reviews, personal reflections
- Any authentic writing that represents your voice and style

_My writing samples included ~20 recent comments I've made that I felt capture my written voice most accurately as well as an exhaustive AI-generated "POV" document that describes my position on everyting from alternative economic systems to least favorite foods._

## 3. Installation and Verification

### Step 1: Clone and Setup Environment

_Instructions are specific to PowerShell installation, but similar steps should work for Mac/Linux configurations so long as requirements are met._

```powershell
git clone <your-repo-url>
cd media-buddy
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install
```

### Step 2: Create Voice Sample Directory

```powershell
# Create the directory (excluded from git for privacy)
mkdir private\writing_style_samples

# Add your personal writing samples as .md files
# Structure: private/writing_style_samples/essay1.md, opinion2.md, etc.
```

### Step 3: Environment Configuration

Create `.env` file in project root:

```bash
# Database
DATABASE_URL=postgresql://username:password@localhost:5432/media_buddy

# Required API Keys
GEMINI_API_KEY=your_gemini_api_key_here

# Optional API Keys
NEWS_API_KEY=your_news_api_key_here
REPLICATE_API_TOKEN=your_replicate_token_here

# Service Configuration
ARTICLE_SERVICE=googlenews
```

### Step 4: Database Setup

```powershell
# Initialize database and create tables
flask init-db
```

### Step 5: Verification

```powershell
# Test basic voice response (requires writing samples)
flask voice-respond --query "What's your take on technology?" --length 100

# Test news analysis (requires API keys)
flask generate-voice-response "artificial intelligence" --length 100

# Check database connection
python -c "from src.media_buddy.extensions import db; print('Database connected successfully')"
```

## 4. Using the App

### 4.1 News Topic Analysis

Generate your response to current news events:

```powershell
# Basic news analysis
flask generate-voice-response "climate change policy"

# Detailed analysis with more sources
flask generate-voice-response "AI regulation debate" --length 200 --top-articles 5
```

**Output**: Saves to `private/writing_style_samples/test/` with source attribution.

### 4.2 Custom Prompt Responses

Generate responses to any question or prompt:

```powershell
# Simple prompt
flask voice-respond --query "What's your philosophy on work-life balance?"

# Build on previous response
flask voice-respond --query "How does this apply to remote work?" --context-file "previous_response.txt"

# Longer response
flask voice-respond --query "Your thoughts on AI in creative work" --length 300
```

**Output**: Saves to `private/writing_style_samples/output/enhanced_scripts/`

### 4.3 Timeline Generation

Convert any text file into visual timelines:

```powershell
# Preview timeline without saving to database
flask generate-timeline-from-file --file-path "content.txt" --preview-only

# Create timeline and save to database for image generation
flask generate-timeline-from-file --file-path "content.txt" --title "My Analysis"
```

**Output**: Database entry with scene breakdown, duration estimates, and visual descriptions.

### 4.4 Image Generation

Create styled images from timelines:

```powershell
# Generate images with a visual theme
flask timeline-approve --article-id 123 --theme retro_anime_80s

# Preview timeline before generating images
flask timeline-approve --article-id 123 --theme cyberpunk_neon --preview-only
```

**Available Themes**: `retro_anime_80s`, `cyberpunk_neon`, `watercolor_soft`, `noir_dramatic`, `abstract_geometric`, `van_gogh`, `pixel_art`, `cosmic_horror`

### 4.5 Video Production

Create complete video compositions:

```powershell
# Final video composition (your recording on top, images below)
flask video-compose --article-id 123 --video-file "my_recording.mov"
```

**Output**: Professional video layout in `instance/output/123/`

### 4.6 Complete Production Workflow

End-to-end content creation:

```powershell
# 1. Create story with your thoughts + news context
flask story-create --story-file "my_thoughts.txt" --news-query "AI breakthroughs"

# 2. Generate enhanced script with timeline and duration estimates
flask script-generate --article-id 123

# 3. Create styled images (shows complete timeline first)
flask timeline-approve --article-id 123 --theme retro_anime_80s

# 4. Compose final video
flask video-compose --article-id 123 --video-file "recording.mov"
```

### 4.7 Configuration Options

#### Switch Content Sources

```powershell
# Use Google News + full content scraping (recommended)
$env:ARTICLE_SERVICE = "googlenews"

# Use NewsAPI (faster, but limited to snippets)
$env:ARTICLE_SERVICE = "newsapi"
```

#### Adjust Response Length

```powershell
--length 125    # ~60-second audio (speaking pace: 150 words/minute)
--length 175    # ~90-second audio
--length 250    # ~2-minute audio
```

### 4.8 File Organization

The system automatically organizes outputs:

```
media-buddy/
├── private/
│   └── writing_style_samples/     # Your personal writing (RAG component)
│       ├── test/                  # News response outputs
│       └── output/enhanced_scripts/ # Voice-respond outputs
├── instance/
│   ├── images/[article_id]/       # Generated images
│   ├── text/[article_id]/         # Script files
│   └── output/[article_id]/       # Final videos
```

### 4.9 Development and Testing Commands

```powershell
# Check workflow status
flask story-status --article-id 123

# Test image generation
flask test-image --prompt "A futuristic cityscape"

# Test archive content extraction
flask test-archive --verbose

# Test database connection
python -c "import torch; print('CUDA available:', torch.cuda.is_available())"
```

## 5. Troubleshooting

### 5.1 Common Setup Issues

**Issue**: `ImportError: No module named 'pgvector'`

- **Solution**: Ensure pgvector extension is compiled and installed in PostgreSQL
- **Reference**: [Official pgvector installation guide](https://github.com/pgvector/pgvector#installation)

**Issue**: `No writing style samples found`

- **Solution**:
  - Ensure `private/writing_style_samples/` directory exists
  - Add `.md` files with your personal writing (aim for 50KB+ total)
  - Verify files contain substantial, authentic writing samples

**Issue**: `Database connection failed`

- **Solution**:
  - Verify PostgreSQL is running
  - Check `DATABASE_URL` in `.env` file
  - Ensure database exists: `createdb media_buddy`

### 5.2 Runtime Issues

**Issue**: `GEMINI_API_KEY not found`

- **Solution**:
  - Get API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
  - Add to `.env` file: `GEMINI_API_KEY=your_key_here`
  - Restart application after adding key

**Issue**: Content extraction failures (normal ~40% failure rate)

- **Expected**: Google News + Archive.is has ~60% success rate
- **Solution**: System automatically tries multiple sources; no action needed

**Issue**: CUDA errors on image generation

- **Solution**: System automatically falls back to CPU processing
- **Check**: `python -c "import torch; print(torch.cuda.is_available())"`

**Issue**: PowerShell command syntax errors

- **Solution**: All commands use PowerShell syntax (`$env:VAR = "value"`)
- **Do not use**: Bash/Linux syntax (`export VAR=value`)

### 5.3 Performance Issues

**Issue**: Slow response generation

- **Check**: Writing samples are substantial but not excessive (50-100KB optimal)
- **Check**: Internet connection for news fetching
- **Check**: GPU availability for faster processing

**Issue**: Image generation timeouts

- **Solution**: Replicate API has rate limits; wait and retry
- **Alternative**: Use `--preview-only` flag to test timelines without generating images

### 5.4 Content Quality Issues

**Issue**: Generated content doesn't match your voice

- **Solution**:
  - Add more diverse writing samples (opinions, personal essays, reviews)
  - Ensure samples represent authentic voice, not formal writing
  - Include emotional and personal content, not just factual writing

**Issue**: Timeline scenes are poorly described

- **Solution**: Original content should be descriptive and narrative-focused
- **Check**: Use higher `--length` parameter for more detailed content

### 5.5 Getting Help

For additional support:

- **pgvector setup**: [Official pgvector documentation](https://github.com/pgvector/pgvector)
- **API quotas**: Check Google AI Studio and Replicate dashboards
- **Performance**: Verify GPU availability and memory usage
- **Voice quality**: Ensure writing samples are substantial and representative

---

**System Requirements Summary**: This system requires substantial personal writing samples to function effectively. Voice adoption quality directly correlates with the quantity and authenticity of your training data.
