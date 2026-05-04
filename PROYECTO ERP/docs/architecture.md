# Arquitectura — Castulo Nuevo

## Topología (objetivo Fase 2)

```
                 ┌─────────────────────┐
                 │   Servidor central  │
                 │  (Railway / Fly)    │
                 │  Flask + Postgres   │
                 │      + Redis        │
                 └──────────┬──────────┘
                            │ HTTPS + WebSocket
     ┌──────────────────────┼──────────────────────┐
     │                      │                      │
     ▼                      ▼                      ▼
┌─────────┐            ┌─────────┐            ┌─────────┐
│ Sucur.1 │            │ Sucur.2 │            │ Sucur.N │
│ Cajas:  │            │ Cajas:  │            │ Cajas:  │
│  Tauri  │            │  Tauri  │            │  Tauri  │
│ +SQLite │            │ +SQLite │            │ +SQLite │
│ local   │            │ local   │            │ local   │
└─────────┘            └─────────┘            └─────────┘
   + 3NSTAR              + 3NSTAR              + 3NSTAR
   + Kretz/Systel        + Kretz/Systel        + Kretz/Systel

             ┌─────────────────────────────┐
             │ Dashboard web + Mobile PWA  │
             │ (mismo bundle React)        │
             └─────────────────────────────┘
```

## Decisiones arquitectónicas (ADR resumido)

1. **Backend monolito modular (Flask blueprints)** — no microservicios. Un solo
   desarrollador no puede mantener N servicios. Si mañana el dominio crece,
   extraer un blueprint a un servicio es ~1 semana.
2. **Postgres central** como única fuente de verdad. Cada caja sincroniza su
   SQLite local contra este Postgres.
3. **Local-first para cajas** — si internet se cae, la venta sigue. La cola
   local de operaciones se drena cuando vuelve internet. AFIP es la única
   operación que bloquea si no hay internet (no podemos pedir CAE offline sin
   CAEA, y CAEA lo dejamos fuera del MVP).
4. **WebSocket (Flask-SocketIO) para sync en vivo** — cambios de precios se
   propagan a todas las sucursales en < 1s.
5. **Redis** como pub/sub entre procesos del backend y cache.
6. **Celery** para jobs asincrónicos: ETL, datamining, OCR, export Excel.
7. **Una sola UI React** — misma codebase se sirve por Flask (web), corre en
   Tauri (caja local) y se installa como PWA (mobile).
8. **Apple aesthetic** implementada como tokens de Tailwind + CSS vars — sin
   librería de componentes adicional más allá de shadcn/ui.
9. **Auth JWT con refresh tokens** + tabla `users` con roles jerárquicos.
10. **AFIP vía PyAfipWs** — biblioteca argentina madura, mejor soportada que
    cualquier wrapper Node/TypeScript.

## Módulos backend (Fase 1)

```
app/
  api/v1/
    auth.py              → login, refresh, me
    sucursales.py        → CRUD sucursales + áreas dinámicas
    articulos.py         → CRUD artículos + categorización
    precios.py           → cambio de precios + sync multisucursal
    clientes.py          → CRUD clientes
    proveedores.py       → CRUD proveedores + marcas
  models/
    user.py
    sucursal.py
    area.py
    articulo.py
    precio.py
    familia.py rubro.py subrubro.py
    cliente.py
    proveedor.py
    marca.py
  services/
    price_sync.py        → broadcast Flask-SocketIO
    auth_service.py
  sockets/
    price_channel.py     → namespace /prices para sync en vivo
```

## Preservación de UX del viejo

Nombres visibles para los usuarios (inspirados en el menú viejo):
- "Caja" → módulo caja
- "Mantenimiento" → artículos/stock
- "Cobranzas" → cta cte + cheques
- "Ventas" → POS
- "Listados" → reportes

Internamente son módulos nuevos con arquitectura limpia.
