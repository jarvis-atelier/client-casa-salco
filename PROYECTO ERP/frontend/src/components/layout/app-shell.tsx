import * as React from "react";
import { useLocation } from "@tanstack/react-router";
import { SidebarNav } from "./sidebar-nav";
import { UserMenu } from "./user-menu";
import { Topbar } from "./topbar";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

interface AppShellProps {
  children: React.ReactNode;
}

const TITLES: Record<string, string> = {
  "/": "Dashboard",
  "/pos": "Punto de venta",
  "/facturas": "Facturas",
  "/movimientos": "Movimientos de caja",
  "/pagos": "Calendario de pagos",
  "/articulos": "Artículos",
  "/clientes": "Clientes",
  "/proveedores": "Proveedores",
  "/compras": "Compras",
  "/compras/ocr": "Compras · OCR",
  "/stock/reposicion": "Stock · Reposición",
  "/stock": "Stock",
  "/sucursales": "Sucursales",
  "/exports": "Exportar",
  "/consultas": "Consultas",
  "/mantenimiento": "Mantenimiento",
};

function getTitle(pathname: string): string {
  if (TITLES[pathname]) return TITLES[pathname];
  const prefix = Object.keys(TITLES).find(
    (p) => p !== "/" && pathname.startsWith(p),
  );
  return prefix ? TITLES[prefix] : "CASA SALCO";
}

function SidebarBrand() {
  return (
    <div className="flex items-center gap-2 px-5 py-5">
      <span className="text-[18px] font-semibold tracking-tight leading-none">
        CASA SALCO
      </span>
      <span className="h-1.5 w-1.5 rounded-full bg-primary" />
    </div>
  );
}

export function AppShell({ children }: AppShellProps) {
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const title = getTitle(location.pathname);

  React.useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  return (
    <div className="min-h-screen bg-background">
      {/* Sidebar desktop */}
      <aside className="hidden md:flex fixed inset-y-0 left-0 w-[240px] flex-col border-r border-border bg-card/40">
        <SidebarBrand />
        <Separator />
        <div className="flex-1 overflow-y-auto py-2">
          <SidebarNav />
        </div>
        <Separator />
        <div className="p-3">
          <UserMenu />
        </div>
      </aside>

      {/* Sheet mobile */}
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent side="left" className="w-[260px] p-0">
          <SheetHeader className="px-5 py-5">
            <SheetTitle className="flex items-center gap-2">
              <span className="text-[18px] font-semibold tracking-tight">
                CASA SALCO
              </span>
              <span className="h-1.5 w-1.5 rounded-full bg-primary" />
            </SheetTitle>
          </SheetHeader>
          <Separator />
          <div className="py-2">
            <SidebarNav onNavigate={() => setMobileOpen(false)} />
          </div>
          <Separator />
          <div className="p-3">
            <UserMenu />
          </div>
        </SheetContent>
      </Sheet>

      <div className="md:pl-[240px] flex min-h-screen flex-col">
        <Topbar title={title} onOpenMobileNav={() => setMobileOpen(true)} />
        <main className="flex-1 px-6 py-8 md:px-12 md:py-10">{children}</main>
      </div>
    </div>
  );
}
