POETRY ?= $(if $(wildcard venv/bin/poetry),venv/bin/poetry,poetry)
APP_MODULE ?= app.main:app
HOST ?= 127.0.0.1
PORT ?= 8081

.DEFAULT_GOAL := help
.PHONY: help install run test lint lint-fix format format-check lock-check check

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "%-14s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install project and development dependencies
	$(POETRY) install --with dev --no-root

run: ## Run the FastAPI app with auto-reload
	$(POETRY) run uvicorn $(APP_MODULE) --reload --host $(HOST) --port $(PORT)

test: ## Run the test suite
	$(POETRY) run pytest -q

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
