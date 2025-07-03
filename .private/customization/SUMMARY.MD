# Media Buddy - Project Summary & Lessons Learned

## Project Goal

"Media Buddy" is a Flask-based application designed to build a 7-step pipeline that transforms news articles into various media formats. This project is a spiritual successor to "job-commando" and aims to leverage lessons learned from previous development cycles.

The core pipeline is:

1.  Fetch news articles from an API.
2.  Process and store the articles, including generating text summaries and vector embeddings.
3.  (Future steps to be defined)

---

## Lessons Learned & Troubleshooting Guide

This section is crucial for guiding future development and for onboarding new developers (or reminding our future selves) of the non-obvious challenges we've already solved.

### 1. The `pgvector` and PostgreSQL on Windows Gauntlet

**Context:** A significant portion of the initial project setup was dedicated to correctly installing, compiling, and configuring the `pgvector` extension for PostgreSQL on a Windows development machine.

**Faulty Assumptions vs. Reality:**

- **Assumption:** Installing `pgvector` would be a simple `pip install pgvector` and adding the extension in PostgreSQL.
- **Reality:** `pgvector` requires compilation from source on Windows, which depends on a specific, non-default component of Visual Studio: the C++ build tools (`nmake.exe`). This led to a multi-day troubleshooting process involving Visual Studio Installer, environment variables (`vcvarsall.bat`), and discovering compiler/linker errors.

- **Assumption:** The `DATABASE_URL` in our `.env` file pointed to the database we were actively managing in `psql`.
- **Reality:** We were meticulously enabling the `vector` extension in a `media_buddy` database while the `.env` file still pointed to the old `job_commando` database. This caused the classic `type "vector" does not exist` error, which sent us on a wild goose chase, suspecting our Python code or SQLAlchemy models.

- **Assumption:** A newer version of PostgreSQL (17) would be stable.
- **Reality:** The initial version of PostgreSQL 17 had a known linker bug that prevented `pgvector` from compiling correctly. The solution was to upgrade to a patched version (17.3+).

**Key Takeaways & Protocol:**

1.  **Verify Environment First:** Before debugging application code, _always_ verify the environment. For database issues, create a simple, temporary script (`check_env.py`) to load the application's configuration and print the exact `DATABASE_URL`. This is the only source of truth.
2.  **Activate Extensions Manually & Specifically:** The `CREATE EXTENSION vector;` command must be run _inside the specific database the application connects to_. It is not a global setting.
3.  **Use a Robust `init-db` Command:** Don't just rely on `db.create_all()`. Create a Flask CLI command that explicitly drops all tables, creates them again, and then runs `CREATE EXTENSION IF NOT EXISTS vector;`. This makes your setup idempotent and resilient to schema changes.
4.  **For a detailed walkthrough of the correct post-compilation setup, see `private/TO-MEDIA-BUDDY/PGVECTOR_IMPLEMENTATION_GUIDE.MD`.**

### 2. Python Environment & Project Structure

- **Faulty Assumption:** We could just start coding.
- **Reality:** The initial project structure, inherited from a previous project, contained circular dependencies and misplaced CLI command definitions. This required a significant refactoring effort:
  - **Circular Imports:** The `db` object caused a loop between `__init__.py` and `models.py`. **Solution:** We created an `extensions.py` file to house the `db = SQLAlchemy()` instance, which both `__init__.py` and `models.py` can import from without issue.
  - **CLI Commands:** Flask CLI commands should be defined and registered within the `create_app` factory function, not in the top-level `run.py`. This ensures they run within the application context.

### 3. Replicate API Integration

- **Context:** Implementing the image-to-image stylization feature required integrating the Replicate API. This process involved a series of cascading errors.
- **Faulty Assumptions vs. Reality:**
  - **Assumption:** The local development environment was not the source of errors. **Reality:** Forgetting to activate the Python `venv` caused misleading PowerShell errors that masked the true problem.
  - **Assumption:** The Replicate Python client's methods could be inferred. **Reality:** We made several incorrect assumptions about how to pass file inputs and handle file outputs, leading to multiple rounds of debugging.
- **Key Takeaway:** The successful solution was found by abandoning complex assumptions and consulting our own project's simple reference snippets (`private/replicate_snippets`). When integrating an external service, **always start with the simplest possible example** and **trust your own documentation**. For a full breakdown, see the "Onion of API Errors" case study in `TROUBLESHOOTING.MD`.

### 4. Collaborative Workflow State Management Crisis & Resolution

- **Context:** After implementing the collaborative writing workflow, users encountered "Cannot add contribution at this time. Current phase: discovery" errors even after workflow initialization.
- **Faulty Assumptions vs. Reality:**
  - **Assumption:** Workflow state would persist across Flask CLI commands in memory. **Reality:** Each Flask command runs in a separate process, so in-memory state was lost between commands.
  - **Assumption:** Database workflow_phase field alone was sufficient for state management. **Reality:** The PipelineOrchestrator needed to reconstruct full workflow state from database fields when not found in memory.
- **Solution:** Enhanced `PipelineOrchestrator.get_workflow_state()` to automatically restore workflow state from database analysis:
  - Has `raw_content` → `USER_CONTRIBUTION` phase
  - Has `user_contribution` → `AI_ENHANCEMENT` phase
  - Has `enhanced_content` → `TIMELINE_GENERATION` phase
  - etc.
- **Key Takeaway:** Flask CLI commands are stateless processes. State management systems must be database-driven with intelligent restoration logic.

### 5. Timeline Generation Enhancement: Text Content Integration

- **Context:** Original timeline generation only provided scene descriptions for image generation, lacking actual text content for timing and narrative analysis.
- **Problem:** Users couldn't analyze speaking duration or understand narrative flow from descriptions alone.
- **Solution:** Enhanced `generate_timeline()` to include four components per scene:
  - `text`: Actual script content (15-25 words per scene)
  - `description`: Visual scene description for image generation
  - `scene`: Scene numbering
  - `is_user_scene`: Personal vs. general scene detection
- **Duration Analysis:** Added automatic timing estimates (150 words/minute) for video production planning.
- **Key Takeaway:** AI-generated timelines need both narrative content AND visual descriptions to be production-ready.

### 6. Video Composition Layout Control Success

- **Context:** Users needed flexible control over video layout, specifically wanting recorded video on TOP rather than BOTTOM of image slideshow.
- **Challenge:** FFmpeg overlay positioning required precise coordinate calculations and filter chain management.
- **Solution:** Modified `VideoCompositor` to:
  - Place recorded video at `y_offset = 0` (top)
  - Position images at `y_offset = scaled_video_height` (bottom)
  - Maintain proper scaling and aspect ratios
- **Result:** Professional video layout with recorded content prominently displayed above supporting visual materials.
- **Key Takeaway:** Video composition flexibility is crucial for different content types and user preferences.

### 7. Archive.is Integration Breakthrough

- **Context:** Traditional news APIs only provided 214-character snippets, limiting content quality for AI enhancement.
- **Solution:** Implemented multi-tier fallback system:
  - Primary: archive.is content extraction
  - Secondary: archive.today fallback
  - Tertiary: Wayback Machine retrieval
- **Results:** 20-40x content increase (from 214 chars to 4,000-8,900 chars) with 60%+ success rate
- **Key Challenge:** Rate limiting (429 errors) from archive.is/archive.today, but Wayback Machine provided reliable fallback.
- **Architecture:** Modular `ArchiveService` inheriting from `ArticleService` with Playwright-based content extraction.
- **Key Takeaway:** Content quality is foundational to AI enhancement. Multi-tier fallback systems provide reliability against web scraping challenges.

### 8. Database Migration Management

- **Context:** Collaborative workflow features required new database columns (`user_contribution`, `enhanced_content`, `workflow_phase`, `workflow_metadata`).
- **Problem:** Migration files existed but weren't applied, causing "column does not exist" errors.
- **Solution:** Proper migration workflow: `flask db upgrade` applies pending migrations.
- **Key Takeaway:** Always check migration status (`flask db current`) before troubleshooting database schema issues.

### 9. Standalone CLI Command Development Success

- **Context:** Implementing `flask voice-respond` command for Thompson's voice generation outside core workflows.
- **Challenge:** Building utility commands that leverage existing infrastructure without interference.
- **Console vs Application Error Distinction:**
  - **Issue:** PowerShell PSReadLine exceptions appeared during long command execution
  - **Reality:** Console rendering issues (cursor positioning) are separate from Flask application functionality
  - **Key Learning:** Don't panic when seeing PSReadLine/console display errors - verify if the actual Flask command succeeded
- **Architectural Success Patterns:**
  - **Reuse Existing Infrastructure:** Leveraged `get_writing_style_examples()` and established Gemini prompting patterns
  - **Complete Isolation:** Built standalone command independent of workflow orchestration
  - **Consistent File Organization:** Used established `private/writing_style_samples/` directory structure
- **Implementation Results:**
  - Zero infrastructure issues due to following established patterns
  - Clean separation from core workflows prevents interference
  - Smooth development cycle with modular architecture approach
- **Key Takeaway:** Utility commands benefit from complete architectural isolation while leveraging existing service layer components. Console display errors don't indicate application failures.

### 10. File-to-Timeline Bridge & Pathway Unification Success

- **Context:** Different content creation pathways (voice-respond files, news articles, user stories) needed unified access to timeline generation and the complete media production pipeline.
- **Challenge:** Bridge file-based content outputs to database-driven workflow system without disrupting existing architecture.
- **Solution Architecture:**
  - **Bridge Function:** `generate_timeline_from_file()` in `text_processor.py` reads any text file and generates timeline using existing `generate_timeline()` function
  - **CLI Integration:** `flask generate-timeline-from-file` command with preview mode and database integration options
  - **Database Compatibility:** Creates pseudo-article entries with `workflow_phase='timeline_generated'` for seamless integration
  - **Content Processing:** Intelligent parsing to extract main content from markdown headers and metadata
- **Pathway Unification Results:**
  - **Pathway A**: Prompt → `voice-respond` → file → timeline → database (COMPLETE)
  - **Pathway B**: News query → database → timeline (existing, maintained)
  - **Pathway C**: News + text file → database → timeline (existing, maintained)
  - **Pathway D**: Prompt + context file → `voice-respond` → timeline → database (COMPLETE)
- **Database Model Learning:**
  - **Issue:** Initial implementation used `created_at=datetime.utcnow()` in NewsArticle constructor
  - **Reality:** NewsArticle model doesn't include `created_at` field in constructor
  - **Solution:** Removed invalid field, letting SQLAlchemy handle timestamp defaults
- **Implementation Success Factors:**
  - **Reused Existing Infrastructure:** Leveraged established `generate_timeline()` function and database patterns
  - **Clean Separation:** Bridge function isolated in text_processor.py without workflow orchestration dependencies
  - **Preview Mode:** Safe testing with `--preview-only` flag before database commits
  - **Complete Integration:** Seamless handoff to existing `timeline-approve` and `video-compose` commands
- **Testing Results:**
  - ✅ Successfully generated 11-17 scene timelines from voice-respond outputs
  - ✅ Database integration working with Article IDs 339 and 340
  - ✅ Complete pathway A and D end-to-end verification
  - ✅ No disruption to existing pathways B and C
- **Key Takeaway:** Architectural bridges can unify disparate content pathways by identifying common interfaces (timeline generation) and following established database patterns. File-based and database-driven systems can coexist seamlessly with proper abstraction layers.

---

_This document should be updated after every major feature implementation or significant troubleshooting session._

---

## Project Roadmap & Milestones

This roadmap outlines the planned development phases for Media Buddy. It defines the discrete steps, their completion criteria, and when we should pause to update this document.

### General Principles

- **When is a feature "complete"?** A feature is considered complete when it is implemented as a self-contained, modular Flask CLI command. The command should perform a single, well-defined task (e.g., `generate-timeline`, `find-images`), using a specific article ID as input, and save its output back to the database or file system. It must include clear logging to indicate success or failure.
- **When do we update `SUMMARY.MD`?** We will update the "Lessons Learned" section after completing any milestone that introduces a new technology (e.g., a new API, a browser tool) or overcomes a significant, unexpected challenge.

---

### Phase 1: Foundation & Core Pipeline (Status: COMPLETED)

This phase involved setting up a stable development environment and building the essential data ingestion and processing backbone of the application.

- **Milestone 1.1: Environment & Dependency Setup**

  - **Task:** Create a stable Python virtual environment and resolve all dependency issues.
  - **"Done" Criteria:** The `requirements.txt` file is clean, includes `pgvector`, and all packages install successfully via `pip install -r requirements.txt`.
  - **Status: ✅ COMPLETED**

- **Milestone 1.2: Database Integration**

  - **Task:** Configure PostgreSQL, compile and install the `pgvector` extension, and connect it to the Flask app.
  - **"Done" Criteria:** The `flask init-db` command runs without error, successfully creating the database schema, including a `Vector` type column.
  - **Status: ✅ COMPLETED**

- **Milestone 1.3: Application Refactoring**

  - **Task:** Restructure the application to eliminate circular dependencies and properly register CLI commands.
  - **"Done" Criteria:** The app runs without import errors. The `db` instance is in `extensions.py`, and CLI commands are in `__init__.py`.
  - **Status: ✅ COMPLETED**

- **Milestone 1.4: Core Data Ingestion & Processing**
  - **Task:** Build the commands to fetch news articles and then process them to generate summaries and vector embeddings.
  - **"Done" Criteria:** `flask fetch-news` populates the database, and `flask process-articles` correctly fills in the `summary` and `embedding` columns for those articles.
  - **Status: ✅ COMPLETED**

---

### Phase 2: Stylized Narrative Generation (Status: ✅ COMPLETED)

This phase focuses on transforming a raw news article summary into a structured narrative that matches your unique writing voice.

- **Milestone 2.1: The Voice Adopter**

  - **Task:** Create a module to generate text in your specific writing style.
  - **"Done" Criteria / How to Test:** The `flask generate-voiced-summary` command successfully populates the `voiced_summary` field in the database.
  - **Status: ✅ COMPLETED**

- **Milestone 2.2: The Timeline Architect**
  - **Task:** Convert the voice-matched summary into a structured, sequential timeline of events or scenes.
  - **"Done" Criteria / How to Test:** The `flask generate-timeline` command populates the `timeline_json` field with a valid JSON list of scenes.
  - **Status: ✅ COMPLETED**

---

### Phase 3: Visual Asset Production (Status: ✅ COMPLETED)

This phase focuses on creating a sequence of stylistically coherent images that correspond to the narrative timeline.

- **Milestone 3.1: The Image Scout & Raw Image Generation**

  - **Task:** For each scene in the timeline, source an image prompt and generate a "raw" image focused on content accuracy.
  - **"Done" Criteria / How to Test:** The `flask source-images` and `flask generate-raw-images` commands successfully run, updating the `timeline_json` with prompts and saving raw images to the `instance/images/` directory. Each scene object in the timeline contains a `raw_image_path`.
  - **Status: ✅ COMPLETED**

- **Milestone 3.2: The Image Artist & Stylization**
  - **Task:** Apply a consistent stylistic transformation to all raw images using a theme-based system.
  - **"Done" Criteria / How to Test:** The `flask stylize-images --theme <theme_name>` command runs successfully. It takes the raw images, applies the selected style via the Replicate API, and saves the new images (e.g., `scene_1_styled.png`) to the filesystem. The `timeline_json` for each scene is updated with a `stylized_image_path`.
  - **Status: ✅ COMPLETED**

---

### Phase 4: Collaborative Writing Workflow (Status: ✅ COMPLETED)

This phase introduced human-AI collaboration for authentic content creation with workflow state management.

- **Milestone 4.1: Collaborative Writing Infrastructure**

  - **Task:** Implement modular service architecture for user contribution and AI enhancement.
  - **Achievement:** Created `CollaborativeWritingService`, `PipelineOrchestrator`, and complete CLI workflow.
  - **Status: ✅ COMPLETED**

- **Milestone 4.2: Workflow State Management**

  - **Task:** Persistent workflow tracking across CLI commands and session boundaries.
  - **Achievement:** Database-driven state restoration from article fields with intelligent phase detection.
  - **Status: ✅ COMPLETED**

- **Milestone 4.3: Archive.is Content Enhancement**

  - **Task:** Breakthrough content acquisition using archived versions for full article text.
  - **Achievement:** 20-40x content increase over traditional snippet-based approaches with 60%+ success rate.
  - **Status: ✅ COMPLETED**

### Phase 5: Production-Ready Media Assembly (Status: ✅ COMPLETED)

This phase brought all assets together into professional video compositions with layout control.

- **Milestone 5.1: Enhanced Timeline Generation**

  - **Task:** Include both narrative text and visual descriptions with duration analysis.
  - **Achievement:** Four-component timeline structure (text, description, timing, scene type) with 150 WPM estimates.
  - **Status: ✅ COMPLETED**

- **Milestone 5.2: Video Composition with Layout Control**

  - **Task:** Flexible video composition allowing user control over layout and positioning.
  - **Achievement:** `VideoCompositor` service with configurable recorded video positioning (top/bottom).
  - **Status: ✅ COMPLETED**

- **Milestone 5.3: Complete Asset Assembly Pipeline**
  - **Task:** End-to-end asset packaging with automatic image copying and organization.
  - **Achievement:** `assemble-final` command with structured output directory and metadata tracking.
  - **Status: ✅ COMPLETED**

### Phase 6: Streamlined Turnkey Workflow (Status: ✅ COMPLETED)

This phase created a completely turnkey 5-command workflow for rapid story-to-video production.

- **Milestone 6.1: Story-First Workflow Design**

  - **Task:** User story drives narrative with news content as supporting context.
  - **Achievement:** `story-create` command combining preliminary story with 3 reliable news articles.
  - **Status: ✅ COMPLETED**

- **Milestone 6.2: Enhanced Script Generation**

  - **Task:** AI blends user story with news context in Thompson's authentic voice.
  - **Achievement:** `script-generate` with `generate_voiced_story_from_user_and_news()` function.
  - **Status: ✅ COMPLETED**

- **Milestone 6.3: Complete Visibility Timeline Approval**

  - **Task:** Full timeline review before committing to image generation.
  - **Achievement:** `timeline-approve` shows complete text + visuals + duration estimates before processing.
  - **Status: ✅ COMPLETED**

- **Milestone 6.4: Final Video Composition Integration**
  - **Task:** Seamless video composition with user's recorded content.
  - **Achievement:** `video-compose` command with automatic asset management and professional layout.
  - **Status: ✅ COMPLETED**
