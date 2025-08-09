# Discord ADR Bot v2.0 - Development Makefile
# Modern Python 3.12 Development Workflow

.PHONY: help install dev test lint format check clean run migrate build docker

# Default target
help: ## Show this help message
	@echo "Discord ADR Bot v2.0 - Development Commands"
	@echo "==========================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Environment Setup
install: ## Install dependencies using UV
	@echo "📦 Installing dependencies..."
	uv sync
	@echo "✅ Dependencies installed"

dev: ## Install development dependencies
	@echo "🔧 Installing development dependencies..."
	uv sync --extra dev
	@echo "✅ Development environment ready"

upgrade: ## Upgrade all dependencies
	@echo "⬆️ Upgrading dependencies..."
	uv lock --upgrade
	uv sync
	@echo "✅ Dependencies upgraded"

# Code Quality
lint: ## Run linting (ruff + mypy)
	@echo "🔍 Running linters..."
	uv run ruff check src tests
	uv run mypy src
	@echo "✅ Linting completed"

# Testing Commands for Discord Bot Commands & Panels
test-fast: ## Run fast unit tests with mocks
	@echo "🏃‍♂️ Running fast tests..."
	uv run pytest -m "unit and mock and not slow" --maxfail=3 --tb=short --disable-warnings --quiet tests/unit/
	@echo "✅ Fast tests completed"

test-commands: ## Run Discord slash command tests
	@echo "⚡ Running command tests..."
	uv run pytest -m "command and mock" --maxfail=5 --tb=short tests/unit/cogs/*/test_*command*.py
	@echo "✅ Command tests completed"

test-panels: ## Run Discord panel interaction tests
	@echo "🎨 Running panel interaction tests..."
	uv run pytest -c pytest_panel.toml --maxfail=5 --tb=short tests/unit/cogs/*/test_*panel*.py
	@echo "✅ Panel tests completed"

test-panels-coverage: ## Run panel tests with coverage
	@echo "📊 Running panel tests with coverage..."
	uv run pytest -c pytest_panel.toml -m "panel" --cov=src/cogs/*/panel --cov-report=html:reports/panel_coverage --cov-report=term-missing tests/unit/cogs/
	@echo "✅ Panel coverage report generated: reports/panel_coverage/index.html"

test-integration: ## Run integration tests
	@echo "🔄 Running integration tests..."
	uv run pytest -m "integration and database" --maxfail=3 --tb=short tests/
	@echo "✅ Integration tests completed"

test-performance: ## Run performance tests
	@echo "⚡ Running performance tests..."
	uv run pytest -m "performance" --benchmark-only --benchmark-sort=mean tests/
	@echo "✅ Performance tests completed"

test-commands-panels: ## Run comprehensive command and panel tests
	@echo "🧪 Running comprehensive command and panel tests..."
	$(MAKE) test-fast
	$(MAKE) test-commands
	$(MAKE) test-panels
	@echo "✅ All command and panel tests completed"

lint-strict: ## Run strict mypy with quality config
	@echo "🔍 Running strict mypy checks..."
	uv run mypy --config-file=quality/mypy.ini src
	@echo "✅ Strict linting completed"

quality-check: ## Run comprehensive quality check using our quality system
	@echo "🏆 Running comprehensive quality check..."
	uv run python scripts/quality_check_tool.py src
	@echo "✅ Quality check completed"

quality-core: ## Check core module quality
	@echo "🔍 Checking core module quality..."
	uv run python scripts/quality_check_tool.py src/core
	@echo "✅ Core quality check completed"

quality-cogs: ## Check cogs module quality
	@echo "🔍 Checking cogs module quality..."
	uv run python scripts/quality_check_tool.py src/cogs
	@echo "✅ Cogs quality check completed"

quality-report: ## Generate detailed quality report
	@echo "📊 Generating quality report..."
	uv run mypy --config-file=quality/mypy.ini src --html-report quality_reports/mypy
	uv run ruff check src --output-format=json > quality_reports/ruff_report.json || true
	@echo "✅ Quality report generated in quality_reports/"

format: ## Format code with black and ruff
	@echo "🎨 Formatting code..."
	uv run black src tests
	uv run ruff check --fix src tests
	@echo "✅ Code formatted"

check: ## Run all code quality checks
	@echo "🧪 Running all quality checks..."
	$(MAKE) format
	$(MAKE) lint
	$(MAKE) test
	@echo "✅ All checks passed"

# Security
security: ## Run security checks
	@echo "🔒 Running security checks..."
	uv run bandit -r src
	uv run safety check
	@echo "✅ Security checks completed"

# Testing
test: ## Run all tests (includes commands and panels)
	@echo "🧪 Running all tests..."
	$(MAKE) test-fast
	$(MAKE) test-commands
	$(MAKE) test-panels
	uv run pytest tests/ --maxfail=10
	@echo "✅ All tests completed"

test-cov: ## Run tests with coverage
	@echo "🧪 Running tests with coverage..."
	uv run pytest --cov=src --cov-report=html:reports/coverage --cov-report=term-missing --cov-report=xml tests/
	@echo "✅ Tests with coverage completed - see reports/coverage/index.html"

test-ci: ## Run tests for CI/CD (strict mode)
	@echo "🏗️ Running CI/CD tests..."
	PYTHONWARNINGS=error TESTING=true ENV=test uv run pytest --strict-markers --strict-config --cov=src --cov-fail-under=70 --cov-report=xml --junit-xml=pytest-results.xml --maxfail=1 --tb=short -q tests/
	@echo "✅ CI/CD tests completed"

test-watch: ## Run tests in watch mode
	@echo "👀 Running tests in watch mode..."
	uv run pytest-watch

test-unit: ## Run unit tests only
	@echo "🧪 Running unit tests..."
	uv run python test_runner.py unit
	@echo "✅ Unit tests completed"

test-integration: ## Run integration tests only
	@echo "🔗 Running integration tests..."
	uv run python test_runner.py integration
	@echo "✅ Integration tests completed"

test-security: ## Run security tests only
	@echo "🔒 Running security tests..."
	uv run python test_runner.py security
	@echo "✅ Security tests completed"

test-performance: ## Run performance tests only
	@echo "⚡ Running performance tests..."
	uv run python test_runner.py performance
	@echo "✅ Performance tests completed"

test-full: ## Run complete test suite with quality checks
	@echo "🎯 Running complete test suite..."
	uv run python test_runner.py full
	@echo "✅ Complete test suite finished"

test-report: ## Generate comprehensive test report
	@echo "📋 Generating test report..."
	uv run python test_runner.py report
	@echo "✅ Test report generated"

# Bot Operations
run: ## Run the bot
	@echo "🚀 Starting Discord ADR Bot..."
	uv run python -m src.main run

run-dev: ## Run the bot in development mode
	@echo "🚀 Starting bot in development mode..."
	uv run python -m src.main run --env development --debug

validate-config: ## Validate configuration
	@echo "🔧 Validating configuration..."
	uv run python -m src.main validate-config

create-config: ## Create sample configuration
	@echo "📝 Creating sample configuration..."
	uv run python -m src.main create-config

# Migration
migrate: ## Run migration from v1.6 to v2.0
	@echo "🔄 Running migration..."
	uv run python scripts/migrate_to_v2.py

# Database Migration & Rollback Testing
test-rollback: ## Test currency system rollback performance
	@echo "⏪ Testing currency rollback performance..."
	uv run python scripts/test_currency_rollback.py --test-size MEDIUM

test-rollback-small: ## Test rollback with small dataset
	@echo "⏪ Testing rollback performance (small dataset)..."
	uv run python scripts/test_currency_rollback.py --test-size SMALL --verbose

test-rollback-large: ## Test rollback with large dataset
	@echo "⏪ Testing rollback performance (large dataset)..."
	uv run python scripts/test_currency_rollback.py --test-size LARGE --verbose

test-rollback-dry-run: ## Dry run rollback test
	@echo "⏪ Dry run rollback test..."
	uv run python scripts/test_currency_rollback.py --dry-run --verbose

db-migrate-apply: ## Apply pending database migrations
	@echo "🗄️ Applying database migrations..."
	uv run alembic upgrade head
	@echo "✅ Database migrations applied"

db-migrate-rollback: ## Rollback last database migration
	@echo "⏪ Rolling back last migration..."
	uv run alembic downgrade -1
	@echo "✅ Database migration rolled back"

db-migrate-status: ## Show migration status
	@echo "📊 Database migration status..."
	uv run alembic current
	uv run alembic history --verbose

# Database
db-init: ## Initialize databases
	@echo "🗄️ Initializing databases..."
	mkdir -p dbs
	@echo "✅ Database directories created"

db-backup: ## Backup databases
	@echo "💾 Backing up databases..."
	mkdir -p backups/$(shell date +%Y%m%d_%H%M%S)
	cp -r dbs backups/$(shell date +%Y%m%d_%H%M%S)/
	@echo "✅ Databases backed up"

# Documentation
docs: ## Generate documentation
	@echo "📚 Generating documentation..."
	uv run mkdocs build
	@echo "✅ Documentation generated"

docs-serve: ## Serve documentation locally
	@echo "📚 Serving documentation..."
	uv run mkdocs serve

# Cleanup
clean: ## Clean up temporary files
	@echo "🧹 Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ htmlcov/
	@echo "✅ Cleanup completed"

deep-clean: clean ## Deep clean including UV cache
	@echo "🧹 Deep cleaning..."
	uv cache clean
	@echo "✅ Deep cleanup completed"

# Building and Distribution
build: ## Build the package
	@echo "🏗️ Building package..."
	uv build
	@echo "✅ Package built"

dist: ## Build package with checksums and size validation
	@echo "📦 Building distribution package..."
	@echo "🧹 Cleaning previous builds..."
	rm -rf dist/ build/
	@echo "🏗️ Building wheel package..."
	uv build
	@echo "📊 Validating package size..."
	@python -c "import os, sys; size = os.path.getsize([f for f in os.listdir('dist') if f.endswith('.whl')][0] if [f for f in os.listdir('dist') if f.endswith('.whl')] else 'nonexistent'); size_mb = size / (1024 * 1024); print(f'Package size: {size_mb:.2f} MB'); sys.exit(1) if size_mb > 25 else None" 2>/dev/null || (echo "❌ Package size exceeds 25MB limit" && exit 1)
	@echo "🔐 Generating SHA256 checksums..."
	@cd dist && sha256sum *.whl *.tar.gz > SHA256SUMS 2>/dev/null || (echo "📁 Generating checksums for available files..." && ls -la *.whl 2>/dev/null | while read f; do sha256sum "$$f"; done > SHA256SUMS)
	@echo "📋 Distribution contents:"
	@ls -la dist/
	@echo "✅ Distribution package ready"

# Docker
docker-build: ## Build Docker image
	@echo "🐳 Building Docker image..."
	docker build -t discord-adr-bot:latest .
	@echo "✅ Docker image built"

docker-run: ## Run bot in Docker
	@echo "🐳 Running bot in Docker..."
	docker run --rm -it \
		--env-file .env \
		-v $(PWD)/dbs:/app/dbs \
		-v $(PWD)/logs:/app/logs \
		discord-adr-bot:latest

docker-compose: ## Run with docker-compose
	@echo "🐳 Starting with docker-compose..."
	docker-compose up -d

# Pre-commit hooks
pre-commit: ## Install pre-commit hooks
	@echo "🪝 Installing pre-commit hooks..."
	uv run pre-commit install
	@echo "✅ Pre-commit hooks installed"

pre-commit-run: ## Run pre-commit on all files
	@echo "🪝 Running pre-commit on all files..."
	uv run pre-commit run --all-files

# Release
version: ## Show current version
	@echo "📋 Current version:"
	@uv run python -c "from src import __version__; print(__version__)"

bump-patch: ## Bump patch version
	@echo "⬆️ Bumping patch version..."
	uv run python scripts/bump_version.py patch

bump-minor: ## Bump minor version
	@echo "⬆️ Bumping minor version..."
	uv run python scripts/bump_version.py minor

bump-major: ## Bump major version
	@echo "⬆️ Bumping major version..."
	uv run python scripts/bump_version.py major

# Monitoring
logs: ## Show recent logs
	@echo "📄 Recent logs..."
	tail -f logs/main.log

logs-error: ## Show recent error logs
	@echo "🚨 Recent error logs..."
	tail -f logs/main_error.log

status: ## Show bot status
	@echo "📊 Bot status..."
	@ps aux | grep "python -m src.main" | grep -v grep || echo "Bot not running"

# Development Workflow
dev-setup: ## Complete development setup
	@echo "🔧 Setting up development environment..."
	$(MAKE) install
	$(MAKE) dev
	$(MAKE) pre-commit
	$(MAKE) db-init
	@echo "✅ Development environment ready!"

dev-reset: ## Reset development environment
	@echo "🔄 Resetting development environment..."
	$(MAKE) deep-clean
	$(MAKE) dev-setup
	@echo "✅ Development environment reset!"

# CI/CD
ci: ## Run CI pipeline locally
	@echo "🚀 Running CI pipeline..."
	$(MAKE) install
	$(MAKE) lint
	$(MAKE) security
	$(MAKE) test-cov
	@echo "✅ CI pipeline completed"

# Quick commands for common tasks
quick-start: dev run-dev ## Quick development start

quick-test: format test ## Quick test run

quick-check: format lint test ## Quick quality check