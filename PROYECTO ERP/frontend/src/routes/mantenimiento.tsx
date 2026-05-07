import * as React from "react";
import { createRoute } from "@tanstack/react-router";
import { requireAccess } from "@/lib/permissions";
import { MantenimientoFamilias } from "@/components/mantenimiento/familias";
import { MantenimientoRubros } from "@/components/mantenimiento/rubros";
import { MantenimientoSubrubros } from "@/components/mantenimiento/subrubros";
import { MantenimientoMarcas } from "@/components/mantenimiento/marcas";
import {
  SegmentedTabs,
  type SegmentedTabItem,
} from "@/components/mantenimiento/segmented-tabs";
import { appLayoutRoute } from "./app-layout";

type MantenimientoTab = "familias" | "rubros" | "subrubros" | "marcas";

const TABS: SegmentedTabItem<MantenimientoTab>[] = [
  { value: "familias", label: "Familias" },
  { value: "rubros", label: "Rubros" },
  { value: "subrubros", label: "Subrubros" },
  { value: "marcas", label: "Marcas" },
];

const STORAGE_KEY = "mantenimiento.activeTab";

export const mantenimientoRoute = createRoute({
  getParentRoute: () => appLayoutRoute,
  path: "/mantenimiento",
  beforeLoad: requireAccess("/mantenimiento"),
  component: MantenimientoPage,
});

function MantenimientoPage() {
  const [tab, setTab] = React.useState<MantenimientoTab>(() => {
    if (typeof window === "undefined") return "familias";
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (
      saved === "familias" ||
      saved === "rubros" ||
      saved === "subrubros" ||
      saved === "marcas"
    ) {
      return saved;
    }
    return "familias";
  });

  React.useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, tab);
  }, [tab]);

  return (
    <div className="flex flex-col gap-8 max-w-[1280px]">
      <div>
        <h2 className="text-[28px] font-semibold tracking-tight leading-tight">
          Mantenimiento
        </h2>
        <p className="mt-1.5 text-[14px] text-muted-foreground">
          Catálogos maestros — familias, rubros, subrubros y marcas.
        </p>
      </div>

      <SegmentedTabs<MantenimientoTab>
        value={tab}
        onChange={setTab}
        items={TABS}
      />

      <div>
        {tab === "familias" && <MantenimientoFamilias />}
        {tab === "rubros" && <MantenimientoRubros />}
        {tab === "subrubros" && <MantenimientoSubrubros />}
        {tab === "marcas" && <MantenimientoMarcas />}
      </div>
    </div>
  );
}
