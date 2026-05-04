# Operations runbook - Jarvis Core

Procedimientos operacionales basicos para mantener Jarvis Core en produccion.

## Logs y monitoring

### Fly.io
```bash
# Logs en vivo
flyctl logs

# Logs historicos (ultimas 24h)
flyctl logs --since 24h

# Status de la app
flyctl status

# Metricas (CPU, memoria, requests)
flyctl dashboard
```

### Railway
Dashboard -> Project -> Service -> Logs / Metrics tab.

### VPS (docker-compose)
```bash
docker compose -f docker-compose.prod.yml logs -f --tail 100 backend
docker compose -f docker-compose.prod.yml logs --since 24h
```

### Sentry (opcional, recomendado)
1. Crear proyecto en https://sentry.io
2. Agregar `sentry-sdk[flask]` a `pyproject.toml` extras
3. En `app/__init__.py`:
   ```python
   import sentry_sdk
   from sentry_sdk.integrations.flask import FlaskIntegration
   sentry_sdk.init(dsn=os.getenv("SENTRY_DSN"), integrations=[FlaskIntegration()], traces_sample_rate=0.1)
   ```
4. Setear secret: `flyctl secrets set SENTRY_DSN=https://...`

---

## Backups Postgres

### Neon
Hace backups automaticos cada 24h con retencion variable segun plan:
- Free: 7 dias
- Pro ($19/mo): 30 dias + branching (clones instantaneos)

Manual snapshot via UI: Dashboard -> Branches -> Create branch from current.

### Adicional: pg_dump cron a S3 (recomendado)

Para retencion 10 anos (requerido por AFIP), Neon free tier no alcanza. Esquema:

```bash
# Cron diario en algun host (ej: el VPS o un GitHub Action scheduled)
pg_dump "$DATABASE_URL" | gzip > /tmp/jarvis-$(date +%F).sql.gz
rclone copy /tmp/jarvis-$(date +%F).sql.gz s3:jarvis-backups/daily/
```

GitHub Action equivalente (`.github/workflows/backup.yml`):
```yaml
name: Postgres backup
on:
  schedule:
    - cron: "0 3 * * *"  # 3 AM UTC diario
jobs:
  backup:
    runs-on: ubuntu-latest
    steps:
      - run: |
          apt-get update && apt-get install -y postgresql-client
          pg_dump "${{ secrets.DATABASE_URL }}" | gzip > backup.sql.gz
          # Upload a S3/B2/Backblaze
          aws s3 cp backup.sql.gz s3://jarvis-backups/daily/$(date +%F).sql.gz
```

### Restore

```bash
gunzip -c backup.sql.gz | psql "$DATABASE_URL"
```

ATENCION: restore reemplaza el contenido. Hacer en una DB nueva primero, validar, recien luego switchear DNS.

---

## Rotacion de secrets

### JWT_SECRET_KEY
Rotar cada 6-12 meses o si hay sospecha de leak.

```bash
NEW_KEY=$(openssl rand -hex 32)
flyctl secrets set JWT_SECRET_KEY=$NEW_KEY
# Esto invalida TODOS los tokens activos -> usuarios deben re-loguear.
```

Para rotacion sin downtime, soportar dual-key (no implementado todavia, requeriria PR al backend).

### SECRET_KEY (Flask)
Solo se usa para sesiones/cookies firmadas internas. Rotar igual que JWT.

### Database password
Neon: Dashboard -> Settings -> Reset password. Actualiza `DATABASE_URL` en Fly:
```bash
flyctl secrets set DATABASE_URL="postgresql+psycopg://user:NEW_PASS@..."
```

---

## AFIP cert renewal

Los certificados AFIP duran **2 anos**. Antes de que expiren:

1. Generar nuevo CSR en el portal AFIP (Mis Aplicaciones Web -> Administracion de Certificados Digitales)
2. AFIP devuelve el `.crt` nuevo
3. Subir al volume en Fly:
   ```bash
   flyctl ssh sftp shell
   > put new_cert.crt /app/instance/afip_certs/<cuit>/certificado.crt
   > exit
   ```
4. Restart la app: `flyctl machine restart`
5. Smoke test: emitir factura test y verificar CAE.

La key privada SE MANTIENE - solo cambia el cert. NO regenerar la key salvo compromiso.

---

## Update dependencies

### Backend
Mensual:
```bash
cd backend
pip install --upgrade pip-tools
pip-compile --upgrade pyproject.toml
# Revisar diff, correr tests
pytest
# Commit y deploy
```

### Frontend
```bash
cd frontend
npx npm-check-updates -u
npm install
npm run build
# Smoke test local
npm run dev
```

CRITICO: revisar changelogs antes de upgrades major. Rotar `package-lock.json` si hay vulnerabilidades reportadas (`npm audit`).

### Imagen Docker base
Cada 3-6 meses revisar:
- `python:3.11-slim` -> `python:3.12-slim` cuando madure
- `node:20-alpine` -> `node:22-alpine` cuando sea LTS estable
- `postgres:16-alpine` -> `postgres:17-alpine` cuando salga

NO actualizar major en produccion sin testear en staging primero.

---

## Restauracion ante caida total

### "Mi backend esta down"
1. `flyctl status` - ver health checks
2. `flyctl logs` - ultimos errores
3. Si es OOM: `flyctl scale vm shared-cpu-1x --memory 1024`
4. Si es DB: chequear Neon dashboard, eventualmente fallback a backup
5. Restart como ultimo recurso: `flyctl machine restart`

### "La DB de Neon esta caida"
1. Status page: https://status.neon.tech
2. Plan B: levantar Postgres en otro provider, restaurar ultimo backup, switchear `DATABASE_URL` en Fly secret. Tiempo: ~15 min si tenes el backup a mano.

### "Cloudflare Pages caido"
- Frontend dejara de cargar pero backend sigue funcionando.
- Plan B: `wrangler pages deploy dist` a otro project, switchear DNS.

---

## Escalado

### Vertical (mas memoria/CPU al backend)
```bash
flyctl scale vm shared-cpu-2x --memory 1024
```

### Horizontal (mas instancias)
SocketIO requiere sticky sessions O Redis pub/sub. Si seguis sin Redis:
```bash
# NO escalar horizontal sin Redis - los eventos socketio se pierden entre instancias.
```

Con Redis:
```bash
flyctl scale count 2  # 2 instancias
flyctl secrets set SOCKETIO_MESSAGE_QUEUE=$REDIS_URL  # backend usa Redis pub/sub
```

### DB
Neon scales automaticamente. Si alcanzas el plan free (3GB), upgrade a $19/mo (10GB) o $69/mo (50GB).

---

## Monitoring checklist semanal

- [ ] Revisar Sentry para errores nuevos
- [ ] Chequear uso de DB en Neon Dashboard (storage usage, query perf)
- [ ] Verificar que los backups cron funcionaron (listar archivos en S3)
- [ ] Revisar logs de Fly: errores recurrentes, slow queries
- [ ] CPU/memoria sostenida > 70% -> considerar scale up
- [ ] Disk de Postgres > 80% -> upgrade plan o limpiar data vieja

## Auditoria mensual

- [ ] Validar que las migraciones de Alembic estan al dia (`flask db current` vs `flask db heads`)
- [ ] Probar restore de backup en staging
- [ ] Verificar que los certs SSL no expiran proximo (Caddy/Fly auto-renew, pero confirmar)
- [ ] Cert AFIP: cuanto falta para vencer?
- [ ] Rotar passwords de DB si pasa mas de 12 meses
