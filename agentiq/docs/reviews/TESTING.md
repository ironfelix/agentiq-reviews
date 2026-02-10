# Testing Guide - Quick Reference

## Installation

```bash
cd apps/reviews
pip install -r requirements-test.txt
```

## Running Tests

### All Tests
```bash
pytest
```

### By Category
```bash
pytest -m unit          # Unit tests (~5s)
pytest -m integration   # Integration tests (~10s)
pytest -m e2e           # End-to-end tests (~15s)
```

### By File
```bash
pytest tests/test_auth.py
pytest tests/test_database.py
pytest tests/test_api_endpoints.py
```

### By Test Name
```bash
pytest -k "test_telegram_auth"
pytest -k "test_create_task"
```

### With Coverage
```bash
# Terminal report
pytest --cov=backend --cov-report=term-missing

# HTML report
pytest --cov=backend --cov-report=html
open htmlcov/index.html
```

### Verbose Output
```bash
pytest -v              # Verbose
pytest -vv             # Extra verbose
pytest -s              # Show print statements
pytest -x              # Stop on first failure
```

### Fast Execution (Parallel)
```bash
pip install pytest-xdist
pytest -n auto         # Use all CPU cores
pytest -n 4            # Use 4 workers
```

## Test Coverage Report

### Check Coverage
```bash
pytest --cov=backend --cov-report=term-missing
```

### Fail if Coverage Below 80%
```bash
pytest --cov=backend --cov-fail-under=80
```

## Debugging Tests

### Run with Debugger
```bash
pytest --pdb           # Drop into debugger on failure
pytest --pdb -x        # Stop on first failure + debugger
```

### Show Locals on Failure
```bash
pytest -l              # Show local variables
pytest --tb=long       # Long traceback
pytest --tb=short      # Short traceback
```

### Logging
```bash
pytest --log-cli-level=INFO    # Show INFO logs
pytest --log-cli-level=DEBUG   # Show DEBUG logs
```

## Test Markers

### Available Markers
- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.e2e` - End-to-end tests
- `@pytest.mark.slow` - Slow tests (>1s)

### Usage
```bash
pytest -m "unit and not slow"
pytest -m "integration or e2e"
pytest -m "not slow"
```

## CI/CD

### Pre-commit (Fast)
```bash
pytest -m unit -x      # Stop on first failure
```

### Full CI Pipeline
```bash
pytest --cov=backend --cov-report=xml --cov-fail-under=80
```

## Common Issues

### Redis Not Running
```bash
# Start Redis
redis-server

# Or use Docker
docker run -d -p 6379:6379 redis:alpine
```

### Import Errors
```bash
# Ensure running from apps/reviews/ directory
cd apps/reviews
pytest
```

### Async Test Failures
- Check for missing `await`
- Ensure fixture is marked with `async`
- Verify `pytest-asyncio` is installed

### Test Hangs
- Check for infinite loops
- Look for missing mocks (real API calls)
- Ensure proper cleanup in fixtures

## Files Structure

```
tests/
├── conftest.py              # Shared fixtures
├── test_auth.py             # Auth tests
├── test_database.py         # Database tests
├── test_llm_analyzer.py     # LLM tests
├── test_api_endpoints.py    # API tests
├── test_celery_tasks.py     # Celery tests
├── test_e2e.py              # E2E tests
├── test_wbcon_integration.py# WBCON tests
├── test_edge_cases.py       # Edge case tests
├── README.md                # Detailed docs
└── TEST_SUMMARY.md          # Test summary
```

## Quick Test Examples

### Test Auth
```bash
pytest tests/test_auth.py::TestTelegramAuth::test_verify_telegram_auth_valid
```

### Test Database
```bash
pytest tests/test_database.py::TestUserModel::test_create_user
```

### Test API
```bash
pytest tests/test_api_endpoints.py::TestTaskEndpoints::test_create_task
```

### Test E2E
```bash
pytest tests/test_e2e.py::TestCompleteUserJourney::test_new_user_registration_and_task_creation
```

## Performance

- **Full suite:** ~30 seconds
- **Unit tests only:** ~5 seconds
- **Parallel (-n auto):** ~10 seconds total

## Coverage Goals

- **Overall:** >80%
- **Critical paths:** >90%
- **Auth/Database:** >95%
- **API endpoints:** >85%
- **Background tasks:** >80%

## Documentation

- Full docs: `tests/README.md`
- Test summary: `tests/TEST_SUMMARY.md`
- API docs: `docs/API.md`
- Architecture: `PROJECT_SUMMARY.md`
