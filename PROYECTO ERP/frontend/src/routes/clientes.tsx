import * as React from "react";
import { createRoute } from "@tanstack/react-router";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  Plus,
  Search,
  Users as UsersIcon,
} from "lucide-react";
import { listClientes } from "@/api/clientes";
import type { Cliente, CondicionIva } from "@/lib/types";
import { parseDecimal } from "@/lib/types";
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
import { ClienteFormDialog } from "@/components/clientes/cliente-form-dialog";
import { ClienteDetailSheet } from "@/components/clientes/cliente-detail-sheet";
import { cn } from "@/lib/utils";
import { appLayoutRoute } from "./app-layout";

const PER_PAGE = 25;

export const clientesRoute = createRoute({
  getParentRoute: () => appLayoutRoute,
  path: "/clientes",
  component: ClientesPage,
});

type FiltroId = "todos" | CondicionIva | "cta_cte";

const FILTROS: { id: FiltroId; label: string }[] = [
  { id: "todos", label: "Todos" },
  { id: "responsable_inscripto", label: "RI" },
  { id: "monotributo", label: "Monotributo" },
  { id: "consumidor_final", label: "Consumidor Final" },
  { id: "exento", label: "Exento" },
  { id: "cta_cte", label: "Con Cta Cte" },
];

const CONDICION_BADGE: Record<
  CondicionIva,
  { label: string; variant: "default" | "secondary" | "outline" }
> = {
  responsable_inscripto: { label: "RI", variant: "default" },
  monotributo: { label: "Monotributo", variant: "outline" },
  consumidor_final: { label: "C. Final", variant: "secondary" },
  exento: { label: "Exento", variant: "outline" },
  no_categorizado: { label: "No cat.", variant: "secondary" },
};

function formatMoney(v?: string | number | null): string {
  const n = parseDecimal(v);
  if (n === null) return "—";
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n);
}

function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = React.useState(value);
  React.useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);
  return debounced;
}

function ClientesPage() {
  const [page, setPage] = React.useState(1);
  const [query, setQuery] = React.useState("");
  const [filtro, setFiltro] = React.useState<FiltroId>("todos");
  const debouncedQuery = useDebounced(query, 350);

  const [selected, setSelected] = React.useState<Cliente | null>(null);
  const [sheetOpen, setSheetOpen] = React.useState(false);
  const [formOpen, setFormOpen] = React.useState(false);
  const [editTarget, setEditTarget] = React.useState<Cliente | null>(null);

  React.useEffect(() => {
    setPage(1);
  }, [debouncedQuery, filtro]);

  const { data, isLoading, isFetching, isError } = useQuery({
    queryKey: ["clientes", { page, q: debouncedQuery }],
    queryFn: () =>
      listClientes({
        page,
        per_page: PER_PAGE,
        q: debouncedQuery || undefined,
      }),
    placeholderData: keepPreviousData,
  });

  const items = data?.items ?? [];

  const filteredItems = React.useMemo(() => {
    if (filtro === "todos") return items;
    if (filtro === "cta_cte")
      return items.filter((c) => c.cuenta_corriente);
    return items.filter((c) => c.condicion_iva === filtro);
  }, [items, filtro]);

  const total = data?.total ?? 0;
  const pages = data?.pages ?? 1;
  const from = total === 0 ? 0 : (page - 1) * PER_PAGE + 1;
  const to = Math.min(page * PER_PAGE, total);

  const openDetail = (cli: Cliente) => {
    setSelected(cli);
    setSheetOpen(true);
  };

  const handleEdit = (cli: Cliente) => {
    setEditTarget(cli);
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
            Clientes
          </h2>
          <p className="mt-1.5 text-[14px] text-muted-foreground">
            Hacé clic en una fila para ver el detalle y la cuenta corriente.
          </p>
        </div>
        <Button onClick={handleNew}>
          <Plus strokeWidth={1.5} />
          Nuevo cliente
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
              <TableHead className="w-[140px]">Condición IVA</TableHead>
              <TableHead>Tel / Email</TableHead>
              <TableHead className="w-[110px]">Cta cte</TableHead>
              <TableHead className="w-[130px] text-right">Saldo</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && items.length === 0
              ? Array.from({ length: 6 }).map((_, i) => (
                  <TableRow key={`sk-${i}`} className="hover:bg-transparent">
                    <TableCell colSpan={7}>
                      <Skeleton className="h-5 w-full" />
                    </TableCell>
                  </TableRow>
                ))
              : filteredItems.map((c) => {
                  const cond = CONDICION_BADGE[c.condicion_iva] ?? {
                    label: c.condicion_iva,
                    variant: "secondary" as const,
                  };
                  const saldoNum = parseDecimal(c.saldo);
                  const saldoColor =
                    saldoNum !== null && saldoNum > 0
                      ? "text-destructive"
                      : "text-foreground";
                  const contacto = [c.telefono, c.email]
                    .filter(Boolean)
                    .join(" · ");
                  return (
                    <TableRow
                      key={c.id}
                      className="cursor-pointer"
                      onClick={() => openDetail(c)}
                    >
                      <TableCell className="font-mono text-[12px] text-muted-foreground">
                        {c.codigo}
                      </TableCell>
                      <TableCell className="font-medium text-foreground">
                        {c.razon_social}
                        {!c.activo && (
                          <Badge
                            variant="secondary"
                            className="ml-2 align-middle"
                          >
                            Inactivo
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="font-mono text-[12px] text-muted-foreground">
                        {c.cuit || "—"}
                      </TableCell>
                      <TableCell>
                        <Badge variant={cond.variant}>{cond.label}</Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground text-[12px] truncate max-w-[260px]">
                        {contacto || "—"}
                      </TableCell>
                      <TableCell>
                        {c.cuenta_corriente ? (
                          <Badge variant="default">Habilitada</Badge>
                        ) : (
                          <Badge variant="secondary">No</Badge>
                        )}
                      </TableCell>
                      <TableCell
                        className={cn(
                          "text-right tabular-nums font-medium",
                          saldoColor,
                        )}
                      >
                        {c.cuenta_corriente ? formatMoney(c.saldo) : "—"}
                      </TableCell>
                    </TableRow>
                  );
                })}

            {!isLoading && filteredItems.length === 0 && (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={7} className="py-16">
                  <div className="flex flex-col items-center gap-3 text-center">
                    <div className="rounded-full bg-muted/60 p-3">
                      <UsersIcon
                        className="h-6 w-6 text-muted-foreground"
                        strokeWidth={1.5}
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <p className="text-[14px] font-medium text-foreground">
                        {debouncedQuery || filtro !== "todos"
                          ? "Sin resultados"
                          : "No hay clientes cargados"}
                      </p>
                      <p className="text-[13px] text-muted-foreground">
                        {debouncedQuery
                          ? `No encontramos clientes para “${debouncedQuery}”.`
                          : "Cuando crees tu primer cliente, aparecerá acá."}
                      </p>
                    </div>
                  </div>
                </TableCell>
              </TableRow>
            )}

            {isError && (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={7} className="py-12 text-center">
                  <p className="text-[13px] text-destructive">
                    No pudimos cargar los clientes.
                  </p>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Card>

      <div className="flex items-center justify-between gap-4">
        <p className="text-[13px] text-muted-foreground tabular-nums">
          {total === 0
            ? "Sin clientes"
            : `Mostrando ${from}-${to} de ${total} clientes`}
          {isFetching && !isLoading && (
            <span className="ml-2 text-muted-foreground/70">
              actualizando…
            </span>
          )}
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1 || isLoading}
          >
            <ChevronLeft strokeWidth={1.5} />
            Anterior
          </Button>
          <span className="text-[13px] tabular-nums text-muted-foreground min-w-[64px] text-center">
            {page} / {pages || 1}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.min(pages || 1, p + 1))}
            disabled={page >= (pages || 1) || isLoading}
          >
            Siguiente
            <ChevronRight strokeWidth={1.5} />
          </Button>
        </div>
      </div>

      <ClienteDetailSheet
        cliente={selected}
        open={sheetOpen}
        onOpenChange={(o) => {
          setSheetOpen(o);
          if (!o) setSelected(null);
        }}
        onEdit={handleEdit}
      />

      <ClienteFormDialog
        open={formOpen}
        onOpenChange={(o) => {
          setFormOpen(o);
          if (!o) setEditTarget(null);
        }}
        cliente={editTarget}
      />
    </div>
  );
}
