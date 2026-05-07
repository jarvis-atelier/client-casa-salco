import { createRoute, Outlet, redirect } from "@tanstack/react-router";
import { hasAccess } from "@/lib/permissions";
import { useAuth } from "@/store/auth";
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
    const { accessToken, user } = useAuth.getState();
    if (!accessToken) {
      throw redirect({ to: "/login" });
    }
    if (!hasAccess(user?.rol, "/compras")) {
      throw redirect({ to: "/" });
    }
    if (location.pathname === "/compras") {
      throw redirect({ to: "/compras/ocr" });
    }
  },
});

function ComprasLayout() {
  return <Outlet />;
}
