# Jarvis Core — Desktop build (Tauri 2.x)

Esta guía explica cómo correr el frontend como **app nativa Windows** vía
[Tauri 2.x](https://tauri.app). La versión web sigue funcionando 100% en el
navegador con `npm run dev` — el shell desktop es un envoltorio adicional
pensado para **cajas dedicadas** (clientes que prefieren un binario instalado
con icono en el escritorio en vez de un browser).

---

## 1. Requisitos previos (una sola vez por máquina)

### Rust toolchain

Tauri compila con Rust. Instalar `rustup` con uno de los dos métodos:

```powershell
winget install Rustlang.Rustup
```

o desde [https://rustup.rs/](https://rustup.rs/) y seguir el wizard.

Después, abrir una terminal NUEVA y verificar:

```bash
rustc --version
cargo --version
```

### WebView2 runtime

Windows 11 ya lo trae. En Windows 10 puede faltar — Tauri lo descarga en el
primer build. Si querés instalarlo manualmente:
[https://developer.microsoft.com/en-us/microsoft-edge/webview2/](https://developer.microsoft.com/en-us/microsoft-edge/webview2/).

### Build tools (Windows)

Si nunca compilaste C++ en esta PC:

```powershell
winget install Microsoft.VisualStudio.2022.BuildTools
```

Y agregá los workloads "Desktop development with C++".

### CLI de Tauri

Ya está como devDependency (`@tauri-apps/cli`). `npm install` lo instala.

---

## 2. Comandos

Todos desde `frontend/`:

```bash
# Instalar deps (incluye @tauri-apps/cli y idb-keyval)
npm install

# DEV — abre la ventana nativa con hot reload (Vite :5173 + WebView2)
npm run tauri:dev

# BUILD — compila el binario release y genera el instalador
npm run tauri:build
```

### Output del build

```
frontend/src-tauri/target/release/
├── jarvis-core.exe                              # binario standalone
└── bundle/
    ├── msi/Jarvis Core_0.1.0_x64_es-AR.msi      # instalador MSI (Wix)
    └── nsis/Jarvis Core_0.1.0_x64-setup.exe     # instalador NSIS
```

---

## 3. Iconos

Los iconos en `frontend/src-tauri/icons/` son **placeholders** copiados del PNG
192×192 del PWA. Para generar el set completo (incluido `icon.ico` que Windows
necesita para el instalador), correr **una vez** desde `frontend/`:

```bash
npx @tauri-apps/cli icon ./public/icons/icon-512.png
```

Eso reemplaza los archivos en `src-tauri/icons/` con tamaños correctos.

---

## 4. Distribución a las cajas

1. Compilar localmente: `npm run tauri:build`.
2. Copiar el `.msi` (o `.exe` NSIS) a un share interno o pendrive.
3. En cada caja: doble click → wizard de instalación → app queda en el menú
   inicio como "Jarvis Core".
4. La app apunta por defecto a `http://localhost:5000` (backend) y
   `http://localhost:9123` (agente de impresión). Si la caja consume un
   backend remoto, hay que ajustar el `.env` del frontend ANTES de buildear o
   exponer la URL como variable de entorno.

---

## 5. Cola offline

Cuando se cae internet:

- **Operaciones no fiscales** (clientes, proveedores, stock interno, notas,
  cuentas corrientes, etc.) se **encolan automáticamente** en IndexedDB y se
  reintentan al volver la conexión. Sobrevive a refresh y reinicio.
- **Facturas A/B/C** (AFIP) **NO se encolan** — el cajero ve el error y debe
  emitir un ticket interno (no fiscal) hasta que vuelva internet, y después
  emitir la factura electrónica con CAE de manera explícita.

El estado de la cola se ve con el componente `<OfflineIndicator>` en
`src/components/layout/offline-indicator.tsx` (pendiente de montar en el
topbar — ver Fase 2.4).

Endpoints excluidos de la cola: `auth/*`, `facturas/`, `emitir-cae`, `afip/*`.

---

## 6. Auto-updater (TODO Fase 3)

Tauri 2.x soporta [auto-updates firmados](https://tauri.app/v1/guides/distribution/updater/).
Pendiente de configurar:

1. Generar par de claves: `npx @tauri-apps/cli signer generate -w ~/.tauri/jarvis.key`
2. Agregar `plugins.updater` al `tauri.conf.json` con la public key y endpoint.
3. Subir releases firmados a un bucket / GitHub releases con un `latest.json`.
4. Llamar `checkUpdate()` desde el frontend al boot.

Por ahora se distribuye manualmente reemplazando el `.msi`.

---

## 7. Troubleshooting

| Síntoma | Causa probable | Solución |
|---|---|---|
| `cargo not found` | Rust no instalado / shell vieja | Instalar `rustup`, abrir NUEVA terminal |
| `MSVC link.exe missing` | No hay Build Tools VS | Instalar VS 2022 Build Tools con workload C++ |
| Build pide `icon.ico` | Iconos placeholder sin .ico | Correr `npx @tauri-apps/cli icon ./public/icons/icon-512.png` |
| Ventana en blanco | Vite no levantó en :5173 | Ver `beforeDevCommand` y logs de la terminal |
| WebView2 missing | Windows 10 viejo | Instalar runtime de WebView2 manualmente |

---

## 8. Comparativa Web vs Desktop

| Feature | Web (PWA) | Desktop (Tauri) |
|---|---|---|
| Instalación | Browser → "Instalar app" (opcional) | `.msi` con icono propio |
| Hotkeys globales | Limitadas a la pestaña | Posibles (futuro) |
| Acceso a hardware | WebSerial / WebUSB con permisos | Vía agente local `:9123` (igual) |
| Auto-updates | SW del navegador | Updater Tauri firmado (TODO) |
| Cola offline | Sí (IndexedDB) | Sí (IndexedDB compartida) |
| Tamaño instalador | 0 MB | ~10–15 MB |

La lógica de negocio es idéntica — `isTauri()` en `src/lib/platform.ts`
permite condicionar comportamiento puntual si fuera necesario.
