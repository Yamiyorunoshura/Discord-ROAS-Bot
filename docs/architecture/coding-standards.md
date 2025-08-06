# Coding Standards

### Existing Standards Compliance
**Code Style:** Black formatting (88 character limit), existing ruff configuration in pyproject.toml
**Linting Rules:** Comprehensive ruff ruleset already configured (E, W, F, I, B, C4, UP, ARG, SIM, TCH, PTH, ERA, PL, RUF)
**Testing Patterns:** pytest-based with asyncio support, existing markers for unit/integration/e2e tests
**Documentation Style:** Google-style docstrings, existing type annotations

### Enhancement-Specific Standards
- **Test Organization:** Mirror production code structure in tests/, comprehensive coverage requirements (85%+)
- **Quality Gates:** Mandatory ruff compliance (zero violations), mypy strict mode enforcement
- **Performance Standards:** numpy usage for all numerical computations, memory usage within Docker limits
- **Documentation Requirements:** All new test utilities and quality tools must have comprehensive docstrings

### Critical Integration Rules
- **Existing API Compatibility:** Zero breaking changes to Discord command interfaces or database schemas
- **Database Integration:** Test data isolation through dedicated schemas, no production data contamination
- **Error Handling:** Maintain existing error handling patterns, enhance with comprehensive test coverage
- **Logging Consistency:** Use existing structlog configuration, add quality metrics logging

