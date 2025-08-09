# High Level Architecture

### Technical Summary

The Discord ROAS Bot is a sophisticated Discord bot built with Python 3.12+, using discord.py for Discord API integration. It features a modular cog-based architecture with comprehensive testing infrastructure already in place.

### Actual Tech Stack

| Category  | Technology | Version | Notes                      |
| --------- | ---------- | ------- | -------------------------- |
| Runtime   | Python     | 3.12+   | Modern Python with type hints |
| Framework | discord.py | 2.5.2+  | Discord API integration    |
| Database  | SQLite     | -       | aiosqlite for async operations |
| ORM       | SQLAlchemy | 2.0+    | Modern async ORM           |
| Testing   | pytest     | 7.0+    | Comprehensive test framework |
| Code Quality | ruff     | 0.1+    | Fast Python linter        |
| Type Checking | mypy    | 1.7+    | Static type checking      |
| Build Tool | uv        | -       | Modern Python package manager |

### Repository Structure Reality Check

- Type: Monorepo with modular cog structure
- Package Manager: uv (modern Python package manager)
- Notable: Extensive test infrastructure already exists (903-line conftest.py)
