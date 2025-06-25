# Job Commando Testing Strategy

This document outlines the testing strategy for the Job Commando project. The goal is to build a comprehensive, multi-layered test suite that ensures code quality, prevents regressions, and increases development velocity.

The test suite is managed by `pytest` and can be run from the root directory with the `pytest` command.

## Test Categories & Markers

To allow for flexible test execution, we use `pytest` markers. This allows us to run specific subsets of the test suite.

- `pytest -m api`: Runs only the API integration tests.
- `pytest -m clients`: Runs only the unit tests for external API clients.
- `pytest -m utils`: Runs only the unit tests for utility functions and business logic.

## Testing Checklist

### Tier 1: API Integration Tests (`tests/test_api.py`)

These tests validate the behavior of the Flask API endpoints from end-to-end, mocking external services but using a real (in-memory) database.

- [x] **`/api/prompt`**
  - [x] Test for a successful response with a valid prompt.
- [ ] **`/api/submit_log`**
  - [x] Test successful submission and database persistence.
  - [ ] Test submission with a malformed filename (e.g., `not-a-date.md`).
  - [ ] Test submission with missing `filename` or `content` in the payload.
- [ ] **`/api/get_log/<date>`**
  - [ ] Test successfully retrieving an existing log.
  - [ ] Test retrieving a non-existent log (should return 404).
  - [ ] Test retrieving with a malformed date string (should return 400).
- [ ] **`/api/summ/*`**
  - [ ] `POST /api/summ/set`: Test linking a new Riot account.
  - [ ] `GET /api/summ/show/<id>`: Test showing a linked account.
  - [ ] `GET /api/summ/last/<id>`: Test getting an analysis for a recent game.

### Tier 2: Client Unit Tests (`tests/test_clients.py`)

These unit tests validate the modules that wrap external third-party APIs. They should be fully isolated from the network.

- [ ] **Google Calendar Client**
  - [ ] Test that `create_quick_checkin_event` constructs the correct API payload.
  - [ ] Test handling of a failed API call from Google.
- [ ] **Riot API Client**
  - [ ] Test that `get_puuid_by_riot_id` calls the correct URL.
  - [ ] Test that `get_match_ids_by_puuid` handles an empty response.
  - [ ] Test error handling when the Riot API is unavailable.

### Tier 3: Utility & Logic Unit Tests (`tests/test_utils.py`)

These unit tests target pure functions and complex business logic, ensuring they behave correctly given specific inputs.

- [ ] **`get_context_from_db()`**
  - [ ] Test context retrieval when a specific date is mentioned.
  - [ ] Test context retrieval when keywords (e.g., "sleep", "game") are used.
  - [ ] Test fallback behavior when no specific context is found.
- [ ] **`map_item_ids()`**
  - [ ] Test with a sample dictionary containing known item IDs.
- [ ] **Database Logic**
  - [ ] Test the Markdown parsing logic in isolation to ensure frontmatter and sections are extracted correctly.
