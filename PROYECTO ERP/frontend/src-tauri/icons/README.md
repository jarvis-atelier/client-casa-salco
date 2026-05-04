# Tauri icons

Estos iconos son **placeholders** generados a partir del PNG 192x192 de la PWA
(`frontend/public/icons/icon-192.png`).

Para generar el set completo (incluido `icon.ico` para Windows MSI/NSIS),
ejecutar **una vez** desde `frontend/`:

```bash
npx @tauri-apps/cli icon ./public/icons/icon-512.png
```

Eso regenera los archivos correctos en `src-tauri/icons/` (`32x32.png`,
`128x128.png`, `128x128@2x.png`, `icon.png`, `icon.ico`, `icon.icns`,
y los `Square*Logo.png` para el bundle Windows Store).

> Nota: hasta que se corra ese comando, `tauri build` puede fallar pidiendo
> `icon.ico`. El `tauri dev` debería funcionar igual con los PNG presentes.
