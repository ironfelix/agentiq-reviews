# AgentIQ MVP Test Suite

Comprehensive test suite for the AgentIQ MVP service, covering unit tests, integration tests, and end-to-end tests.

## Quick Start

```bash
# Install test dependencies
cd apps/reviews
pip install -r requirements-test.txt

# Run all tests
pytest

# Run with coverage report
pytest --cov=backend --cov-report=html

# Run specific test categories
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests only
pytest -m e2e           # End-to-end tests only

# Run specific test file
pytest tests/test_auth.py

# Run with verbose output
pytest -v

# Run in parallel (faster)
pip install pytest-xdist
pytest -n auto
```

## Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures and test configuration
├── test_auth.py             # Unit tests for authentication (Telegram, JWT)
├── test_database.py         # Unit tests for database models
├── test_llm_analyzer.py     # Unit tests for LLM analyzer with guardrails
├── test_api_endpoints.py    # Integration tests for API endpoints
├── test_celery_tasks.py     # Integration tests for Celery tasks
├── test_e2e.py              # End-to-end tests for user flows
└── README.md                # This file
```

## Test Categories

### Unit Tests (`@pytest.mark.unit`)
Test individual functions and classes in isolation:
- **Auth module** (`test_auth.py`): Telegram authentication, JWT creation/validation, token refresh
- **Database models** (`test_database.py`): Model creation, constraints, relationships
- **LLM analyzer** (`test_llm_analyzer.py`): Guardrails, sanitization, validation

**Coverage:** ~150 unit tests

### Integration Tests (`@pytest.mark.integration`)
Test API endpoints and component integration:
- **API endpoints** (`test_api_endpoints.py`):
  - Health check
  - Auth flow (Telegram callback, invite codes, logout)
  - Task management (create, list, status, delete)
  - Report viewing and sharing
  - Frontend routes
- **Celery tasks** (`test_celery_tasks.py`):
  - WBCON API integration (mocked)
  - Task execution flow
  - Error handling

**Coverage:** ~60 integration tests

### End-to-End Tests (`@pytest.mark.e2e`)
Test complete user journeys from start to finish:
- New user registration → invite code → task creation → report viewing
- Existing user login → task list → report access
- Share link generation and public access
- Error scenarios (unauthorized access, invalid data)
- Multi-task management

**Coverage:** ~25 e2e tests

## Key Features

### Mocking Strategy
- **External APIs**: All external services (WBCON, WB CDN, DeepSeek LLM) are mocked using `responses` and `unittest.mock`
- **Celery tasks**: Mocked using `pytest-mock` to avoid async execution during tests
- **Database**: In-memory SQLite database for fast, isolated tests
- **Redis**: Separate Redis DB (15) for tests to avoid conflicts

### Test Database
- Uses in-memory SQLite for speed
- Fresh database for each test
- Automatic cleanup after each test
- Async support via `aiosqlite`

### Fixtures

#### Database Fixtures
- `test_db_engine`: Async database engine
- `test_db_session`: Async database session with automatic rollback
- `test_user`: User with invite code
- `test_user_without_invite`: User without invite code (for invite flow tests)
- `test_task`: Pending task
- `completed_task`: Completed task with report

#### Data Fixtures
- `sample_feedbacks`: Sample feedback data
- `sample_wbcon_response`: WBCON API response
- `sample_wb_card`: WB card API response
- `mock_telegram_auth_data`: Valid Telegram auth data with HMAC

#### Auth Fixtures
- `auth_headers`: HTTP headers with valid session token
- `test_client`: Async HTTP client with database override

## Configuration

### Environment Variables
Tests automatically set test environment variables in `conftest.py`:
- `ENVIRONMENT=test` - Enables test mode
- `DATABASE_URL=sqlite+aiosqlite:///:memory:` - In-memory database
- `REDIS_URL=redis://localhost:6379/15` - Separate Redis DB
- `USE_LLM=0` - Disable LLM calls by default
- Test tokens for Telegram, WBCON, DeepSeek

### pytest.ini
- Coverage threshold: 80% (configurable)
- HTML coverage report in `htmlcov/`
- Async test support
- Test markers for filtering

## Writing New Tests

### Unit Test Example
```python
import pytest

@pytest.mark.unit
class TestMyFeature:
    def test_something(self):
        """Test description."""
        assert 1 + 1 == 2
```

### Integration Test Example
```python
import pytest

@pytest.mark.integration
class TestMyAPI:
    async def test_endpoint(self, test_client, test_user):
        """Test API endpoint."""
        from backend.auth import create_session_token

        token = create_session_token(test_user.telegram_id)
        response = await test_client.get(
            "/api/endpoint",
            cookies={"session_token": token},
        )
        assert response.status_code == 200
```

### E2E Test Example
```python
import pytest

@pytest.mark.e2e
class TestUserJourney:
    async def test_complete_flow(self, test_client, test_db_session):
        """Test complete user journey."""
        # Step 1: Login
        # Step 2: Create task
        # Step 3: View report
        pass
```

### Using Mocks
```python
import pytest
import responses

@pytest.mark.integration
class TestExternalAPI:
    @responses.activate
    def test_api_call(self):
        """Test with mocked HTTP response."""
        responses.add(
            responses.GET,
            "https://api.example.com/data",
            json={"result": "ok"},
            status=200,
        )
        # Your test code here
```

## Best Practices

### 1. Test Isolation
- Each test should be independent
- Use fixtures for setup/teardown
- Don't rely on test execution order

### 2. Clear Test Names
- Use descriptive test names: `test_create_task_unauthorized`
- Follow pattern: `test_<what>_<condition>_<expected_outcome>`

### 3. Test One Thing
- Each test should verify one behavior
- Use parametrize for testing multiple inputs:
```python
@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (2, 4),
    (3, 6),
])
def test_double(input, expected):
    assert double(input) == expected
```

### 4. Mock External Services
- Never make real API calls in tests
- Use `responses` for HTTP mocks
- Use `unittest.mock.patch` for function mocks

### 5. Async Tests
- Mark async tests with `async def`
- Use `await` for async operations
- pytest-asyncio handles the event loop

### 6. Database Tests
- Use `test_db_session` fixture
- Changes are automatically rolled back
- Each test gets fresh database

## CI/CD Integration

### GitHub Actions Example
```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          cd apps/reviews
          pip install -r requirements.txt
          pip install -r requirements-test.txt
      - name: Run tests
        run: |
          cd apps/reviews
          pytest --cov=backend --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

## Troubleshooting

### Tests hanging
- Check for missing `await` in async tests
- Ensure Redis is running for integration tests
- Check for infinite loops in code

### Import errors
- Ensure you're running from `apps/reviews/` directory
- Check `sys.path` modifications in conftest.py
- Verify all dependencies installed

### Database errors
- Check fixture dependencies
- Ensure proper session cleanup
- Look for missing `await` on database operations

### Flaky tests
- Check for time-dependent assertions
- Use `freezegun` for time mocking
- Ensure proper test isolation

## Coverage Report

View coverage report:
```bash
# Generate HTML coverage report
pytest --cov=backend --cov-report=html

# Open in browser (macOS)
open htmlcov/index.html

# Open in browser (Linux)
xdg-open htmlcov/index.html
```

## Running Tests in Docker

```bash
# Build test container
docker build -t agentiq-tests -f Dockerfile.test .

# Run tests
docker run --rm agentiq-tests pytest

# Run with coverage
docker run --rm agentiq-tests pytest --cov=backend
```

## Performance

Test suite performance on M1 MacBook Pro:
- Unit tests: ~5 seconds
- Integration tests: ~10 seconds
- E2E tests: ~15 seconds
- **Total: ~30 seconds**

To speed up:
```bash
# Run in parallel (requires pytest-xdist)
pip install pytest-xdist
pytest -n auto  # Uses all CPU cores
```

## Contributing

When adding new features:
1. Write tests first (TDD)
2. Ensure all tests pass: `pytest`
3. Check coverage: `pytest --cov=backend`
4. Add new fixtures to `conftest.py` if reusable
5. Document complex test scenarios

## Contact

For questions about tests, see:
- Main README: `../README.md`
- API documentation: `../../docs/API.md`
- Architecture: `../PROJECT_SUMMARY.md`
