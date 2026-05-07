import { createRouter } from "@tanstack/react-router";
import { rootRoute } from "./root";
import { loginRoute } from "./login";
import { appLayoutRoute } from "./app-layout";
import { dashboardRoute } from "./dashboard";
import { articulosRoute } from "./articulos";
import { clientesRoute } from "./clientes";
import { proveedoresRoute } from "./proveedores";
import { stockRoute } from "./stock";
import { stockReposicionRoute } from "./stock-reposicion";
import { posRoute } from "./pos";
import { sucursalesRoute } from "./sucursales";
import { mantenimientoRoute } from "./mantenimiento";
import { facturasRoute } from "./facturas";
import { movimientosRoute } from "./movimientos";
import { exportsRoute } from "./exports";
import { consultasRoute } from "./consultas";
import { pagosRoute } from "./pagos";
import { comprasRoute } from "./compras";
import { comprasOcrRoute } from "./compras/ocr";
import { notFoundRoute } from "./not-found";

const routeTree = rootRoute.addChildren([
  loginRoute,
  appLayoutRoute.addChildren([
    dashboardRoute,
    posRoute,
    facturasRoute,
    movimientosRoute,
    articulosRoute,
    clientesRoute,
    proveedoresRoute,
    stockRoute,
    stockReposicionRoute,
    sucursalesRoute,
    mantenimientoRoute,
    exportsRoute,
    consultasRoute,
    pagosRoute,
    comprasRoute.addChildren([comprasOcrRoute]),
  ]),
  notFoundRoute,
]);

// `import.meta.env.BASE_URL` viene del `base` de vite.config.ts. En dev = "/",
// en build con prefix = "/casasalco/". TanStack Router quiere basepath SIN
// trailing slash.
const basepath = (import.meta.env.BASE_URL || "/").replace(/\/$/, "");

export const router = createRouter({
  routeTree,
  defaultPreload: "intent",
  basepath: basepath || undefined,
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
