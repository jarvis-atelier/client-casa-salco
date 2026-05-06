# Deploy guide - Jarvis Core

Guia paso a paso para deployar Jarvis Core a produccion. Soporta 3 targets:

1. **Fly.io + Neon + Cloudflare Pages** (RECOMENDADO - region eze, latencia minima Argentina)
2. **Railway + Neon + Cloudflare Pages** (alternativa, mas simple)
3. **VPS propio + docker-compose** (control total, requiere mas ops)

## Costos esperados (USD/mes)

| Componente   | Tier free                    | Costo estimado |
|--------------|------------------------------|----------------|
| Postgres (Neon) | 3 GB storage, branching free | $0 - $19       |
| Redis (Upstash) | 10k commands/dia free        | $0 - $10       |
| Backend (Fly.io)| 3 maquinas shared free       | $0 - $30       |
| Frontend (CF Pages) | unlimited static         | $0             |
| **Total**       |                              | **$0 - $60**   |

Para producir: subir Postgres a $19/mo (10GB) y backend a $30/mo (1 dedicated CPU).
Total realista produccion: **~$50/mo**.

---

## Pre-requisitos

- Cuenta en GitHub (para CI/CD)
- Cuenta en [Neon](https://neon.tech) (Postgres)
- Cuenta en [Fly.io](https://fly.io) o [Railway](https://railway.app)
- Cuenta en [Cloudflare](https://cloudflare.com) (frontend + DNS)
- Cuenta en [Upstash](https://upstash.com) (Redis, opcional)
- Dominio propio (ej: `jarvis-core.com`)
- Para AFIP real: certificado y key emitidos por AFIP a tu CUIT

---

## Opcion 1: Fly.io + Neon + Cloudflare Pages (RECOMENDADO)

### Step 1 - Crear Postgres en Neon

1. Login a https://console.neon.tech
2. Create project: `jarvis-core`, region: `aws-us-east-1` (mas cercana a Fly eze)
3. Copiar connection string del dashboard. Ejemplo:
   ```
   postgresql://user:pass@ep-xxx.us-east-1.aws.neon.tech/neondb
   ```
4. **IMPORTANTE**: agregar `?sslmode=require` y prefijo `+psycopg`:
   ```
   postgresql+psycopg://user:pass@ep-xxx.us-east-1.aws.neon.tech/neondb?sslmode=require
   ```

### Step 2 - Crear Redis en Upstash (opcional)

Si vas a usar SocketIO multi-instancia o Celery, necesitas Redis. Sino, podes saltearte este paso (SocketIO funciona en modo single-instance sin Redis).

1. Login a https://console.upstash.com
2. Create Database, region: us-east-1
3. Copiar `redis://default:pass@host:port` del dashboard

### Step 3 - Crear app en Fly.io

```bash
# Instalar flyctl (una vez)
curl -L https://fly.io/install.sh | sh
flyctl auth login

# Desde la raiz del repo:
flyctl launch --no-deploy --copy-config --name jarvis-core
# Esto detecta fly.toml y NO crea Postgres (usamos Neon externo).
```

### Step 4 - Setear secrets

```bash
flyctl secrets set \
  DATABASE_URL="postgresql+psycopg://user:pass@ep-xxx.us-east-1.aws.neon.tech/neondb?sslmode=require" \
  REDIS_URL="redis://default:pass@host:port" \
  JWT_SECRET_KEY="$(openssl rand -hex 32)" \
  SECRET_KEY="$(openssl rand -hex 32)" \
  AFIP_CUIT="20XXXXXXXXX" \
  CORS_ORIGINS="https://app.jarvis-core.com"
```

Para agregar Gemini OCR:
```bash
flyctl secrets set OCR_MODE=gemini GEMINI_API_KEY="AIzaSy-xxxxx"
```

### Step 5 - Crear volume para certs AFIP (si vas a usar AFIP real)

```bash
flyctl volumes create afip_certs --region eze --size 1
```

### Step 6 - Deploy

```bash
flyctl deploy
```

Fly compila el `backend/Dockerfile`, ejecuta `flask db upgrade` automaticamente al arrancar (CMD del Dockerfile), y queda corriendo en `https://jarvis-core.fly.dev`.

### Step 7 - Migrar datos SQLite existentes (si los hay)

```bash
# Desde tu maquina local:
python scripts/migrate_sqlite_to_postgres.py \
  --sqlite backend/instance/casasalco.db \
  --postgres "postgresql+psycopg://user:pass@ep-xxx.us-east-1.aws.neon.tech/neondb?sslmode=require"
```

Si el destino esta vacio, podes correr antes el seed:
```bash
DATABASE_URL="postgresql+psycopg://...?sslmode=require" \
ADMIN_EMAIL="admin@jarvis-core.com" \
ADMIN_PASSWORD="$(openssl rand -base64 24)" \
python scripts/seed-prod.py
```

### Step 8 - Subir certs AFIP (cuando los tengas)

```bash
# Por SFTP via fly:
flyctl ssh sftp shell
> put /local/path/certificado.crt /app/instance/afip_certs/<cuit>/certificado.crt
> put /local/path/privada.key /app/instance/afip_certs/<cuit>/privada.key
> exit

# Setear paths y switchear AFIP a real
flyctl secrets set \
  AFIP_MODE=pyafipws \
  AFIP_HOMO=false \
  AFIP_CERT_PATH=/app/instance/afip_certs/<cuit>/certificado.crt \
  AFIP_KEY_PATH=/app/instance/afip_certs/<cuit>/privada.key
```

### Step 9 - Frontend en Cloudflare Pages

Opcion A: con `wrangler` CLI:
```bash
cd frontend
npm run build
npx wrangler pages deploy dist --project-name jarvis-core
```

Opcion B: via GitHub integration (RECOMENDADO):
1. Login Cloudflare Dashboard -> Pages -> Create -> Connect to Git
2. Seleccionar el repo
3. Build config:
   - Build command: `cd frontend && npm ci && npm run build`
   - Build output: `frontend/dist`
   - Env var: `VITE_API_URL=https://jarvis-core.fly.dev/api`
4. Save and deploy

### Step 10 - Custom domain

**Backend** (api.jarvis-core.com):
```bash
flyctl certs add api.jarvis-core.com
# Crear CNAME en Cloudflare DNS: api.jarvis-core.com -> jarvis-core.fly.dev
```

**Frontend** (app.jarvis-core.com):
- Cloudflare Pages -> Custom domain -> agregar `app.jarvis-core.com`
- Cloudflare crea el DNS automaticamente

Actualizar `CORS_ORIGINS` y `VITE_API_URL` con los dominios finales:
```bash
flyctl secrets set CORS_ORIGINS="https://app.jarvis-core.com"
# Re-build frontend con VITE_API_URL=https://api.jarvis-core.com/api
```

### Step 11 - Smoke test post-deploy

```bash
# Health
curl https://api.jarvis-core.com/healthz

# Login (debe devolver JWT)
curl -X POST https://api.jarvis-core.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@jarvis-core.com","password":"<la que pusiste>"}'

# Frontend carga
curl -I https://app.jarvis-core.com
```

Probar el flow completo desde la UI: login -> crear factura -> verificar CAE (mock o real).

---

## Opcion 2: Railway + Neon + Cloudflare Pages

Railway es mas simple que Fly pero NO tiene region Buenos Aires (latencia mas alta).

```bash
# Instalar Railway CLI
npm install -g @railway/cli
railway login

# Crear proyecto
railway init --name jarvis-core

# Conectar repo y deployar
railway link
railway up
```

Setear vars de entorno desde el Dashboard de Railway o:
```bash
railway variables set DATABASE_URL="..." JWT_SECRET_KEY="..." ...
```

Frontend igual que Opcion 1.

---

## Opcion 3: VPS propio + docker-compose

Para deploys con control total (Hetzner CX21 = 4 EUR/mes, suficiente para 1 sucursal).

### Setup VPS (Ubuntu 22.04 LTS)

```bash
# Instalar Docker + Compose
curl -fsSL https://get.docker.com | sh
apt install -y docker-compose-plugin

# Caddy como reverse proxy con SSL automatico
apt install -y caddy

# Clonar el repo
git clone https://github.com/<user>/jarvis-core.git
cd jarvis-core

# Crear .env.prod (NO commitear)
cat > .env.prod <<EOF
POSTGRES_USER=jarvis
POSTGRES_PASSWORD=$(openssl rand -base64 32)
POSTGRES_DB=jarvis
JWT_SECRET_KEY=$(openssl rand -hex 32)
SECRET_KEY=$(openssl rand -hex 32)
AFIP_CUIT=20XXXXXXXXX
AFIP_MODE=mock
CORS_ORIGINS=https://app.jarvis-core.com
EOF

# Levantar todo
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d

# Ver logs
docker compose -f docker-compose.prod.yml logs -f backend
```

### Caddy reverse proxy (`/etc/caddy/Caddyfile`):

```
api.jarvis-core.com {
    reverse_proxy localhost:8080
}

app.jarvis-core.com {
    reverse_proxy localhost:80
}
```

```bash
systemctl reload caddy
```

Caddy obtiene certs Lets Encrypt automaticamente.

### Backups automaticos (Postgres -> S3)

Cron diario:
```bash
# /etc/cron.daily/jarvis-backup
#!/bin/bash
docker exec casasalco_postgres pg_dump -U jarvis jarvis | gzip > /backups/jarvis-$(date +%F).sql.gz
# Subir a S3 / Backblaze B2 con rclone
rclone copy /backups remote:jarvis-backups
# Limpiar locales > 7 dias
find /backups -type f -mtime +7 -delete
```

---

## CI/CD via GitHub Actions

`.github/workflows/ci.yml` corre en cada push/PR:
- Backend: ruff lint + pytest contra Postgres real
- Frontend: tsc check + build
- Docker: smoke build de ambas imagenes (solo en push)

`.github/workflows/deploy.yml` corre en tags `v*.*.*`:
- Deploy backend a Fly.io
- Deploy frontend a Cloudflare Pages

### Secrets necesarios en GitHub

Settings -> Secrets and variables -> Actions:

| Secret                     | Como obtenerlo                                   |
|----------------------------|--------------------------------------------------|
| `FLY_API_TOKEN`            | `flyctl auth token`                              |
| `RAILWAY_TOKEN`            | Railway Dashboard -> Account -> Tokens           |
| `CLOUDFLARE_API_TOKEN`     | CF Dashboard -> My Profile -> API Tokens         |
| `CLOUDFLARE_ACCOUNT_ID`    | CF Dashboard -> Sidebar derecho                  |
| `PROD_API_URL`             | `https://api.jarvis-core.com/api`                |

### Tag y deploy

```bash
git tag v1.0.0
git push origin v1.0.0
# GitHub Actions deploya automaticamente a Fly + Cloudflare
```

---

## Troubleshooting

### "psycopg2 not found" al deployar
El backend usa `psycopg[binary]` v3 (declarado en pyproject.toml). Si ves errores con `psycopg2`, alguna lib vieja todavia lo importa. Revisar requirements.

### "flask db upgrade fails" en Fly
- Verificar que `DATABASE_URL` este seteada como secret.
- SSH al machine: `flyctl ssh console` -> `flask db current` para ver estado.

### CORS rechaza requests del frontend
- `CORS_ORIGINS` en backend debe incluir el dominio EXACTO del frontend (sin trailing slash).
- Multiples origins: separar con coma: `https://app.jarvis-core.com,https://staging.jarvis-core.com`.

### SocketIO no conecta en produccion
- Detras de Cloudflare: activar "WebSockets" en Network settings.
- Detras de nginx: configurar `proxy_set_header Upgrade $http_upgrade`.
- Sin Redis: solo funciona en single-instance (ok para empezar).

### Migracion SQLite -> Postgres falla con "syntax error"
- SQLite a veces guarda fechas como string. Si SQLAlchemy no las convierte, ajustar el script `migrate_sqlite_to_postgres.py` para hacer cast explicito.
- Booleans: 0/1 en SQLite vs true/false en Postgres - SQLAlchemy lo maneja, pero validar con `--dry-run` primero.
