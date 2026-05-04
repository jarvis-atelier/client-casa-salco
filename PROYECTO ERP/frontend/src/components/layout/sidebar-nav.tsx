import { Link, useLocation } from "@tanstack/react-router";
import {
  CalendarClock,
  LayoutGrid,
  Package,
  ShoppingCart,
  Store,
  Settings,
  Receipt,
  Search,
  Users,
  Wallet,
  Truck,
  Boxes,
  FileDown,
  FileImage,
  PackagePlus,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface NavItem {
  to?: string;
  label: string;
  icon: LucideIcon;
  disabled?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Dashboard", icon: LayoutGrid },
  { to: "/pos", label: "Punto de venta", icon: ShoppingCart },
  { to: "/facturas", label: "Facturas", icon: Receipt },
  { to: "/movimientos", label: "Movimientos", icon: Wallet },
  { to: "/pagos", label: "Calendario pagos", icon: CalendarClock },
  { to: "/articulos", label: "Artículos", icon: Package },
  { to: "/clientes", label: "Clientes", icon: Users },
  { to: "/proveedores", label: "Proveedores", icon: Truck },
  { to: "/compras", label: "Compras", icon: FileImage },
  { to: "/stock", label: "Stock", icon: Boxes },
  { to: "/stock/reposicion", label: "Reposición", icon: PackagePlus },
  { to: "/sucursales", label: "Sucursales", icon: Store },
  { to: "/consultas", label: "Consultas", icon: Search },
  { to: "/exports", label: "Exportar", icon: FileDown },
  { to: "/mantenimiento", label: "Mantenimiento", icon: Settings },
];

interface SidebarNavProps {
  onNavigate?: () => void;
}

export function SidebarNav({ onNavigate }: SidebarNavProps) {
  const location = useLocation();
  const current = location.pathname;

  return (
    <nav className="flex flex-col gap-0.5 px-3 py-2">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon;
        // Match exacto cuando hay sub-rutas que comparten prefijo (ej: /stock vs /stock/reposicion)
        const exactOnly = item.to === "/" || item.to === "/stock";
        const active =
          item.to &&
          (exactOnly
            ? current === item.to
            : current.startsWith(item.to));

        if (item.disabled) {
          return (
            <div
              key={item.label}
              title="Próximamente"
              className="flex items-center gap-3 rounded-[8px] px-3 py-2 text-[13px] text-muted-foreground/60 cursor-not-allowed select-none"
            >
              <Icon className="h-[18px] w-[18px]" strokeWidth={1.5} />
              <span>{item.label}</span>
              <span className="ml-auto text-[10px] uppercase tracking-wider text-muted-foreground/50">
                Pronto
              </span>
            </div>
          );
        }

        return (
          <Link
            key={item.label}
            to={item.to!}
            onClick={onNavigate}
            className={cn(
              "flex items-center gap-3 rounded-[8px] px-3 py-2 text-[13px] font-medium transition-colors duration-200 ease-apple",
              active
                ? "bg-muted text-foreground"
                : "text-muted-foreground hover:bg-muted/50 hover:text-foreground",
            )}
          >
            <Icon className="h-[18px] w-[18px]" strokeWidth={1.5} />
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
