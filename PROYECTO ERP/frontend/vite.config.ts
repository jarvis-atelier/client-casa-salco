import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: [
        "favicon.svg",
        "apple-touch-icon.png",
        "icons/icon-192.png",
        "icons/icon-512.png",
      ],
      devOptions: {
        // En `npm run dev` también queremos el SW disponible para testing.
        enabled: true,
        type: "module",
      },
      manifest: {
        name: "Jarvis Core ERP",
        short_name: "Jarvis Core",
        description: "Sistema de gestión integral multi-sucursal",
        theme_color: "#fafafa",
        background_color: "#fafafa",
        display: "standalone",
        orientation: "any",
        lang: "es-AR",
        scope: "/",
        start_url: "/",
        icons: [
          {
            src: "/icons/icon-192.png",
            sizes: "192x192",
            type: "image/png",
            purpose: "any",
          },
          {
            src: "/icons/icon-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "any",
          },
          {
            src: "/icons/icon-192-maskable.png",
            sizes: "192x192",
            type: "image/png",
            purpose: "maskable",
          },
          {
            src: "/icons/icon-512-maskable.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        navigateFallback: "/index.html",
        // Endpoints autenticados y socket.io NO deben ser interceptados.
        navigateFallbackDenylist: [/^\/api\//, /^\/socket\.io\//],
        runtimeCaching: [
          {
            // Catálogos casi-estáticos: stale-while-revalidate.
            urlPattern: ({ url }) =>
              /\/api\/v1\/(sucursales|familias|rubros|subrubros|marcas|proveedores|areas)/.test(
                url.pathname,
              ),
            handler: "StaleWhileRevalidate",
            options: {
              cacheName: "api-catalogos",
              expiration: { maxEntries: 64, maxAgeSeconds: 24 * 60 * 60 },
            },
          },
          {
            // Listado de artículos: NetworkFirst con TTL corto.
            urlPattern: ({ url }) => url.pathname.startsWith("/api/v1/articulos"),
            handler: "NetworkFirst",
            options: {
              cacheName: "api-articulos",
              networkTimeoutSeconds: 4,
              expiration: { maxEntries: 64, maxAgeSeconds: 5 * 60 },
            },
          },
          {
            // Iconos / fuentes / assets estáticos.
            urlPattern: ({ request }) =>
              request.destination === "image" ||
              request.destination === "font" ||
              request.destination === "style" ||
              request.destination === "script",
            handler: "StaleWhileRevalidate",
            options: { cacheName: "static-assets" },
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:5000",
        changeOrigin: true,
      },
      "/socket.io": {
        target: "http://localhost:5000",
        ws: true,
        changeOrigin: true,
      },
    },
  },
});
