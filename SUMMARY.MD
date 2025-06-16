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

---

_This document should be updated after every major feature implementation or significant troubleshooting session._
