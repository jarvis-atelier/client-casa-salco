import * as React from "react";
import { createRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Plus, Search, Truck } from "lucide-react";
import { listProveedoresFull } from "@/api/proveedores";
import type { ProveedorFull } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ProveedorFormDialog } from "@/components/proveedores/proveedor-form-dialog";
import { ProveedorDetailSheet } from "@/components/proveedores/proveedor-detail-sheet";
import { cn } from "@/lib/utils";
import { requireAccess } from "@/lib/permissions";
import { appLayoutRoute } from "./app-layout";

export const proveedoresRoute = createRoute({
  getParentRoute: () => appLayoutRoute,
  path: "/proveedores",
  beforeLoad: requireAccess("/proveedores"),
  component: ProveedoresPage,
});

type FiltroId = "todos" | "activos" | "inactivos";

const FILTROS: { id: FiltroId; label: string }[] = [
  { id: "todos", label: "Todos" },
  { id: "activos", label: "Activos" },
  { id: "inactivos", label: "Inactivos" },
];

function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = React.useState(value);
  React.useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);
  return debounced;
}

function ProveedoresPage() {
  const [query, setQuery] = React.useState("");
  const [filtro, setFiltro] = React.useState<FiltroId>("activos");
  const debouncedQuery = useDebounced(query, 350);

  const [selected, setSelected] = React.useState<ProveedorFull | null>(null);
  const [sheetOpen, setSheetOpen] = React.useState(false);
  const [formOpen, setFormOpen] = React.useState(false);
  const [editTarget, setEditTarget] = React.useState<ProveedorFull | null>(
    null,
  );

  const { data, isLoading, isError, isFetching } = useQuery({
    queryKey: ["proveedores-full"],
    queryFn: listProveedoresFull,
    staleTime: 30_000,
  });

  const items = data ?? [];

  const filtered = React.useMemo(() => {
    let arr = items;
    if (filtro === "activos") arr = arr.filter((p) => p.activo);
    else if (filtro === "inactivos") arr = arr.filter((p) => !p.activo);
    if (debouncedQuery.trim()) {
      const q = debouncedQuery.trim().toLowerCase();
      arr = arr.filter(
        (p) =>
          p.codigo.toLowerCase().includes(q) ||
          p.razon_social.toLowerCase().includes(q) ||
          (p.cuit ?? "").toLowerCase().includes(q),
      );
    }
    return arr;
  }, [items, filtro, debouncedQuery]);

  const openDetail = (p: ProveedorFull) => {
    setSelected(p);
    setSheetOpen(true);
  };

  const handleEdit = (p: ProveedorFull) => {
    setEditTarget(p);
    setSheetOpen(false);
    setFormOpen(true);
  };

  const handleNew = () => {
    setEditTarget(null);
    setFormOpen(true);
  };

  return (
    <div className="flex flex-col gap-8 max-w-[1280px]">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-[28px] font-semibold tracking-tight leading-tight">
            Proveedores
          </h2>
          <p className="mt-1.5 text-[14px] text-muted-foreground">
            Hacé clic en una fila para ver el detalle.
          </p>
        </div>
        <Button onClick={handleNew}>
          <Plus strokeWidth={1.5} />
          Nuevo proveedor
        </Button>
      </div>

      <div className="flex flex-col gap-4">
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-[16px] w-[16px] text-muted-foreground"
            strokeWidth={1.5}
          />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar por código, razón social o CUIT…"
            className="h-10 pl-9"
          />
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {FILTROS.map((f) => {
            const active = filtro === f.id;
            return (
              <button
                key={f.id}
                type="button"
                onClick={() => setFiltro(f.id)}
                className={cn(
                  "h-8 px-3 rounded-full border text-[12px] font-medium transition-colors duration-200 ease-apple",
                  active
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border bg-transparent text-muted-foreground hover:bg-muted/50",
                )}
              >
                {f.label}
              </button>
            );
          })}
        </div>
      </div>

      <Card className="overflow-hidden p-0">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="w-[120px]">Código</TableHead>
              <TableHead>Razón social</TableHead>
              <TableHead className="w-[140px]">CUIT</TableHead>
              <TableHead>Tel / Email</TableHead>
              <TableHead className="w-[100px]">Estado</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading
              ? Array.from({ length: 6 }).map((_, i) => (
                  <TableRow key={`sk-${i}`} className="hover:bg-transparent">
                    <TableCell colSpan={5}>
                      <Skeleton className="h-5 w-full" />
                    </TableCell>
                  </TableRow>
                ))
              : filtered.map((p) => {
                  const contacto = [p.telefono, p.email]
                    .filter(Boolean)
                    .join(" · ");
                  return (
                    <TableRow
                      key={p.id}
                      className="cursor-pointer"
                      onClick={() => openDetail(p)}
                    >
                      <TableCell className="font-mono text-[12px] text-muted-foreground">
                        {p.codigo}
                      </TableCell>
                      <TableCell className="font-medium text-foreground">
                        {p.razon_social}
                      </TableCell>
                      <TableCell className="font-mono text-[12px] text-muted-foreground">
                        {p.cuit || "—"}
                      </TableCell>
                      <TableCell className="text-muted-foreground text-[12px] truncate max-w-[280px]">
                        {contacto || "—"}
                      </TableCell>
                      <TableCell>
                        {p.activo ? (
                          <Badge variant="success">Activo</Badge>
                        ) : (
                          <Badge variant="secondary">Inactivo</Badge>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}

            {!isLoading && filtered.length === 0 && (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={5} className="py-16">
                  <div className="flex flex-col items-center gap-3 text-center">
                    <div className="rounded-full bg-muted/60 p-3">
                      <Truck
                        className="h-6 w-6 text-muted-foreground"
                        strokeWidth={1.5}
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <p className="text-[14px] font-medium text-foreground">
                        {debouncedQuery || filtro !== "todos"
                          ? "Sin resultados"
                          : "No hay proveedores cargados"}
                      </p>
                      <p className="text-[13px] text-muted-foreground">
                        {debouncedQuery
                          ? `No encontramos proveedores para “${debouncedQuery}”.`
                          : "Cuando crees tu primer proveedor, aparecerá acá."}
                      </p>
                    </div>
                  </div>
                </TableCell>
              </TableRow>
            )}

            {isError && (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={5} className="py-12 text-center">
                  <p className="text-[13px] text-destructive">
                    No pudimos cargar los proveedores.
                  </p>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Card>

      <p className="text-[13px] text-muted-foreground tabular-nums">
        {filtered.length === 0
          ? "Sin proveedores"
          : `${filtered.length} ${filtered.length === 1 ? "proveedor" : "proveedores"}`}
        {isFetching && !isLoading && (
          <span className="ml-2 text-muted-foreground/70">actualizando…</span>
        )}
      </p>

      <ProveedorDetailSheet
        proveedor={selected}
        open={sheetOpen}
        onOpenChange={(o) => {
          setSheetOpen(o);
          if (!o) setSelected(null);
        }}
        onEdit={handleEdit}
      />

      <ProveedorFormDialog
        open={formOpen}
        onOpenChange={(o) => {
          setFormOpen(o);
          if (!o) setEditTarget(null);
        }}
        proveedor={editTarget}
      />
    </div>
  );
}
