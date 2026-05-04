.PHONY: help infra-up infra-down backend-install backend-dev backend-migrate backend-test frontend-install frontend-dev etl-import clean

help:
	@echo "Castulo Nuevo - comandos disponibles:"
	@echo ""
	@echo "  make infra-up          Levanta Postgres + Redis (Docker)"
	@echo "  make infra-down        Apaga Postgres + Redis"
	@echo ""
	@echo "  make backend-install   Instala dependencias del backend"
	@echo "  make backend-dev       Arranca Flask en modo dev"
	@echo "  make backend-migrate   Corre migraciones de Alembic"
	@echo "  make backend-test      Corre pytest"
	@echo ""
	@echo "  make frontend-install  Instala deps del frontend"
	@echo "  make frontend-dev      Arranca Vite dev server"
	@echo ""
	@echo "  make etl-import        Corre ETL desde DBFs del viejo"
	@echo "  make clean             Borra caches y builds"

infra-up:
	docker compose up -d

infra-down:
	docker compose down

backend-install:
	cd backend && python -m venv .venv && .venv/Scripts/pip install -e .[dev]

backend-dev:
	cd backend && .venv/Scripts/flask run --debug

backend-migrate:
	cd backend && .venv/Scripts/flask db upgrade

backend-test:
	cd backend && .venv/Scripts/pytest

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

etl-import:
	cd etl && python import_dbfs.py --source ../../viejo/DBF

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name node_modules -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name dist -exec rm -rf {} + 2>/dev/null || true
