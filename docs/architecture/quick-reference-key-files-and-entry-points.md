# Quick Reference - Key Files and Entry Points

### Critical Files for Understanding the System

- **Main Entry**: `src/main.py` (Discord bot entry point)
- **Configuration**: `pyproject.toml`, `pytest.toml`, `pytest_panel.toml`
- **Core Business Logic**: `src/cogs/` (Discord cog modules)
- **Database Models**: `src/core/database/` (SQLAlchemy models)
- **Testing Infrastructure**: `tests/conftest.py` (903 lines of test configuration)
- **Key Algorithms**: `src/cogs/activity_meter/` (ROAS calculation logic)

### Enhancement Impact Areas

Based on the PRD requirements, these files will be affected:

- `tests/conftest.py` - Enhanced test infrastructure
- `tests/unit/` - New unit tests for core logic
- `tests/integration/` - Database and API integration tests
- `src/cogs/*/panel/` - Panel interaction tests
- `pytest.toml` - Updated test configuration
