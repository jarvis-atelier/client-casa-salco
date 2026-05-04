import { Outlet, createRoute, redirect } from "@tanstack/react-router";
import { useAuth } from "@/store/auth";
import { AppShell } from "@/components/layout/app-shell";
import { usePriceSyncListener } from "@/hooks/use-price-sync";
import { rootRoute } from "./root";

export const appLayoutRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: "app-layout",
  beforeLoad: () => {
    const { accessToken } = useAuth.getState();
    if (!accessToken) {
      throw redirect({ to: "/login" });
    }
  },
  component: AppLayoutComponent,
});

function AppLayoutComponent() {
  // Conecta el socket /prices y escucha `price:updated` para todo lo autenticado.
  usePriceSyncListener();

  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}
