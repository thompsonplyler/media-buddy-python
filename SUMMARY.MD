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

### Phase 4: Final Assembly & Orchestration (Status: PENDING)

This phase brings all the generated assets together into a final video product.

- **Milestone 4.1: The Video Editor**

  - **Task:** Use FFmpeg to combine the sequence of transformed images and an audio file into a final video.
  - **Plan:**
    1.  Create a new command: `flask assemble-video --article-id <id> --audio-file <path>`.
    2.  The script will use the `timeline_json` to determine the order and duration of each image.
    3.  It will use `ffmpeg` to create a video from the images at `final_image_path` and mux it with the provided audio.
    4.  Add a `final_video_path` column to the `NewsArticle` model.
  - **"Done" Criteria / How to Test:** The command successfully produces a valid `.mp4` video file with the correct images, timing, and audio. The video path is saved to the database.

- **Milestone 4.2: The Conductor**
  - **Task:** Create a single master command to run the entire pipeline and expose key functions via an API.
  - **Plan:**
    1.  Create a command `flask process-full-video <article_id>` that chains all previous commands in the correct order.
    2.  Develop a simple REST API (e.g., `POST /api/articles/<id>/generate-video`) to trigger the full pipeline.
  - **"Done" Criteria / How to Test:** The single command runs without error and produces the final video. The API endpoint successfully triggers the process.
