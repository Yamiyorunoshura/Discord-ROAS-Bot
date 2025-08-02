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
test: ## Run tests
	@echo "🧪 Running tests..."
	uv run pytest
	@echo "✅ Tests completed"

test-cov: ## Run tests with coverage
	@echo "🧪 Running tests with coverage..."
	uv run pytest --cov=src --cov-report=html --cov-report=term
	@echo "✅ Tests with coverage completed"

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

# Building
build: ## Build the package
	@echo "🏗️ Building package..."
	uv build
	@echo "✅ Package built"

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