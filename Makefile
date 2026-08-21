.PHONY: help dev up down build test eval migrate sync reindex reset-db clean-db clean-cache

help:
	@echo "Available commands:"
	@echo "  make dev       - Start all containers locally with docker compose"
	@echo "  make up        - Start background services"
	@echo "  make down      - Stop all containers"
	@echo "  make build     - Build all docker images"
	@echo "  make migrate   - Run alembic database migrations"
	@echo "  make sync      - Trigger documentation sync from GitHub"
	@echo "  make clean-cache - Remove search and answer caches without touching data"
	@echo "  make clean-db  - Truncate all tables in the running PostgreSQL container"
	@echo "  make reset-db  - Wipe all volumes and rebuild containers fresh"
	@echo "  make eval      - Run evaluation benchmark suite"

dev:
	docker compose up --build

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

migrate:
	cd services/indexer && alembic upgrade head

clean-db:
	docker exec -i liara-chatbot-db psql -U postgres -d liara_chatbot -c "TRUNCATE TABLE documents, document_revisions, chunks, chunk_occurrences, embedding_cache, sync_runs, url_mapping_issues, conversations, messages, feedback, query_log CASCADE;"
	docker exec -i liara-chatbot-redis redis-cli FLUSHALL

clean-cache:
	@docker exec -i liara-chatbot-redis sh -c 'for pattern in "search_cache:*" "ans_cache:*"; do redis-cli --scan --pattern "$$pattern" | while IFS= read -r key; do [ -z "$$key" ] || redis-cli DEL "$$key" >/dev/null; done; done'

reset-db:
	docker compose down -v

sync:
	curl -X POST http://localhost:8001/admin/sync \
		-H "X-Internal-Token: dev-internal-token" \
		-H "X-Operator-Token: dev-operator-token" \
		-H "Content-Type: application/json" \
		-d '{"mode": "incremental", "dry_run": false}'

eval:
	python eval/run_eval.py --api-base http://localhost:8000
