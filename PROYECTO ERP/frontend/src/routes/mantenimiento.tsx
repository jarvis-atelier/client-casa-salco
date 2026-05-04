import { createRoute } from "@tanstack/react-router";
import { Settings } from "lucide-react";
import { Card } from "@/components/ui/card";
import { appLayoutRoute } from "./app-layout";

export const mantenimientoRoute = createRoute({
  getParentRoute: () => appLayoutRoute,
  path: "/mantenimiento",
  component: MantenimientoPage,
});

function MantenimientoPage() {
  return (
    <div className="flex flex-col gap-8 max-w-[1280px]">
      <div>
        <h2 className="text-[28px] font-semibold tracking-tight leading-tight">
          Mantenimiento
        </h2>
        <p className="mt-1.5 text-[14px] text-muted-foreground">
          Catálogos maestros y configuración del sistema.
        </p>
      </div>

      <Card className="p-12 flex flex-col items-center text-center gap-4">
        <div className="rounded-full bg-muted/60 p-4">
          <Settings
            className="h-7 w-7 text-muted-foreground"
            strokeWidth={1.5}
          />
        </div>
        <div className="flex flex-col gap-1.5 max-w-md">
          <h3 className="text-[18px] font-semibold tracking-tight">
            Módulo Mantenimiento — próximamente
          </h3>
          <p className="text-[13px] text-muted-foreground leading-relaxed">
            En Fase 2 vas a poder gestionar familias, rubros, marcas, proveedores
            y clientes desde este módulo. Por ahora los datos llegan vía ETL y
            seeds.
          </p>
        </div>
      </Card>
    </div>
  );
}
