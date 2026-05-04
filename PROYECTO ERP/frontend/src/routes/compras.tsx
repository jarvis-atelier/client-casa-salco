import { createRoute, Outlet, redirect } from "@tanstack/react-router";
import { appLayoutRoute } from "./app-layout";

/**
 * Hub de compras. Por ahora redirige a /compras/ocr.
 * Más adelante puede tener tabs (OCR / Manual / Histórico).
 */
export const comprasRoute = createRoute({
  getParentRoute: () => appLayoutRoute,
  path: "/compras",
  component: ComprasLayout,
  beforeLoad: ({ location }) => {
    if (location.pathname === "/compras") {
      throw redirect({ to: "/compras/ocr" });
    }
  },
});

function ComprasLayout() {
  return <Outlet />;
}
