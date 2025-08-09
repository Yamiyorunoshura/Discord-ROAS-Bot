# Technical Debt and Known Issues

### Critical Technical Debt

1. **dpytest Integration**: Temporarily commented out in conftest.py due to installation issues
2. **Test Coverage**: Some modules lack comprehensive unit tests
3. **Mock Complexity**: Extensive mock setup in conftest.py (903 lines)
4. **Database Testing**: Complex test database setup with multiple isolated databases

### Workarounds and Gotchas

- **Test Environment**: Uses `/tmp/test_project` for isolated testing
- **Database Isolation**: Each test module gets its own isolated database
- **Mock Objects**: Extensive use of MagicMock for Discord objects
- **Async Testing**: Complex async test setup with pytest-asyncio
