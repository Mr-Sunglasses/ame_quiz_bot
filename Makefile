.DEFAULT_GOAL := help

.PHONY: help install sync run test lint docker-build docker-up docker-down

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Create venv and install all dependencies (including dev)
	uv sync --all-extras

sync: ## Sync dependencies without dev extras
	uv sync

run: ## Run the bot (long-polling mode)
	uv run python -m src.main

test: ## Run tests
	uv run pytest tests/ -v

docker-build: ## Build Docker image
	docker compose build

docker-up: ## Start the bot via Docker Compose
	docker compose up -d

docker-down: ## Stop Docker Compose services
	docker compose down
