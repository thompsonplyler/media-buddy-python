# 1. Core Architectural Principles

This section lays out the fundamental philosophies guiding robust software development for projects like Job Commando. Adhering to these principles from the outset will prevent a multitude of common issues and enhance maintainability.

### Separation of Concerns (SoC)

- **Principle:** Each distinct feature or aspect of the system should be isolated into a separate, independent module. Modifications to one concern should ideally not impact others.
- **Application:** In Job Commando, this means the Discord bot should act as a thin client to the Flask API. The bot's primary role is to handle Discord-specific interactions and route commands; it should not contain business logic, direct database access, or complex data transformations. All core logic (e.g., managing job data, interacting with Google Calendar) resides within the Flask backend, exposed via well-defined REST endpoints, making the bot replaceable and the backend independently testable.

### Treat External Services as Fallible

- **Principle:** Never assume that external APIs (Google Calendar, Riot Games API, Google Gemini) or even internal services will always be available, performant, or behave as expected. Failures are inevitable.
- **Application:** Implement robust error handling, timeouts, retries with exponential backoff, and circuit breakers when interacting with any external service. Gracefully degrade functionality or provide informative error messages to the user when an external dependency is unavailable. Plan for API changes, versioning, and deprecations.

### Configuration as Code

- **Principle:** All configurable parameters of the application (e.g., database connection strings, API keys, service URLs, feature flags) should be stored in a centralized, version-controlled manner, separate from the application's core logic.
- **Application:** Utilize a dedicated `config.py` module to manage all settings. Load `.env` values into `config.py` at startup. Validate and document them, and avoid hard-coding secrets. This promotes consistency, simplifies deployment across different environments (development, testing, production), and reduces human error during configuration updates.

### Defensive Programming

- **Principle:** Anticipate and prevent issues by validating inputs and states at every boundary. Assume data from external sources (user input, external APIs, file system events) is potentially malicious or malformed.
- **Application:**
  - Validate Discord inputs (commands, parameters).
  - Strictly validate API responses—check types, required fields.
  - Sanitize paths and content imported from file sync.
  - Use type checking (e.g., Marshmallow schemas, Pydantic models) at all integration boundaries.

# 2. Flask, SQLAlchemy & Alembic

This section focuses on best practices for developing a resilient and maintainable database-driven Flask application using SQLAlchemy for ORM and Alembic for migrations.

### Migrations: The Golden Rule

- **Principle:** Once a migration file has been created and applied to any shared environment, never modify it. Changes to old migration files introduce inconsistencies in the database history.
- **Workflow:**
  1.  Make changes to your SQLAlchemy models (`models.py`).
  2.  Generate a new migration script: `flask db migrate -m "Descriptive message"`
  3.  Review the generated script for accuracy.
  4.  Apply the migration: `flask db upgrade`
  5.  Commit the new migration file along with your model changes.
- **Troubleshooting:** Errors like `UndefinedTable` or `ColumnNotFound` often point to schema drift. In rare development-only cases, a manual database reset may be the last resort.

### Data Integrity & Exceptions

- **Data Types:** Choose precise SQLAlchemy data types. Use `Text` for variable-length strings and specific types like `DateTime`, `Boolean`, and `Integer`.
- **Constraints:** Enforce database-level constraints (`unique=True`, `nullable=False`) directly in your SQLAlchemy models.
- **Error Handling:** Catch `sqlalchemy.exc.DataError` during database writes to gracefully manage issues like invalid data types or length violations.

### Migration Pitfalls & Recovery

- **"Tangling":** This occurs due to out-of-order application of migrations, often from branch merges.
- **Recovery (Dev Only):** Dropping and recreating the database (`flask db upgrade head` from a clean state) is an acceptable last resort in a local development environment. **Never in production.**

# 3. Architecting a Resilient File-Sync Service

Connecting a local file system to a remote backend requires a robust approach.

### The Core Principle: Treat the Local Source as a Remote Endpoint

- **Principle:** The `watchdog` service should not use `os.path` for business logic. The local file system is a data source whose changes are transmitted to the backend via a well-defined REST API.
- **Application:** When a file changes, `watchdog` captures the event and calls the Flask backend's API. The backend's API dictates the data format and validity checks. This decouples the services.

### Robustness

- **Retry Queues:** Implement a persistent retry queue (e.g., using Redis/Celery) with exponential backoff for failed API calls.
- **Dead-Letter Queues (DLQ):** After a predefined number of retries, move persistently failing operations to a DLQ for manual inspection.
- **Notifications:** Log critical errors if the backend is unreachable.

### SSL & Certificates

- **Development:** Use `verify=False` in `requests` only in dev environments with self-signed certificates.
- **Production:** Use properly chained TLS certificates or pass the path to your internal CA bundle (`verify='/path/to/ca.pem'`).
- **Troubleshooting:** An `requests.exceptions.SSLError` points to a verification configuration issue.

# 4. External API Integration

Consuming third-party APIs requires careful design.

### Credential Management

- **Principle:** Never hardcode secrets or commit them to version control.
- **Application:** Store secrets in `.env` files and load them through `config.py`.
- **Troubleshooting:** On 401/403 errors, verify credential loading. Implement mechanisms to refresh tokens automatically where applicable.

### Client Abstraction

- **Principle:** Encapsulate all interactions with a specific external API within dedicated client classes.
- **Application:** Build clients (e.g., `GoogleCalendarClient`, `RiotClient`) to handle authentication, token refreshing, retries, rate limiting, and response normalization.

### Input Validation

- **Principle:** Always validate incoming data from external APIs.
- **Application:** Rigorously validate responses: check for required fields, correct data types, and use schemas (e.g., Pydantic) to enforce structure.

# 5. Conversational AI State Management

Providing an AI with "memory" is crucial for coherent interactions.

### Short-Term Memory

- **Principle:** The AI needs immediate access to preceding messages for context.
- **Application:** Pass recent message history in each request to the Gemini API.
- **Best Practice:** Use summaries or truncation for long histories to stay within API token limits.

### Long-Term Memory

- **Principle:** Persistent long-term memory is required for recall across sessions.
- **Strategies:**
  - **Structured Data:** Store in a relational DB (PostgreSQL) for specific facts.
  - **Unstructured/Semantic Data:** Use a vector database (e.g., `pgvector`) for embeddings-based recall.

### Retrieval Limitations

- **Principle:** Simple keyword-based context retrieval struggles with conceptual understanding.
- **Application:** For deep context, projects should aim for semantic retrieval (vector embeddings and similarity search).

# 6. Environment-Specific Gotchas (Windows)

Developing on Windows introduces specific considerations.

### Virtual Environments

- **Issue:** A `venv` created in WSL is not compatible with a native Windows Python installation.
- **Best Practice:** Always create and activate the `venv` with the native Windows Python interpreter: `python -m venv .venv` followed by `.\.venv\Scripts\activate`.

### Server Compatibility

- **Issue:** WSGI servers like `gunicorn` do not run natively on Windows.
- **Application:** For local development, use Flask's built-in server (`flask run`) or Waitress. For production, use Linux-based containers (e.g., Docker).

# 7. Addenda from the Field: Job Commando Case Studies

The following are specific, hard-won lessons from the `job-commando` project. They serve as concrete examples of the principles outlined above.

### Case Study: The "Nuclear Option" for Database Migrations

- **Symptom:** `flask db upgrade` commands fail with obscure errors, even after trying to `downgrade` or `stamp` to a previous version. The migration history felt irreparably "tangled."
- **Root Cause:** The `alembic_version` table in the PostgreSQL database became desynchronized from the actual migration files in the `migrations/versions` directory. This was likely due to previous failed migrations or manual deletion of migration files.
- **The Fix (Development Only):** A "nuclear option" was required.
  1.  A temporary Python script was created to connect directly to the database with `SQLAlchemy`.
  2.  This script manually executed `DELETE FROM alembic_version;` and `INSERT INTO alembic_version (version_num) VALUES ('<latest_revision_hash>');` to force the database's internal tracking to match the latest migration file.
- **Lesson:** While the best practice is to never touch a live database manually, this illustrates that in a local development environment, sometimes a direct, "brute-force" intervention is the fastest way to unblock a hopelessly corrupted migration state.

### Case Study: The Stubbornly Incorrect API Result

- **Symptom:** The Riot Games API consistently returned `0` matches played, even when it was known that games had been played.
- **Root Cause:** This was a two-part problem:
  1.  An incorrect `PUUID` for an old account was cached in the `.env` file.
  2.  Even after correcting the `.env` file, the running Python script was using a stale, in-memory version of the environment variables.
- **The Fix:**
  1.  A utility script, `get_puuid.py`, was created to fetch the correct `PUUID` from the API, confirming the correct identifier.
  2.  The `load_dotenv()` call in `config.py` was modified to include `override=True`. This forced the application to reload the environment variables from the `.env` file on every startup, ensuring the correct `PUUID` was used.
- **Lesson:** This reinforces the "Client Abstraction" principle. A mature `RiotClient` could have had a method to re-validate a PUUID if it repeatedly failed. It also highlights the subtle but critical behavior of environment variable loading.

### Case Study: The Ideal Solution vs. The Practical Solution

- **Symptom:** The AI's contextual responses were poor because its long-term memory retrieval was based on simple keyword matching.
- **The Goal:** Implement a true semantic search using vector embeddings via the `pgvector` extension for PostgreSQL.
- **The Roadblock:** The `pgvector` library requires C++ build tools to be installed and correctly configured on the host machine. On our Windows development environment, we encountered significant, time-consuming, and ultimately unresolved errors trying to get these build tools to work.
- **The Pivot:** We abandoned the "ideal" solution (`pgvector`) and pivoted to a "practical" one. We restructured the database schema (`DailyLog`, `LogSection`) to mirror the structure of the source documents. This allowed us to perform more targeted, albeit less intelligent, SQL queries.
- **Lesson:** The technically superior solution is irrelevant if it cannot be implemented and maintained within the constraints of the development environment. It is often better to ship a working, practical solution than to get stuck chasing a perfect but unattainable one. This is a crucial consideration for any project.

### Case Study: The Unreliable Test Suite

- **Symptom:** Tests (`pytest`) fail inconsistently. Sometimes the entire test suite hangs indefinitely. Errors seem to point towards complex database issues.
- **Root Cause & Troubleshooting Steps**: This was caused by three separate issues. When encountering similar symptoms, check these in order:
  1.  **Check for Trivial Parsing Errors**: Before assuming a complex database problem, check the code being tested for simple mistakes. Our most persistent test failure was not a database error, but a simple parsing bug where `\\s` and `\\n` were used instead of `\s` and `\n` in a regular expression. An `assert 0 == 2` failure is a classic sign that a loop that was supposed to populate a list never ran due to a silent parsing error.
  2.  **Ensure True Test Isolation**: Tests that modify a database **must not** share state. The fix was to replace all session-scoped or transaction-based fixtures with a single, **function-scoped fixture** that creates the database schema from scratch before every test and drops it completely after. This is the gold standard for preventing test contamination.
  3.  **Use Modern SQLAlchemy Relationship Patterns**: The use of the `backref` helper in a model relationship can cause subtle commit errors that are difficult to trace. The modern, preferred pattern is to explicitly define the relationship on **both** models using `back_populates`.
      - **On the "one" side**: `sections = db.relationship('LogSection', back_populates='daily_log', ...)`
      - **On the "many" side**: `daily_log = db.relationship('DailyLog', back_populates='sections')`
- **Lesson:** Debugging should often work from simplest cause to most complex. The most obscure errors can be symptoms of the most basic mistakes. Fixing the test isolation and model definitions not only improved reliability but also resolved the mysterious hanging issue, which was likely caused by database deadlocks from contaminated test states.

### Case Study: The Onion of API Errors (Replicate Integration)

- **Symptom:** A chain of cascading, seemingly unrelated errors occurred when attempting to use the Replicate API for image stylization. The process began with cryptic PowerShell rendering failures, followed by `AttributeError` and `UnicodeDecodeError` exceptions from the Python script.
- **Root Cause & Troubleshooting Steps:** This was a multi-layered problem rooted in incorrect assumptions about the external API's contract and the local development environment.
  1.  **Check the Environment First:** The initial PowerShell errors were a red herring caused by forgetting to activate the Python virtual environment (`venv`). The command was failing because it couldn't find Flask, not because of a rendering bug.
  2.  **Validate API Input/Output:** Once the environment was fixed, we received an `Input validation failed` error from the API. This was because we were passing a local file path, but the API expected a public URL. This led to a brief, incorrect path of trying to manually upload the file first.
  3.  **Consult the Canonical "Hello World":** After the manual upload attempt also failed (with an `AttributeError` on a non-existent helper function), we corrected course. The key insight came from ignoring our complex assumptions and finding the simplest possible example for the API endpoint. We discovered the `replicate.run()` function handles file uploads automatically if you pass it a file object opened in binary mode.
  4.  **Handle the Output Correctly:** The final error was a `UnicodeDecodeError`. This happened because we were treating the output from `replicate.run()` as a URL string to be downloaded, when in fact it was a file-like object containing the binary image data directly.
- **The Fix:** The final, correct implementation was remarkably simple:
  1.  Open the local input image file using `with open(filepath, "rb") as f:`.
  2.  Pass the file object `f` directly to the `input_image` parameter in `replicate.run()`.
  3.  The return value from `replicate.run()` is another file-like object. Call `.read()` on it.
  4.  Write the resulting binary data to the destination file.
- **Lesson:** When integrating a new external API, start with the absolute simplest use case from the official documentation. Our troubleshooting became a tangled mess because we started with incorrect assumptions. The most critical lesson was to **trust our own reference snippets**—you pointing me to `private/replicate_snippets` was what ultimately revealed the simple, correct pattern and cut through the noise. Always check local project documentation and the official "hello world" before descending into complex debugging.

# 8. Project-Specific Testing

For guidance on writing and troubleshooting tests with `pytest`, refer to the `PYTEST_TROUBLESHOOTING.MD` document. It contains critical information on avoiding common pitfalls, such as database configuration leaks, and provides standardized patterns for database and client fixtures.
