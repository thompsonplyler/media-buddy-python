# Project Summary: Job Commando

THIS FILE WORKS IN TANDEM WITH MENTOR_PROTOCOL.MD AND PERSONALITY.MD. If you reach this file and you haven't taken taken both of those files into account as well, please make sure to incorporate those into your understanding of the conversation.

This document summarizes the development progress and key decisions made for the Job Commando project.

## Current Architecture: The Live Assistant (Phase 4)

This phase marks the project's evolution from a set of disparate scripts into a cohesive, database-backed application. The system is designed to act as a live, interactive assistant accessible via Discord, with a persistent memory and an automated sync to the user's local Obsidian vault.

The application now runs as three concurrent services managed by `run.py`.

### Core Components

1.  **Flask API (`src/job_commando`)**: The central brain of the application. It handles all business logic, database interactions, and communication with the Google Gemini API.
2.  **Discord Bot (`src/job_commando/discord_bot.py`)**: The conversational interface. It listens for user commands in Discord, forwards requests to the Flask API, and formats the responses for the user.
3.  **Obsidian Sync Agent (`src/job_commando/obsidian_sync_agent.py`)**: The bridge to the user's local workflow. It uses `watchdog` to monitor the user's specified log directory for file changes and automatically pushes new or updated logs to the Flask API, ensuring the bot's memory stays current without manual user intervention.

### Operating Manual

#### Environment Setup

To run the application, a new user must configure the following variables in their `.env` file:

- `DATABASE_URL`: The full connection string for the PostgreSQL database (e.g., `'postgresql://user:password@host:port/dbname'`).
- `DISCORD_BOT_TOKEN`: The secret token for the Discord bot, obtained from the Discord Developer Portal.
- `GEMINI_API_KEY`: The API key for the Google Gemini service.
- `OBSIDIAN_LOG_PATH`: The **full, absolute path** to the local directory containing the user's daily Markdown log files.

#### API Endpoints

The Flask application exposes the following endpoints:

- **`POST /api/submit_log`**: The primary endpoint for ingesting log data. It expects a JSON payload with `filename` (e.g., `"2025-06-12.md"`) and `content` (the full text of the Markdown file). It will intelligently create a new log entry or update an existing one based on the date parsed from the filename.
- **`GET /api/get_log/<log_date_str>`**: A diagnostic endpoint to retrieve a log for a specific date (formatted as `YYYY-MM-DD`).
- **`POST /api/prompt`**: The endpoint for generating conversational responses. It takes a JSON payload with a `prompt` and a `history` of recent messages, combines them with core personality documents, and returns a response from the Gemini API.

#### Discord Commands

- **`$prompt <your message>`**: The primary way to converse with the bot. The bot will respond using its core personality and the context of the last 10 messages in the channel.
- **`$log` (with a .md file attachment)**: A manual way to submit a daily log to the bot's database. This is largely superseded by the automated Sync Agent but remains a useful tool for manual backfills or corrections.
- **`$showlog <YYYY-MM-DD>`**: A diagnostic command to view the exact content of a log that the bot has stored in its database for a given date.

### Key Technical Journey & Lessons Learned (Phase 4)

- **The Need for Permanent, Internal State**: Our initial designs for providing context to the bot were flawed. We first tried passing file contents directly, then using the Gemini Files API. **Both were wrong.** The key lesson learned was that a deployed, autonomous bot **must have its own persistent data store.** It cannot rely on ephemeral file uploads or direct access to a user's local file system. This led to the decision to use a PostgreSQL database as the bot's "memory".
- **Hybrid Sync Model**: To reconcile the need for a persistent database with the user's desire to maintain their local Obsidian workflow, we designed a hybrid system. The application's database is the single source of truth for the bot, and a separate **Sync Agent** is responsible for keeping that database updated in near real-time as the user works on their local files. This provides a seamless user experience without compromising architectural integrity.
- **Database Migration Hell**: We encountered and overcame a series of painful `flask db` migration issues. The primary cause was a corrupted revision history from previous development attempts.
  - **Lesson**: Alembic's dependency tracking is fragile. Deleting old migration files is not enough if the database's internal `alembic_version` table still references them.
  - **Solution**: When migrations become hopelessly tangled, the most effective solution is a direct, manual intervention. We created a temporary script (`force_db_version.py`) to connect directly to the database with `SQLAlchemy` and manually `DELETE` and `INSERT` the correct revision number into the `alembic_version` table. This brute-force approach fixed the state and allowed the `upgrade` command to proceed correctly. This should be a tool of last resort, but it is a vital one to have in the toolkit.

---

_The historical summary below is preserved for context._

## Job Search File Locations

- Job search materials are located in `private/job-search/`
- Base resumes are located at `private/job-search/base-resumes/`
- Inside that folder, the `master_resume.md` is the single source of truth for all the user's professional experiences.
- Specific job search materials are in `private/job-search/job-hunt/`
- For specific job searches, the job description, resume, and cover letter should go in an appropriately named folder. For example, for the "AI Systems Engineer" job at Qlik, the materials would go in `private/job-search/job-hunt/qlik-ai-systems-engineer/`

## Job Application Protocol

This protocol outlines the step-by-step process for creating tailored application materials for a new job listing.

1.  **Locate Job Materials**: The user will place the new job description in a dedicated, descriptively named folder within `private/job-search/job-hunt/`. For example, a role at "ExampleCorp" would be in a folder like `examplecorp-software-engineer/`.
2.  **Identify Job Description**: The agent's first step is to list the contents of the new directory to find the job description file (e.g., `examplecorp-job.txt`).
3.  **Read Source Documents**: The agent will read two key documents:
    - The newly found job description file.
    - The user's `master_resume.md`, located in `private/job-search/base-resumes/`.
4.  **Analyze and Strategize**: The agent will analyze the job description and the master resume to identify key overlaps and determine the best angle for the application. The goal is to create a compelling narrative that frames the user's existing experience in the context of the role's requirements, **without exaggerating or fabricating skills**.
5.  **Draft Tailored Resume**: The agent will create a new, tailored resume as a Markdown file.
    - **Naming Convention**: `Thompson_Plyler_[Company]_Resume.md`.
    - **Content Focus**: The resume should be a single page, re-framing the master resume's content to specifically highlight the skills and experiences most relevant to the new role.
    - **Location**: The new file will be saved in the same job-specific folder as the description (e.g., in `examplecorp-software-engineer/`).
6.  **Draft Tailored Cover Letter**: The agent will create a new, tailored cover letter as a Markdown file.
    - **Naming Convention**: `Thompson_Plyler_[Company]_Cover_Letter.md`.
    - **Content Focus**: The letter should tell the story that connects the resume's facts, building a strong narrative that is professional, authentic, and speaks to the specific culture and needs of the company.
    - **Location**: The new file will be saved alongside the resume in the job-specific folder.
7.  **Review and Finalize**: The agent will present both drafted files to the user for review and approval. Once approved, the user will handle the final submission.

## Initial Setup (Phase 1)

- **Framework**: The project is built using Python and the Flask web framework.
- **Database**: SQLAlchemy is used as the ORM, with Alembic (via Flask-Migrate) for handling database migrations. The application is configured to connect to a PostgreSQL database, with a fallback to SQLite for local development.
- **Core Application**:
  - A basic Flask application structure was created using the application factory pattern (`create_app`) for improved modularity and testability.
  - A simple `User` model was defined in `src/job_commando/models.py`.
  - A root API endpoint (`/`) was established in `src/job_commando/routes.py` to return a JSON response, confirming the server can handle requests.
- **Environment**: The project was initially set up using Rye.

## Transition to Standard Python Environment (Phase 2)

- **Dependency Management**: Rye was removed from the project to simplify the development environment.
- **Virtual Environment**: The project now uses a standard Python virtual environment (`venv`).
- **Requirements**: A `requirements.txt` file was created and cleaned to contain only the essential packages for the application, resolving installation errors caused by system-level packages.
- **Verification**: The application was successfully tested after transitioning from Rye, confirming that the server runs and responds to requests correctly.

## Tooling and MCPs

This section documents the status and known issues with the MCP tools used in this project, highlighting peculiarities and workarounds discovered.

- **Memory MCP**: **Functional.** The tool's functionality is confirmed.
- **Obsidian MCP**: **Partially Functional with significant workarounds required.**
  - **Pain Point**: An early assumption that the tool could list directory contents was proven wrong. The `list_files_in_dir` command consistently fails for any subdirectory, returning a "Not Found" error even for valid paths.
  - **Pain Point**: The file-reading tools fail if a filename contains special characters (e.g., emojis). However, special characters in the parent directory's path are handled correctly.
  - **Workaround**: The `simple_search` tool is the most reliable method for discovering files. It does not, however, reliably filter by a specific path.
  - **Workaround**: Specific files can be read successfully using `get_file_contents` or `batch_get_file_contents` if the full, correct path is known and the filename uses standard characters.
  - **Success**: The `get_periodic_note` command with `period: "daily"` is the correct and functional tool for retrieving the current daily note, resolving previous issues where other AIs or tools failed to find it.
- **Web Automation (Puppeteer)**: **Non-functional.** Encountered persistent issues with the Puppeteer MCP, which failed to execute navigation and screenshot commands. This remains an unsolved error.
- **Time Service**: **Functional.** Successfully tested.
- **Obsidian API Documentation**: The official documentation for the Obsidian Local REST API has been saved locally at `private/documentation/obsidian_rest_api/Local Rest API for Obsidian_ Interactive API Documentation.htm`. This should be considered the primary source of truth for all interactions with the Obsidian vault.

## Environment-Specific Notes

### Windows

- **Virtual Environment**: The project's `venv` must be created natively on Windows. An environment created in WSL will not function correctly, leading to pathing errors where PowerShell cannot find executables like `python.exe` or `Activate.ps1`. The fix is to delete the existing `venv` directory and recreate it with `python -m venv venv`.
- **Gunicorn**: The `requirements.txt` includes `gunicorn`, which is a Unix-only package. While it installs on Windows, it is not functional and should not be used as the production server in a Windows environment. The standard Flask development server (`app.run()`) works correctly for local development.

## Compassionate Intervention System (Phase 3)

This phase shifted focus from job searching to creating a proactive, automated wellness monitor. The system is designed to detect certain patterns and create a "Compassionate Check-in" event on the user's Google Calendar to gently prompt a conversation.

### Core Architecture

The system is a standalone Python script (`run.py`) that runs an infinite monitoring loop. It is built on three new modules:

- `google_calendar.py`: Handles authentication and creation of calendar events using the Google Calendar API.
- `riot_api.py`: Fetches the user's recent match history from the Riot Games API.
- `state_manager.py`: Manages the application's state (i.e., whether an intervention has already been triggered for the day), using the Obsidian API as its backend.
- `config.py`: A centralized configuration module that handles loading all secrets from the `.env` file and provides a single source of truth for all settings. This was a critical addition to solve import-order dependency issues.

### Triggers

Two triggers are currently implemented:

1.  **League Vortex**: Fires if the user plays 3 or more games of League of Legends in a single day.
2.  **Radio Silence**: Fires if no daily log file is found in the user's Obsidian vault by 8:00 PM EST.

### Key Technical Journey & Lessons Learned

The development of this system was a multi-day process that revealed several crucial technical lessons:

- **Pivoting from AI to APIs**: An initial attempt to use high-level AI tools to "check game history" proved unreliable, returning inconsistent and incorrect results. This led to a crucial architectural decision: **for precise, mission-critical data, always prefer direct API integration over abstracted AI tools.** This project now uses the official Google Calendar and Riot Games APIs directly.
- **The Obsidian API is the Source of Truth**: A fundamental and painful error was made by assuming the Obsidian vault should be treated as a local file system directory. **This was wrong.** The correct architecture, which we eventually implemented, treats the vault as an endpoint that is **only** accessible via the Obsidian Local REST API. The `state_manager.py` module was completely rewritten to use `GET` and `PUT` requests to manage its state file inside the vault, rather than using local file I/O.
- **Debugging the Riot API**: We spent significant time debugging an issue where the Riot API consistently reported `0` matches played. The root cause was twofold:
  1.  An incorrect `PUUID` for an old account was cached in the user's `.env` file. A `get_puuid.py` utility was created to solve this.
  2.  Even with the correct PUUID, the script was using a cached version. Forcing `dotenv` to `override=True` was the final fix.
- **Python Import-Order Issues**: We encountered persistent `ValueError` exceptions where modules could not find environment variables that were clearly in the `.env` file. The root cause was that modules were trying to access `os.getenv()` at import time, _before_ the main script had a chance to run `load_dotenv()`. The solution was to create a centralized `config.py` that loads the `.env` file once, and then have all other modules import their settings from `config`.
- **Obsidian API SSL Warnings**: The script produced `InsecureRequestWarning` messages on every call to the Obsidian local API because it uses a self-signed certificate.
  - **Solution**: We placed the server's certificate file at `private/obsidian_cert/obsidian-local-rest-api.crt`. We then refactored `obsidian_api.py` to use a centralized `_make_obsidian_request` helper function that passes the path to this certificate in the `verify` parameter of every `requests` call. This eliminated the warnings and centralized the API logic.
- **Riot API Inefficiency**: The initial method for counting daily matches was inefficient, fetching the last 20 matches and checking the timestamp of each one individually.
  - **Solution**: The `get_matches_played_today` function in `riot_api.py` was refactored to calculate the Unix timestamp for the start of the current day in the user's local timezone. It now makes a single API call using the `startTime` parameter, which is far more efficient and reliable.

### Current Status

The system is fully functional. It successfully monitors for both triggers, creates a Google Calendar event, and logs its actions and state directly into the user's Obsidian vault via the API. The next step is to test the "Radio Silence" trigger in a real-world scenario and then establish a deployment method for running the script autonomously in the background.
