# CASA SALCO

Sistema de gestión integral para almacén multi-sucursal.
Reingeniería del sistema Harbour legacy (`../viejo/`).

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Flask + SQLAlchemy + Alembic + Flask-SocketIO + Celery |
| Validación | Pydantic |
| Base de datos | PostgreSQL (central) + SQLite (local en cajas) |
| Cache / pub-sub | Redis |
| Frontend | React + Vite + TypeScript + Tailwind + shadcn/ui |
| Estética | Apple-like (SF fonts, Apple Blue accent, radius 12px) |
| Cliente local POS | Tauri + React (Fase 2) |
| Hardware | AFIP WSFEv1 (PyAfipWs) · 3NSTAR ESC/POS · Kretz/Systel serial |
| Infra | Railway / Fly.io |

## Estructura

```
nuevo/
├── backend/          # Flask API + SocketIO
├── frontend/         # React SPA (web + PWA mobile)
├── etl/              # Scripts de importación desde DBFs viejos
├── infra/            # Configs de deployment
├── docs/             # Documentación de arquitectura
└── docker-compose.yml
```

## Requisitos de desarrollo

- Python 3.12+
- Node.js 20+
- Docker Desktop (para Postgres + Redis locales)

## Arranque rápido

```bash
# 1. Levantar Postgres + Redis
docker compose up -d

# 2. Backend
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -e .[dev]
flask db upgrade
flask run

# 3. Frontend (otra terminal)
cd frontend
npm install
npm run dev

# 4. ETL (una vez, para importar del sistema viejo)
cd etl
python import_dbfs.py --source ../../viejo/DBF --dry-run
```

### Importación desde Excel legacy

Para importar productos / proveedores / catálogo desde los `.xls` legacy de
CASA SALCO (formato BIFF, Excel 97-2003), ver
[etl/xls/README.md](etl/xls/README.md). Atajos:

```bash
make etl-import-xls-dry   # dry-run, no escribe a la DB
make etl-import-xls       # corrida real (snapshot pg_dump previo recomendado)
```

## Roadmap

- **Fase 1** (MVP — 8-10 sem): sync de precios multi-sucursal + ETL + artículos + dashboard básico
- **Fase 2** (10-12 sem): POS Tauri + AFIP + 3NSTAR + balanzas + offline queue
- **Fase 3** (8 sem): dashboard premium + heatmaps + mapas + alertas + PWA mobile
- **Fase 4** (6-8 sem): OCR + datamining + export Excel contador

## Dolor #1 que ataca el MVP

Sincronización de precios entre las sucursales en tiempo real.
