.PHONY: help infra-up infra-down backend-install backend-dev backend-migrate backend-test frontend-install frontend-dev etl-import etl-import-xls etl-import-xls-dry clean

# Paths a los .xls legacy en la raiz del repo (un nivel arriba de PROYECTO ERP).
# Override-able desde la linea de comandos: make etl-import-xls XLS_FILE1=/otro/path.xls
XLS_FILE1 ?= ../3EB052EF592E1D591FBB8C-h00ugz.xls
XLS_FILE2 ?= ../3EB07DF9C6673E43F507BE-615s0b.xls

help:
	@echo "Castulo Nuevo - comandos disponibles:"
	@echo ""
	@echo "  make infra-up               Levanta Postgres + Redis (Docker)"
	@echo "  make infra-down             Apaga Postgres + Redis"
	@echo ""
	@echo "  make backend-install        Instala dependencias del backend"
	@echo "  make backend-dev            Arranca Flask en modo dev"
	@echo "  make backend-migrate        Corre migraciones de Alembic"
	@echo "  make backend-test           Corre pytest"
	@echo ""
	@echo "  make frontend-install       Instala deps del frontend"
	@echo "  make frontend-dev           Arranca Vite dev server"
	@echo ""
	@echo "  make etl-import             Corre ETL desde DBFs del viejo"
	@echo "  make etl-import-xls         Corre ETL desde los .xls legacy (REAL — pide backup antes)"
	@echo "  make etl-import-xls-dry     Corre ETL desde los .xls legacy (dry-run, no escribe)"
	@echo "  make clean                  Borra caches y builds"

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

etl-import-xls:
	@echo "Importacion XLS REAL — asegurate de tener backup (pg_dump) antes."
	python -m etl.xls.import_xls \
		--proveedores $(XLS_FILE1) \
		--articulos $(XLS_FILE2) \
		--articulos-proveedores $(XLS_FILE1)

etl-import-xls-dry:
	@echo "Importacion XLS DRY-RUN — no escribe a la DB."
	python -m etl.xls.import_xls \
		--proveedores $(XLS_FILE1) \
		--articulos $(XLS_FILE2) \
		--articulos-proveedores $(XLS_FILE1) \
		--dry-run

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name node_modules -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name dist -exec rm -rf {} + 2>/dev/null || true
