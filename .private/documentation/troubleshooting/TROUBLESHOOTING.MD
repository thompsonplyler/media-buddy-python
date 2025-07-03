# Media Buddy: Complete Troubleshooting & Best Practices Guide

**Purpose:** This document provides the definitive guide for best practices and troubleshooting procedures for Media Buddy and similar Python/Flask projects. It serves as the primary reference for AI agents and developers to stay on task and maintain high standards.

**Quick Reference:** For technology-specific guidance, see:

- `TROUBLESHOOTING_FLUX_PROMPTING.MD` - T5-style prompting best practices
- `VOICE_PROCESSOR_INTEGRATION_GUIDE.md` - Voice processing system integration
- `FLASK_TROUBLESHOOTING.md` - Production Flask patterns and security

---

## 1. Core Architectural Principles

These fundamental philosophies prevent common issues and enhance maintainability across any Python/Flask project.

### Separation of Concerns (SoC)

- **Principle:** Each distinct feature should be isolated into separate, independent modules
- **Application:** External services (Discord, APIs) act as thin clients to the Flask backend
- **Media Buddy Example:** Timeline generation, voice processing, and image generation are separate services that communicate through well-defined interfaces

### Treat External Services as Fallible

- **Principle:** Never assume external APIs (Gemini, Replicate, Google Calendar) will always be available
- **Implementation:**
  - Robust error handling with timeouts
  - Retries with exponential backoff
  - Circuit breakers for persistent failures
  - Graceful degradation with informative error messages

### Configuration as Code

- **Principle:** All configurable parameters stored centrally and version-controlled
- **Implementation:** Use `config.py` module, load `.env` values at startup, validate and document settings
- **Security:** Never hard-code secrets or commit them to version control

### Defensive Programming

- **Principle:** Validate inputs and states at every boundary
- **Application:**
  - Validate CLI inputs and parameters
  - Strictly validate API responses (check types, required fields)
  - Sanitize file paths and imported content
  - Use type checking (schemas, Pydantic models) at integration boundaries

---

## 2. Flask, SQLAlchemy & Alembic Best Practices

### Migrations: The Golden Rule

- **Never modify existing migration files** once applied to any shared environment
- **Workflow:**
  1. Make changes to SQLAlchemy models (`models.py`)
  2. Generate migration: `flask db migrate -m "Descriptive message"`
  3. **Review the generated script for accuracy**
  4. Apply migration: `flask db upgrade`
  5. Commit migration file with model changes

### Data Integrity & Error Handling

- **Data Types:** Use precise SQLAlchemy types (`Text`, `DateTime`, `Boolean`, `Integer`)
- **Constraints:** Enforce database-level constraints (`unique=True`, `nullable=False`)
- **Exception Handling:** Catch `sqlalchemy.exc.DataError` for graceful degradation

### Migration Recovery (Development Only)

- **Symptom:** `UndefinedTable` or `ColumnNotFound` errors indicate schema drift
- **Recovery:** Database reset with `flask db upgrade head` from clean state
- **⚠️ Never in production** - use proper migration rollback procedures

---

## 3. External API Integration Patterns

### Credential Management

- **Storage:** Use `.env` files loaded through `config.py`
- **Validation:** Implement credential verification on startup
- **Refresh:** Automatic token refresh where applicable (Google APIs)
- **Troubleshooting:** 401/403 errors → verify credential loading and token expiration

### Client Abstraction Pattern

Encapsulate all interactions with external APIs in dedicated client classes:

```python
class ReplicateClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.replicate.com"

    def generate_image(self, prompt: str, **kwargs):
        # Handle authentication, retries, rate limiting
        # Normalize responses, validate outputs
        pass
```

### Input Validation & Response Handling

- **Always validate API responses:** Check required fields, data types, use schemas
- **Handle the "Onion of Errors":** Start with environment validation, then API contract validation, then output handling
- **Reference canonical examples:** When integrating new APIs, start with the simplest "Hello World" from official docs

---

## 4. AI Content Generation Best Practices

### Voice Processing System

- **Key Insight:** Distinguish between STYLE and CONTENT in prompts
- **Implementation:** Use extensive writing samples (70KB+) for style adoption
- **Quality Control:** Separate style analysis from content generation
- **Integration:** See `VOICE_PROCESSOR_INTEGRATION_GUIDE.md` for detailed implementation

### Image Generation (Flux/Replicate)

- **Prompting Style:** Use T5-style natural language, not keyword lists
- **Single Concept Rule:** Each image should represent ONE distinct thing
- **Cost Optimization:** Direct theme integration vs. expensive kontext styling
- **Reference:** See `TROUBLESHOOTING_FLUX_PROMPTING.MD` for detailed T5 prompting guidelines

### Timeline Generation

- **Segmentation:** 15-25 words per scene for proper pacing
- **Visual Descriptions:** Complete sentences explaining scenes to a person
- **Concept-Driven:** Use content analysis to create relevant, focused visuals
- **Quality Validation:** Check for composite descriptions (avoid "A and B", "while", "with")

---

## 5. Testing Strategy & Implementation

### Test Categories (Pytest Markers)

```bash
pytest -m api      # API integration tests
pytest -m clients  # External API client unit tests
pytest -m utils    # Utility function unit tests
```

### Critical Testing Patterns

#### Database Test Isolation

**Problem:** Tests that modify database state contaminate each other
**Solution:** Function-scoped fixtures that create/destroy schema per test

```python
@pytest.fixture(scope="function")
def clean_db():
    # Create schema from scratch
    db.create_all()
    yield db
    # Completely drop schema
    db.drop_all()
```

#### SQLAlchemy Relationship Patterns

**Avoid:** `backref` helpers (cause subtle commit errors)
**Use:** Explicit `back_populates` on both models:

```python
# Parent model
sections = db.relationship('LogSection', back_populates='daily_log')

# Child model
daily_log = db.relationship('DailyLog', back_populates='sections')
```

#### Common Test Failures

1. **Check parsing errors first:** `assert 0 == 2` often indicates silent regex/parsing failures
2. **Verify test isolation:** Hanging tests usually indicate contaminated database state
3. **Environment setup:** Ensure virtual environment is activated before running tests

---

## 6. File System & Content Processing

### File Sync Service Architecture

- **Principle:** Treat local file system as a remote endpoint
- **Implementation:** `watchdog` service calls Flask API, doesn't use `os.path` for business logic
- **Robustness:** Implement retry queues with exponential backoff, dead-letter queues for failed operations

### Content Processing Pipeline

1. **File Detection:** Monitor file changes with `watchdog`
2. **Content Extraction:** Parse content, extract metadata
3. **Voice Processing:** Generate voiced content if needed
4. **Timeline Generation:** Create visual scene descriptions
5. **Image Generation:** Produce images from timeline descriptions
6. **Video Composition:** Combine audio, images, and timings

---

## 7. Environment-Specific Considerations

### Windows Development

- **Virtual Environments:** Create with native Windows Python (`python -m venv venv`)
- **Activation:** Use `.\\venv\\Scripts\\activate`
- **Server Compatibility:** Use Flask dev server or Waitress (gunicorn doesn't work on Windows)
- **PowerShell Profiles:** Configure Cursor to load personal PowerShell profile for consistent environment

### SSL & Certificates

- **Development:** Use `verify=False` only in dev with self-signed certificates
- **Production:** Properly chained TLS certificates or CA bundle path
- **Troubleshooting:** `SSLError` indicates verification configuration issue

---

## 8. Project-Specific Case Studies

### The "Nuclear Option" for Database Migrations

**Symptom:** Migration history corruption, `flask db upgrade` fails with obscure errors
**Root Cause:** `alembic_version` table desynchronized from migration files
**Solution (Dev Only):** Direct database intervention:

```python
# Force alembic version sync
DELETE FROM alembic_version;
INSERT INTO alembic_version (version_num) VALUES ('<latest_revision_hash>');
```

### API Integration: Start Simple

**Symptom:** Complex API integration failures with cascading errors
**Root Cause:** Starting with complex assumptions instead of canonical examples
**Solution:** Always begin with official "Hello World" examples, then build complexity

### The Practical vs. Perfect Solution

**Symptom:** Time lost chasing technically superior but unattainable solutions
**Example:** Abandoning `pgvector` (C++ build issues) for practical SQL-based approach
**Lesson:** Ship working, practical solutions rather than getting stuck on perfect ones

---

## 9. Emergency Troubleshooting Procedures

### Database Issues

1. **Check simple parsing errors first** (regex patterns, loop conditions)
2. **Verify environment variables** (`echo $DATABASE_URL`)
3. **Check container status** (`docker ps`)
4. **Review migration history** (`flask db current`, `flask db history`)
5. **Nuclear option (dev only):** Fresh database with `flask db upgrade head`

### API Integration Failures

1. **Verify credentials and environment setup**
2. **Test with simplest possible API call**
3. **Check rate limits and quotas**
4. **Validate input/output contracts**
5. **Implement proper error handling and retries**

### Image Generation Issues

1. **Verify prompt format** (T5-style natural language vs. keywords)
2. **Check single concept rule** (no composites, "and", "while")
3. **Validate theme integration** (direct vs. kontext styling)
4. **Test with known good prompts**
5. **Check API quotas and model availability**

---

## 10. Quality Assurance Checklist

### Before Deploying New Features

- [ ] All tests pass with proper isolation
- [ ] API endpoints return appropriate error codes
- [ ] External service failures are handled gracefully
- [ ] Configuration is environment-aware
- [ ] Sensitive data is properly protected
- [ ] Documentation is updated

### Code Review Focus Areas

- [ ] Input validation at all boundaries
- [ ] Proper error handling and logging
- [ ] Resource cleanup (database sessions, file handles)
- [ ] Security considerations (SQL injection, XSS prevention)
- [ ] Performance implications (N+1 queries, blocking operations)

---

**Remember:** The goal is to build systems that fail gracefully, provide clear error messages, and can be debugged efficiently. When in doubt, prioritize simplicity and reliability over complexity and optimization.
