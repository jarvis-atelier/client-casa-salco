import * as React from "react";
import { createRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { listSucursales } from "@/api/sucursales";
import { listClientes } from "@/api/clientes";
import { listProveedoresFull } from "@/api/proveedores";
import {
  downloadCobranzasExport,
  downloadComprasExport,
  downloadCtaCteCliente,
  downloadCtaCteProveedor,
  downloadLibroIvaDigital,
  downloadPagosExport,
  downloadResumenClientes,
  downloadResumenProveedores,
  downloadStockExport,
  downloadStockValorizado,
  downloadVentasDetallado,
  downloadVentasExport,
} from "@/api/exports";
import { ExportCard } from "@/components/exports/export-card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { appLayoutRoute } from "./app-layout";

export const exportsRoute = createRoute({
  getParentRoute: () => appLayoutRoute,
  path: "/exports",
  component: ExportsPage,
});

type TabId = "fiscales" | "comerciales" | "stock" | "cuentas";

const TABS: { id: TabId; label: string }[] = [
  { id: "fiscales", label: "Fiscales" },
  { id: "comerciales", label: "Comerciales" },
  { id: "stock", label: "Stock" },
  { id: "cuentas", label: "Cuentas corrientes" },
];

function fmtDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function defaultLastMonth(): { from: string; to: string } {
  const today = new Date();
  const firstOfThisMonth = new Date(today.getFullYear(), today.getMonth(), 1);
  const lastOfPrevMonth = new Date(firstOfThisMonth);
  lastOfPrevMonth.setDate(lastOfPrevMonth.getDate() - 1);
  const firstOfPrevMonth = new Date(
    lastOfPrevMonth.getFullYear(),
    lastOfPrevMonth.getMonth(),
    1,
  );
  return { from: fmtDate(firstOfPrevMonth), to: fmtDate(lastOfPrevMonth) };
}

function defaultLast30(): { from: string; to: string } {
  const today = new Date();
  const past = new Date(today);
  past.setDate(today.getDate() - 30);
  return { from: fmtDate(past), to: fmtDate(today) };
}

function ExportsPage() {
  const [tab, setTab] = React.useState<TabId>("fiscales");
  const sucursalesQ = useQuery({
    queryKey: ["sucursales"],
    queryFn: listSucursales,
    staleTime: 60_000,
  });

  return (
    <div className="flex flex-col gap-6 max-w-[1200px]">
      <div>
        <h2 className="text-[28px] font-semibold tracking-tight leading-tight">
          Exportar
        </h2>
        <p className="mt-1.5 text-[14px] text-muted-foreground">
          Descargá los reportes en Excel listos para entregar al contador.
        </p>
      </div>

      {/* Segmented control iOS-style */}
      <div
        role="tablist"
        className="inline-flex items-center gap-1 rounded-[10px] border border-border bg-muted/40 p-1 self-start"
      >
        {TABS.map((t) => {
          const active = t.id === tab;
          return (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setTab(t.id)}
              className={cn(
                "px-4 py-1.5 rounded-[8px] text-[13px] font-medium transition-all duration-200 ease-apple",
                active
                  ? "bg-background text-foreground shadow-apple"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      {tab === "fiscales" && (
        <SeccionFiscales />
      )}
      {tab === "comerciales" && (
        <SeccionComerciales sucursales={sucursalesQ.data} />
      )}
      {tab === "stock" && <SeccionStock sucursales={sucursalesQ.data} />}
      {tab === "cuentas" && <SeccionCuentas />}
    </div>
  );
}

// --- Sección Fiscales ---

function SeccionFiscales() {
  const initial = React.useMemo(defaultLastMonth, []);
  const [from, setFrom] = React.useState(initial.from);
  const [to, setTo] = React.useState(initial.to);
  const valid = from && to && from <= to;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <ExportCard
        title="Libro IVA Digital"
        description="Formato RG 4597 — sheets Ventas y Compras. Default: mes anterior completo."
        disabled={!valid}
        onDownload={() => downloadLibroIvaDigital({ fecha_desde: from, fecha_hasta: to })}
      >
        <DateRangeFields
          from={from}
          to={to}
          onFromChange={setFrom}
          onToChange={setTo}
        />
      </ExportCard>
    </div>
  );
}

interface SuccCommonProps {
  sucursales:
    | { id: number; codigo: string; nombre: string; activa: boolean }[]
    | undefined;
}

// --- Sección Comerciales ---

function SeccionComerciales({ sucursales }: SuccCommonProps) {
  const initial = React.useMemo(defaultLast30, []);
  const [from, setFrom] = React.useState(initial.from);
  const [to, setTo] = React.useState(initial.to);
  const [suc, setSuc] = React.useState<number | null>(null);
  const valid = from && to && from <= to;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <ExportCard
        title="Ventas detalladas"
        description="Comprobantes emitidos + sheets agrupados por sucursal, familia, cajero y top productos."
        disabled={!valid}
        onDownload={() =>
          downloadVentasDetallado({ fecha_desde: from, fecha_hasta: to }, suc)
        }
      >
        <DateRangeFields
          from={from}
          to={to}
          onFromChange={setFrom}
          onToChange={setTo}
        />
        <SucursalSelect label="Sucursal" value={suc} onChange={setSuc} sucursales={sucursales} />
      </ExportCard>

      <ExportCard
        title="Ventas (legacy)"
        description="Listado de comprobantes emitidos + resumen diario."
        disabled={!valid}
        onDownload={() =>
          downloadVentasExport({ fecha_desde: from, fecha_hasta: to }, suc)
        }
      >
        <DateRangeFields
          from={from}
          to={to}
          onFromChange={setFrom}
          onToChange={setTo}
        />
        <SucursalSelect label="Sucursal" value={suc} onChange={setSuc} sucursales={sucursales} />
      </ExportCard>

      <ExportCard
        title="Compras"
        description="Compras a proveedores (factura tipo C) + resumen por proveedor."
        disabled={!valid}
        onDownload={() =>
          downloadComprasExport({ fecha_desde: from, fecha_hasta: to }, null, suc)
        }
      >
        <DateRangeFields
          from={from}
          to={to}
          onFromChange={setFrom}
          onToChange={setTo}
        />
        <SucursalSelect label="Sucursal" value={suc} onChange={setSuc} sucursales={sucursales} />
      </ExportCard>

      <ExportCard
        title="Cobranzas"
        description="Pagos recibidos de clientes + breakdown por medio de pago."
        disabled={!valid}
        onDownload={() =>
          downloadCobranzasExport({ fecha_desde: from, fecha_hasta: to }, null, suc)
        }
      >
        <DateRangeFields
          from={from}
          to={to}
          onFromChange={setFrom}
          onToChange={setTo}
        />
        <SucursalSelect label="Sucursal" value={suc} onChange={setSuc} sucursales={sucursales} />
      </ExportCard>

      <ExportCard
        title="Pagos a proveedores"
        description="Pagos efectuados a proveedores + breakdown por proveedor."
        disabled={!valid}
        onDownload={() =>
          downloadPagosExport({ fecha_desde: from, fecha_hasta: to }, null, suc)
        }
      >
        <DateRangeFields
          from={from}
          to={to}
          onFromChange={setFrom}
          onToChange={setTo}
        />
        <SucursalSelect label="Sucursal" value={suc} onChange={setSuc} sucursales={sucursales} />
      </ExportCard>
    </div>
  );
}

// --- Sección Stock ---

function SeccionStock({ sucursales }: SuccCommonProps) {
  const [suc, setSuc] = React.useState<number | null>(null);
  const [sucVal, setSucVal] = React.useState<number | null>(null);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <ExportCard
        title="Stock actual"
        description="Snapshot por artículo y sucursal (cantidad, costo, valor)."
        onDownload={() => downloadStockExport(suc)}
      >
        <SucursalSelect
          label="Sucursal"
          value={suc}
          onChange={setSuc}
          sucursales={sucursales}
        />
      </ExportCard>

      <ExportCard
        title="Stock valorizado"
        description="Stock con familia, rubro, marca, valor total y % del valor de inventario."
        onDownload={() => downloadStockValorizado(sucVal)}
      >
        <SucursalSelect
          label="Sucursal"
          value={sucVal}
          onChange={setSucVal}
          sucursales={sucursales}
        />
      </ExportCard>
    </div>
  );
}

// --- Sección Cuentas Corrientes ---

function SeccionCuentas() {
  const clientesQ = useQuery({
    queryKey: ["clientes-export"],
    queryFn: () => listClientes({ per_page: 200 }),
    staleTime: 30_000,
  });
  const proveedoresQ = useQuery({
    queryKey: ["proveedores-export"],
    queryFn: () => listProveedoresFull(),
    staleTime: 30_000,
  });

  const [clienteSel, setClienteSel] = React.useState<number | null>(null);
  const [proveedorSel, setProveedorSel] = React.useState<number | null>(null);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <ExportCard
        title="Resumen de clientes"
        description="Listado completo de clientes con saldo y última operación."
        onDownload={() => downloadResumenClientes()}
      />

      <ExportCard
        title="Resumen de proveedores"
        description="Proveedores con compras totales y última compra."
        onDownload={() => downloadResumenProveedores()}
      />

      <ExportCard
        title="Histórico de cliente"
        description="Cuenta corriente histórica de un cliente con saldo running."
        disabled={!clienteSel}
        onDownload={async () => {
          if (clienteSel) await downloadCtaCteCliente(clienteSel);
        }}
      >
        <div className="flex flex-col gap-1.5">
          <Label>Cliente</Label>
          <select
            value={clienteSel ?? ""}
            onChange={(e) =>
              setClienteSel(e.target.value === "" ? null : Number(e.target.value))
            }
            className="flex h-10 w-full rounded-[8px] border border-input bg-background px-3 py-2 text-sm text-foreground transition-colors duration-200 ease-apple focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1"
          >
            <option value="">— Elegí un cliente —</option>
            {(clientesQ.data?.items ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.codigo} · {c.razon_social}
              </option>
            ))}
          </select>
        </div>
      </ExportCard>

      <ExportCard
        title="Histórico de proveedor"
        description="Cuenta corriente histórica con compras y pagos."
        disabled={!proveedorSel}
        onDownload={async () => {
          if (proveedorSel) await downloadCtaCteProveedor(proveedorSel);
        }}
      >
        <div className="flex flex-col gap-1.5">
          <Label>Proveedor</Label>
          <select
            value={proveedorSel ?? ""}
            onChange={(e) =>
              setProveedorSel(e.target.value === "" ? null : Number(e.target.value))
            }
            className="flex h-10 w-full rounded-[8px] border border-input bg-background px-3 py-2 text-sm text-foreground transition-colors duration-200 ease-apple focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1"
          >
            <option value="">— Elegí un proveedor —</option>
            {(proveedoresQ.data ?? []).map((p) => (
              <option key={p.id} value={p.id}>
                {p.codigo} · {p.razon_social}
              </option>
            ))}
          </select>
        </div>
      </ExportCard>
    </div>
  );
}

// --- Componentes auxiliares ---

interface DateRangeFieldsProps {
  from: string;
  to: string;
  onFromChange: (value: string) => void;
  onToChange: (value: string) => void;
}

function DateRangeFields({
  from,
  to,
  onFromChange,
  onToChange,
}: DateRangeFieldsProps) {
  const idFrom = React.useId();
  const idTo = React.useId();
  return (
    <div className="grid grid-cols-2 gap-3">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={idFrom}>Desde</Label>
        <Input
          id={idFrom}
          type="date"
          value={from}
          onChange={(e) => onFromChange(e.target.value)}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={idTo}>Hasta</Label>
        <Input
          id={idTo}
          type="date"
          value={to}
          onChange={(e) => onToChange(e.target.value)}
        />
      </div>
    </div>
  );
}

interface SucursalSelectProps {
  label: string;
  value: number | null;
  onChange: (id: number | null) => void;
  sucursales:
    | { id: number; codigo: string; nombre: string; activa: boolean }[]
    | undefined;
}

function SucursalSelect({
  label,
  value,
  onChange,
  sucursales,
}: SucursalSelectProps) {
  const id = React.useId();
  const items = sucursales?.filter((s) => s.activa) ?? [];

  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <select
        id={id}
        value={value ?? ""}
        onChange={(e) =>
          onChange(e.target.value === "" ? null : Number(e.target.value))
        }
        className="flex h-10 w-full rounded-[8px] border border-input bg-background px-3 py-2 text-sm text-foreground transition-colors duration-200 ease-apple focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background"
      >
        <option value="">Todas las sucursales</option>
        {items.map((s) => (
          <option key={s.id} value={s.id}>
            {s.codigo} · {s.nombre}
          </option>
        ))}
      </select>
    </div>
  );
}
