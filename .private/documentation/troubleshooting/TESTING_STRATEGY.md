# Complete Testing Strategy & Troubleshooting Guide

This document outlines the comprehensive testing strategy for Media Buddy and similar Flask projects. It includes testing patterns, troubleshooting procedures, and best practices to ensure code quality and prevent regressions.

**Quick Reference:**

- For detailed pytest troubleshooting: See `PYTEST_TROUBLESHOOTING.md`
- For Flask-specific testing patterns: See `FLASK_TROUBLESHOOTING.md`

---

## Test Strategy Overview

The test suite is managed by `pytest` and follows a multi-layered approach to ensure comprehensive coverage while maintaining fast execution times.

### Test Categories & Markers

Use `pytest` markers for flexible test execution:

```bash
pytest -m api      # API integration tests
pytest -m clients  # External API client unit tests
pytest -m utils    # Utility function unit tests
pytest -m voice    # Voice processing tests
pytest -m timeline # Timeline generation tests
```

---

## Critical Testing Patterns

### 1. Database Test Isolation

**The Golden Rule:** Tests that modify database state MUST NOT share state.

#### ✅ Correct Pattern (Function-Scoped Fixtures)

```python
@pytest.fixture(scope="function")
def clean_db():
    """Create fresh database schema for each test"""
    db.create_all()
    yield db
    db.drop_all()
    db.session.remove()
```

#### ❌ Avoid (Session/Transaction-Based Fixtures)

```python
# DON'T DO THIS - causes test contamination
@pytest.fixture(scope="session")
def shared_db():
    # Shared state leads to flaky tests
    pass
```

### 2. SQLAlchemy Relationship Patterns

#### ✅ Modern Pattern (back_populates)

```python
# Parent model
class DailyLog(db.Model):
    sections = db.relationship('LogSection', back_populates='daily_log', cascade='all, delete-orphan')

# Child model
class LogSection(db.Model):
    daily_log = db.relationship('DailyLog', back_populates='sections')
```

#### ❌ Legacy Pattern (backref - causes commit errors)

```python
# DON'T USE - can cause subtle database issues
class DailyLog(db.Model):
    sections = db.relationship('LogSection', backref='daily_log')
```

### 3. External API Client Testing

#### Mock External Services

```python
@pytest.fixture
def mock_gemini_api(monkeypatch):
    """Mock Gemini API responses"""
    def mock_generate_content(prompt):
        return MockResponse(text='{"timeline": [{"scene": 1, "text": "Test"}]}')

    monkeypatch.setattr('google.generativeai.GenerativeModel.generate_content', mock_generate_content)

def test_timeline_generation(mock_gemini_api):
    """Test timeline generation with mocked API"""
    result = generate_timeline("Test content")
    assert len(result) > 0
    assert result[0]['scene'] == 1
```

#### Test Client Abstraction

```python
def test_replicate_client_error_handling():
    """Test that client handles API failures gracefully"""
    client = ReplicateClient("invalid_key")
    result = client.generate_image("test prompt")
    assert result is None  # Should return None on failure, not crash
```

---

## Testing Checklist by Layer

### Tier 1: API Integration Tests (`tests/test_api.py`)

Validate Flask API endpoints end-to-end with real database, mocked external services.

#### Voice & Content Generation

- [x] **`/api/voice-respond`**
  - [x] Test successful response with valid prompt
  - [x] Test with length parameter
  - [x] Test error handling for invalid input
- [ ] **`/api/generate-voice-response`**
  - [x] Test news topic processing
  - [ ] Test with invalid topic
  - [ ] Test with API failure

#### Timeline & Image Generation

- [ ] **`/api/generate-timeline-from-file`**
  - [ ] Test successful timeline generation
  - [ ] Test concept-based vs standard timeline
  - [ ] Test with theme integration
  - [ ] Test file not found error
- [ ] **`/api/timeline-approve`**
  - [ ] Test image generation from timeline
  - [ ] Test with different themes
  - [ ] Test cost optimization flags

### Tier 2: Client Unit Tests (`tests/test_clients.py`)

Validate external API wrapper modules in isolation.

#### Google APIs

- [ ] **Gemini Client**
  - [ ] Test prompt construction for voice generation
  - [ ] Test timeline generation prompts
  - [ ] Test error handling for quota limits
  - [ ] Test response parsing and validation

#### Replicate/Flux Integration

- [ ] **Image Generation Client**
  - [ ] Test prompt formatting (T5-style vs keyword)
  - [ ] Test user scene detection and trigger integration
  - [ ] Test theme integration (direct vs kontext)
  - [ ] Test single-concept validation
  - [ ] Test error handling for failed generations

#### News APIs

- [ ] **News Service Clients**
  - [ ] Test article fetching and filtering
  - [ ] Test content extraction and validation
  - [ ] Test rate limiting and error recovery

### Tier 3: Utility & Logic Unit Tests (`tests/test_utils.py`)

Target pure functions and complex business logic.

#### Content Processing

- [ ] **Timeline Generation Logic**
  - [ ] Test concept analysis extraction
  - [ ] Test scene segmentation (15-25 words)
  - [ ] Test single-concept validation
  - [ ] Test composite description detection
- [ ] **Voice Processing Logic**
  - [ ] Test style vs content separation
  - [ ] Test writing sample integration
  - [ ] Test embedding generation
- [ ] **Image Prompt Generation**
  - [ ] Test T5-style prompt formatting
  - [ ] Test user trigger integration
  - [ ] Test theme blending

---

## Common Test Failure Troubleshooting

### 1. Database-Related Failures

#### Symptom: Tests hang indefinitely

**Likely Causes:**

- Database deadlocks from contaminated test state
- Session not properly cleaned up between tests
- Foreign key constraint violations

**Solutions:**

1. Use function-scoped database fixtures
2. Ensure `db.session.remove()` after each test
3. Check for proper cascade settings on relationships

#### Symptom: `assert 0 == 2` failures

**Likely Cause:** Silent parsing errors in loops
**Solutions:**

1. Check regex patterns (`\s` vs `\\s`, `\n` vs `\\n`)
2. Validate loop conditions and data processing
3. Add debug prints to verify loop execution

### 2. API Integration Failures

#### Symptom: `requests.exceptions.SSLError`

**Solutions:**

1. Use `verify=False` for development only
2. Check certificate paths and CA bundles
3. Verify API endpoint URLs

#### Symptom: Authentication failures (401/403)

**Solutions:**

1. Verify environment variable loading
2. Check API key validity and permissions
3. Test token refresh mechanisms

### 3. Content Generation Failures

#### Symptom: Timeline has composite descriptions

**Solutions:**

1. Check prompt engineering for single-concept enforcement
2. Validate description parsing and filtering
3. Test with known good vs bad examples

#### Symptom: Images don't match content

**Solutions:**

1. Verify T5-style prompt formatting
2. Check concept analysis accuracy
3. Test theme integration logic

---

## Performance & Optimization

### Test Execution Speed

- **Unit tests:** Should run in milliseconds
- **Integration tests:** Should complete in seconds
- **Full suite:** Should finish under 2 minutes

### Isolation Strategies

- Use in-memory databases for speed
- Mock external API calls
- Parallel test execution where possible

### CI/CD Integration

```bash
# Run fast tests first
pytest -m "not slow" --maxfail=5

# Run full suite if fast tests pass
pytest --cov=src --cov-report=html
```

---

## Emergency Debugging Procedures

### When All Tests Fail

1. **Check Environment Setup**

   ```bash
   # Verify virtual environment
   which python
   pip list

   # Check environment variables
   env | grep -E "(DATABASE|API_KEY)"
   ```

2. **Database State Reset**

   ```bash
   # Nuclear option (development only)
   flask db downgrade base
   flask db upgrade head
   ```

3. **Isolate the Problem**

   ```bash
   # Run single test to isolate issue
   pytest tests/test_specific.py::test_function -v -s

   # Check for import errors
   python -c "import src.media_buddy"
   ```

### When Tests Are Flaky

1. **Run tests multiple times**

   ```bash
   pytest --count=10 tests/test_flaky.py
   ```

2. **Check for state leakage**

   - Add debug prints to fixtures
   - Verify database cleanup
   - Check global variables

3. **Verify test isolation**
   - Run tests in different orders
   - Use `pytest-randomly` plugin

---

**Remember:** Good tests are fast, isolated, deterministic, and provide clear failure messages. When debugging test failures, start with the simplest possible cause before assuming complex issues.
