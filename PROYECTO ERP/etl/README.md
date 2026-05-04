# ETL - Importación desde el sistema viejo

Scripts Python que leen los DBFs de `../viejo/DBF/` y pueblan la base del backend nuevo.

## Alcance Fase 1.3

- `ARTICULO.DBF` + `ARTICULO.DBT` -> tabla `articulos`
- `CLIENTES.DBF` -> tabla `clientes`  (con mapeo NUIV -> CondicionIvaEnum)
- `PROVEEDO.DBF` -> tabla `proveedores`
- `RUBRO.DBF` -> tabla `rubros`  (cuelga de familia "General")
- `LINEA.DBF` / `LIN.DBF` -> tabla `familias`  (solo si tiene descripciones reales)
- `ARTIPROV.DBF` -> tabla `articulos_proveedores`

Además se crean dos categorías de fallback siempre:
- Familia `sin-familia` / Rubro `sin-rubro` para artículos huérfanos.
- Familia `general` como padre por defecto de los rubros del legacy.

## Instalación

El grupo opcional `etl` del backend incluye las dependencias:

```bash
cd ../backend
.venv\Scripts\pip install -e ".[etl]"
```

## Uso

```bash
# Dry-run (no escribe, solo extrae y reporta)
..\backend\.venv\Scripts\python import_dbfs.py --source ..\..\viejo\DBF --dry-run

# Corrida real
..\backend\.venv\Scripts\python import_dbfs.py --source ..\..\viejo\DBF

# Seleccionar dominios
..\backend\.venv\Scripts\python import_dbfs.py --source ..\..\viejo\DBF --tables proveedores clientes

# Wipe + re-import (PELIGROSO: pide confirmación interactiva)
..\backend\.venv\Scripts\python import_dbfs.py --source ..\..\viejo\DBF --truncate
```

### Opciones del CLI

| Flag | Descripción |
|---|---|
| `--source` | Carpeta con los `.DBF` (default: `../../viejo/DBF`) |
| `--encoding` | `cp1252` (default), `cp850`, `latin1`, `utf-8` |
| `--tables` | Lista de dominios; default todos. Valores válidos: `proveedores`, `familias`, `rubros`, `clientes`, `articulos`, `articulos_proveedores`, `todos` |
| `--dry-run` | No escribe en la DB; valida y reporta |
| `--truncate` | Borra datos importables antes de correr (pide confirmación) |
| `--verbose` | Log DEBUG en stdout |

## Encoding

Los DBFs están en **CP1252** (Windows Latin). Si se ven caracteres raros, probá `cp850` (DOS viejo).

El ETL normaliza Unicode a NFC después de decodificar y reemplaza null bytes y control chars.

## Idempotencia

Re-correr el ETL **no duplica** registros. La decisión de insert vs update se toma por la columna única:
- Proveedor: `codigo`
- Cliente: `codigo`
- Familia: `codigo`
- Rubro: `(familia_id, codigo)`
- Artículo: `codigo`
- ArticuloProveedor: `(articulo_id, proveedor_id)`

## Outputs

- `last-run.log` - log completo (DEBUG) de la última corrida.
- `last-report.md` - resumen markdown con totales por entidad y warnings.

## Arquitectura

```
etl/
├── import_dbfs.py       # CLI (click) - orquesta las fases
├── mappers/
│   ├── common.py        # helpers: sanitización, mapeos de enums, LoadReport
│   ├── proveedores.py
│   ├── clientes.py
│   ├── familias_rubros.py
│   ├── articulos.py
│   └── articulos_proveedores.py
├── tests/
│   ├── test_common.py
│   └── test_mappers.py
└── last-run.log / last-report.md
```

Cada mapper expone:

```python
def extract(source_dir: Path, encoding: str) -> Iterator[dict]: ...
def load(session, rows: Iterable[dict], *, dry_run: bool = False) -> LoadReport: ...
```

## Tests

```bash
..\backend\.venv\Scripts\python -m pytest tests/ -v
```

43 tests cubren sanitización, mapeo de enums, extracción y idempotencia.

## Campos NO mapeados (intencionalmente)

Del legacy se descartan o no hay modelo equivalente:
- `ARTICULO`: stock multi-depósito (stock, stock2..stock10, nstock*, sstock*, dstock*, estock*), kilogramos (kilos*, kilogramo*), talle×color (ta01..ta20, co01..co20, tc*, sttc*, batc*), adicionales (adi1..adi12), ctipo1..ctipo15 (flags), anticipo, incremento, snapshots antes (anCosto*, anVenta, etc.), flete (string multi-operador), bonifica/utilidad (strings tipo "20+10+5"), maestro/descargar.
- `PROVEEDO`: banco/cuenta/cbu/sucursal/tipo, observa1/observa2, paridad, sald (saldo histórico), mantener, bonifica/utilidad.
- `CLIENTES`: dnigar1/dnigar2/nomgar1..2 (garantes, no se usa en almacén), observa, tiporesu, fechanac/fechaalta/fechabaja (solo se toma altaActual via default).

Si aparecen casos donde se necesita un campo legacy, se puede extender el modelo destino o agregar una columna JSON `legacy_meta`.
