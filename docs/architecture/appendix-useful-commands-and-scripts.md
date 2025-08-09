# Appendix - Useful Commands and Scripts

### Frequently Used Commands

```bash
pytest                           # Run all tests
pytest -v                        # Verbose output
pytest -k "test_name"            # Run specific test
pytest -m "unit"                 # Run unit tests only
pytest --cov=src                 # Run with coverage
ruff check                       # Code quality check
mypy src/                        # Type checking
uv sync                          # Install dependencies
```

### Debugging and Troubleshooting

- **Test Logs**: Check pytest output for detailed test information
- **Database Issues**: Use isolated test databases in conftest.py
- **Mock Problems**: Extensive mock setup in conftest.py
- **Performance Issues**: Use built-in performance monitoring fixtures

### Test Data Management

- **Test Data Generation**: `test_data_generator` fixture available
- **Database Cleanup**: Automatic cleanup in isolated test databases
- **Mock Management**: `mock_manager` fixture for complex mocking scenarios
