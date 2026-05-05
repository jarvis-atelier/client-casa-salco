# ETL XLS — Importación desde Excel legacy

Importador one-shot, idempotente, que lee los `.xls` (formato BIFF, Excel 97-2003)
exportados desde el sistema viejo de CASA SALCO y los persiste en Postgres
via SQLAlchemy. Cubre tres entidades en orden por FK:

1. `Proveedor` (sheet `proveedor` del File 1).
2. `Articulo` (sheet `Sheet1` del File 2).
3. `ArticuloProveedor` (sheet `RELACION PRODUCTOS PROVEEDOR` del File 1).

NO modifica modelos. NO crea migraciones. Re-correr es seguro: las claves naturales
(`Proveedor.codigo`, `Articulo.codigo`, `(articulo_id, proveedor_id)`) determinan
insert vs update vs skip.

## Prerrequisitos

- Python 3.12+
- PostgreSQL corriendo (típicamente `docker compose up -d` desde la raíz del repo).
- Backend instalado con el grupo opcional `[import-xls]`:

  ```bash
  cd backend
  pip install -e ".[import-xls]"
  ```

  El grupo agrega `xlrd==1.2.0` (read-side BIFF) y `xlwt>=1.3.0` (write-side, solo
  necesario para regenerar los fixtures sintéticos de tests).

- **CRÍTICO**: las entradas `sin-familia` (Familia) y `sin-rubro` (Rubro) deben
  existir en la DB antes de correr el importer. El importer NO las auto-crea —
  falla con `RuntimeError` si faltan. Cómo asegurarlas:

  - **DB con `articulos > 50`** (ya poblada): `flask seed big` tiene un guard que
    early-returns y NO corre `_seed_taxonomia`. Workaround idiomático — invocar
    `_seed_taxonomia` directo desde el venv:

    ```bash
    cd backend
    .venv/Scripts/python -c "from app.seeds.big import _seed_taxonomia; from app import create_app; app=create_app(); ctx=app.app_context(); ctx.push(); _seed_taxonomia(echo=print); from app.extensions import db; db.session.commit()"
    ```

    Esto reusa el seed idempotente sin pasar por el guard. Ver
    `casa-salco/seed-big-articulos-guard` para el contexto del workaround.

  - **DB con `articulos < 50`** (DB fresca o casi vacía): `flask seed big`
    corre el seed completo, incluyendo taxonomía. No hace falta workaround.

## CLI

```
python -m etl.xls.import_xls [OPTIONS]

Options:
  --proveedores PATH                              Ruta al .xls File 1 (sheet 'proveedor').       [required]
  --articulos PATH                                Ruta al .xls File 2 (sheet 'Sheet1').          [required]
  --articulos-proveedores PATH                    Ruta al .xls File 1 (sheet 'RELACION ...').    [required]
  --skip-compra-cero / --no-skip-compra-cero      Si ON, articulos con COMPRA=0 son saltados.    [default: OFF]
  --dry-run / --no-dry-run                        No escribe a la DB; rollback final.            [default: OFF]
  --batch-size INTEGER                            Filas por flush() de la session.               [default: 1000]
  --report-out PATH                               Directorio para los reports timestamped.       [default: etl/xls/reports]
  --db-url TEXT                                   Wired pero no consumido — ver Limitaciones.
  -v, --verbose                                   Log DEBUG en stdout.
  -h, --help                                      Muestra ayuda.
```

Exit codes:

- `0` — success (todas las fases comitearon, `failed=0` en cada `LoadReport`).
- `1` — partial (alguna fase tuvo `failed > 0`; típicamente FK no resueltos en `ArticuloProveedor`).
- `2` — failure (excepción no recuperable, rollback global de la fase abortada).

## Ejemplos

Dry-run contra los `.xls` reales (sin escribir a la DB):

```bash
cd "PROYECTO ERP"
python -m etl.xls.import_xls \
  --proveedores ../3EB052EF592E1D591FBB8C-h00ugz.xls \
  --articulos ../3EB07DF9C6673E43F507BE-615s0b.xls \
  --articulos-proveedores ../3EB052EF592E1D591FBB8C-h00ugz.xls \
  --dry-run
```

Primera corrida real, con backup previo:

```bash
# 1. Snapshot de la DB ANTES de tocar nada.
pg_dump -Fc casa_salco > pre-xls-import-$(date +%Y%m%d).dump

# 2. Correr el importer (sin --dry-run).
cd "PROYECTO ERP"
python -m etl.xls.import_xls \
  --proveedores ../3EB052EF592E1D591FBB8C-h00ugz.xls \
  --articulos ../3EB07DF9C6673E43F507BE-615s0b.xls \
  --articulos-proveedores ../3EB052EF592E1D591FBB8C-h00ugz.xls

# 3. Inspeccionar el report markdown.
cat etl/xls/last-report.md
```

Con `--skip-compra-cero` (cuando el cliente decide descartar artículos legacy
sin precio de compra):

```bash
python -m etl.xls.import_xls \
  --proveedores ../3EB052EF592E1D591FBB8C-h00ugz.xls \
  --articulos ../3EB07DF9C6673E43F507BE-615s0b.xls \
  --articulos-proveedores ../3EB052EF592E1D591FBB8C-h00ugz.xls \
  --skip-compra-cero
```

Atajos por Makefile (ver target en `PROYECTO ERP/Makefile`):

```bash
make etl-import-xls-dry   # dry-run con paths default
make etl-import-xls       # corrida real con paths default
```

## Idempotencia

Re-correr es seguro. La política de upsert por entidad:

| Entidad             | Clave natural                       | Insert | Update | Skip                  |
|---------------------|-------------------------------------|--------|--------|-----------------------|
| `Proveedor`         | `codigo` (String(30) unique)        | nueva  | cambia | sin deltas            |
| `Articulo`          | `codigo` (String(30) unique)        | nueva  | cambia | sin deltas            |
| `ArticuloProveedor` | `(articulo_id, proveedor_id)` UQ    | nueva  | cambia | sin deltas            |

Cada UPDATE solo machaca campos seteados desde el `.xls` (`descripcion`, `costo`,
`pvp_base`, `unidad_medida`, `proveedor_principal_id`, `familia_id`, `rubro_id`).
NO toca `marca_id`, `descripcion_corta`, `iva_porc` — preserva valores que
pudieran haber sido seteados por el importer DBF u otra fuente. Tampoco toca
`articulo_codigos` (los códigos de barra viven en una tabla 1:N — ver sección
"Cambio de schema" más abajo).

## Reports

Cada corrida genera dos archivos markdown:

- `etl/xls/reports/xls-import-{YYYYMMDDTHHMMSSZ}.md` — timestamped, persistente.
- `etl/xls/last-report.md` — copia del último report (sobrescribible).

Secciones del report (en orden):

1. Header: timestamp ISO, paths fuente, duración en segundos, exit status.
2. `## Counts` — tabla `inserted | updated | skipped | failed` por entidad.
3. `## Articulos con compra=0` — primeros 20 + `... and N more` si excede.
4. `## FK no resueltos` — articulos con `proveedor_codigo` inexistente; AP con
   articulo o proveedor faltante.
5. `## Rubro/Familia/Marca no mapeados` — primeros 20 + `... and N more` con los
   raw values legacy que cayeron en fallback.
6. `## Raw catalog values preserved` — `codigo → {rubro, grupo, marca}` raw
   tuples, primeros 200 + `... and N more`. Datos para promover catálogos en un
   change futuro (ver Limitaciones).
7. `Distinct rubros / grupos / marcas / grupdesc / categorias seen` — counts
   agregados.
8. `## Junk filtered` — filas con `codigo IN ('0000','')`, `codigo == descripcion`,
   o `descripcion ~ /^(test|prueba|xxx|asdla|yyy)/i`.
9. `## Sheets skipped` — incluye literalmente la línea
   `EMPAQUETADOS DE PRODUCTOS — pending multi-codigo model (next change)`.
10. `## Errors` — excepciones no fatales por fila, con número de fila + sheet.

Secciones vacías renderizan `(none)`. Listas largas usan el patrón
`primer 20 + ... and N more` para que el report sea legible incluso con 78k filas.

## Rollback

El importer es aditivo (no borra) e idempotente, así que el rollback más simple
es restaurar el snapshot tomado ANTES de la primera corrida real:

```bash
pg_restore -d casa_salco -c pre-xls-import-YYYYMMDD.dump
```

Como secundario (rollback quirúrgico, no recomendado para data masiva), se podría
hacer `DELETE WHERE created_at >= <timestamp>` directo en SQL, pero `pg_restore`
es más seguro y documentado.

## Cambio de schema: `codigo_barras` → `ArticuloCodigo` (revision `e5f6a7b8c9d0`)

A partir del change `articulo-multi-codigo-migration` (mayo 2026), el campo
legacy `Articulo.codigo_barras` (String(50) singular) fue eliminado. Los códigos
de barra ahora viven en la tabla 1:N `articulo_codigos` con un campo `tipo`:

| `tipo`        | Significado                                                        |
|---------------|--------------------------------------------------------------------|
| `principal`   | El código principal del articulo (lo que antes era `codigo_barras`). |
| `alterno`     | Códigos alternativos (poblados por changes futuros).               |
| `empaquetado` | Códigos de empaquetado (caja x N, fardo, etc.).                    |
| `interno`     | Códigos internos (no escaneables, uso administrativo).             |

Constraint: `UNIQUE (articulo_id, codigo)` por par — un mismo código puede
existir en distintos articulos (no UNIQUE global).

### Implicancias para este importer

- **El xls importer NO toca `articulo_codigos`.** Los códigos vienen de la
  sheet `EMPAQUETADOS DE PRODUCTOS` (File 1, 22683 filas), que sigue siendo
  scope del próximo change `xls-empaquetados-y-presentaciones`.
- En la tabla "Column → Field Mapping" del spec, la columna `(derived) →
  Articulo.codigo_barras` (NULL) ya no aplica: el target legacy fue eliminado.
  El próximo change escribirá directamente en `articulo_codigos` con el `tipo`
  correspondiente.
- El importer DBF (`etl/mappers/articulos.py`) sí escribe el código principal,
  vía un par dict `_principal_codigo` que el `load()` pop-ea y persiste como
  `ArticuloCodigo(tipo='principal')` en un segundo paso (post-flush del
  Articulo padre).

### API y POS

- Endpoint para lookup exact-match desde el POS:
  `GET /api/v1/articulos/by-codigo/<codigo>` — retorna 200 + `ArticuloOut` o
  404 si no existe. Roles habilitados: mismos que `GET /articulos`.
- Payload de creación (`POST /articulos`): el campo se llama `codigo_principal`
  (singular, opcional) en el body; el server crea el child row con
  `tipo='principal'`.
- Lectura: `Articulo.codigos[]` viene populado vía relationship `selectin`,
  sin N+1.
- UI label: se mantiene literal "Código de barras" en el form de alta — Omar's
  convención de UX para preservar terminología legacy del usuario.

## Limitaciones conocidas

- **Sheet `EMPAQUETADOS DE PRODUCTOS`** (22683 filas en File 1) NO se importa.
  Diferida al próximo change `xls-empaquetados-y-presentaciones`, que escribirá
  los códigos en `articulo_codigos` con `tipo='empaquetado'` (ver "Cambio de
  schema" más arriba). El report lo lista en `## Sheets skipped`.
- **Catálogo de rubros / familias / marcas**: los ~612 rubros, ~2052 marcas, etc.
  presentes en el `.xls` NO se promueven a las tablas reales en este import.
  Quedan como raw values en el report (`## Raw catalog values preserved`) para
  promoción futura. Todos los artículos importados arrancan con
  `rubro_id = sin-rubro.id`, `familia_id = sin-familia.id`, `marca_id = NULL`.
- **Columna `cantidad`** de `RELACION PRODUCTOS PROVEEDOR`: se descarta. El
  modelo `ArticuloProveedor` no tiene campo de presentación; diferido al change
  `xls-empaquetados-y-presentaciones`.
- **Flag `--db-url`** está cableado pero NO consumido. El importer construye el
  contexto con `app.create_app()`, que lee `DATABASE_URL` del environment.
  Pasar `--db-url` solo loguea un WARNING.
- **Encoding cp1252 / mojibake**: el helper `decode_xls_str` aplica
  `s.encode('latin-1','replace').decode('cp1252','replace')` antes de
  `sanitize_text`. Es idempotente: strings ya en utf-8 limpio sobreviven
  intactas. Si aparecen caracteres raros en la DB después del import, abrir
  bug — probablemente algún path de `extract` salteó el helper.

## Tests

```bash
cd "PROYECTO ERP"
python -m pytest etl/tests/test_xls_mappers.py -v
```

35 tests: 8 casos parametrize de `decode_xls_str`, idempotencia, junk filtering,
mapeo de unidades, raw values, y 7 clases de integración con fixtures sintéticos.

Los fixtures viven en `etl/tests/fixtures/xls_synthetic/` y se commitean (≤ 5KB
c/u). Para regenerarlos:

```bash
cd "PROYECTO ERP"
python etl/tests/fixtures/xls_synthetic/build.py
```

Esto requiere `xlwt` instalado (incluido en `[import-xls]`).
