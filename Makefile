POETRY ?= $(if $(wildcard venv/bin/poetry),venv/bin/poetry,poetry)
APP_MODULE ?= app.main:app
HOST ?= 127.0.0.1
PORT ?= 8081

.DEFAULT_GOAL := help
.PHONY: help install run test lint lint-fix format format-check lock-check check \
	db-revision db-upgrade db-current db-history

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "%-14s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install project and development dependencies
	$(POETRY) install --with dev --no-root

run: ## Run the FastAPI app with auto-reload
	$(POETRY) run uvicorn $(APP_MODULE) --reload --host $(HOST) --port $(PORT)

test: ## Run the test suite
	$(POETRY) run pytest -q

db-revision: ## Create an Alembic revision (use REVISION_MESSAGE='...')
	@test -n "$(REVISION_MESSAGE)" || { echo "Set REVISION_MESSAGE, e.g. make db-revision REVISION_MESSAGE='create conversation table'" >&2; exit 2; }
	$(POETRY) run alembic revision -m "$(REVISION_MESSAGE)"

db-upgrade: ## Apply all pending database migrations
	$(POETRY) run alembic upgrade head

db-current: ## Show the database's current Alembic revision
	$(POETRY) run alembic current

db-history: ## Show migration history
	$(POETRY) run alembic history

lint: ## Run Ruff lint checks
	$(POETRY) run ruff check app tests

lint-fix: ## Apply Ruff's safe automatic lint fixes
	$(POETRY) run ruff check --fix app tests

format: ## Format application and test code
	$(POETRY) run ruff format app tests

format-check: ## Check formatting without changing files
	$(POETRY) run ruff format --check app tests

lock-check: ## Check Poetry configuration and lockfile consistency
	$(POETRY) check --lock

check: lock-check lint format-check test ## Run all project checks
