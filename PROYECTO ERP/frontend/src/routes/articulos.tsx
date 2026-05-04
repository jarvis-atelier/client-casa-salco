import * as React from "react";
import { createRoute } from "@tanstack/react-router";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Package, Plus, Search } from "lucide-react";
import { listArticulos } from "@/api/articulos";
import { listFamilias, listRubros } from "@/api/catalogos";
import type { Articulo } from "@/lib/types";
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
import { CreateArticleDialog } from "@/components/articulos/create-article-dialog";
import { UpdatePriceDialog } from "@/components/articulos/update-price-dialog";
import { appLayoutRoute } from "./app-layout";

const PER_PAGE = 20;

export const articulosRoute = createRoute({
  getParentRoute: () => appLayoutRoute,
  path: "/articulos",
  component: ArticulosPage,
});

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

function ArticulosPage() {
  const [page, setPage] = React.useState(1);
  const [query, setQuery] = React.useState("");
  const debouncedQuery = useDebounced(query, 350);

  const [selectedArticulo, setSelectedArticulo] =
    React.useState<Articulo | null>(null);
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [createOpen, setCreateOpen] = React.useState(false);

  React.useEffect(() => {
    setPage(1);
  }, [debouncedQuery]);

  const { data, isLoading, isFetching, isError } = useQuery({
    queryKey: ["articulos", { page, q: debouncedQuery }],
    queryFn: () =>
      listArticulos({
        page,
        per_page: PER_PAGE,
        q: debouncedQuery || undefined,
      }),
    placeholderData: keepPreviousData,
  });

  const familiasQ = useQuery({ queryKey: ["familias"], queryFn: listFamilias });
  const rubrosQ = useQuery({ queryKey: ["rubros"], queryFn: listRubros });

  const familiasById = React.useMemo(() => {
    const map = new Map<number, string>();
    (familiasQ.data ?? []).forEach((f) => map.set(f.id, f.nombre));
    return map;
  }, [familiasQ.data]);

  const rubrosById = React.useMemo(() => {
    const map = new Map<number, string>();
    (rubrosQ.data ?? []).forEach((r) => map.set(r.id, r.nombre));
    return map;
  }, [rubrosQ.data]);

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const pages = data?.pages ?? 1;
  const from = total === 0 ? 0 : (page - 1) * PER_PAGE + 1;
  const to = Math.min(page * PER_PAGE, total);

  const openDialogFor = (a: Articulo) => {
    setSelectedArticulo(a);
    setDialogOpen(true);
  };

  return (
    <div className="flex flex-col gap-8 max-w-[1280px]">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-[28px] font-semibold tracking-tight leading-tight">
            Artículos
          </h2>
          <p className="mt-1.5 text-[14px] text-muted-foreground">
            Catálogo unificado del sistema. Hacé clic en una fila para
            actualizar el precio en todas las sucursales.
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus strokeWidth={1.5} />
          Nuevo artículo
        </Button>
      </div>

      <div className="relative">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-[16px] w-[16px] text-muted-foreground"
          strokeWidth={1.5}
        />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Buscar por código o descripción…"
          className="h-10 pl-9"
        />
      </div>

      <Card className="overflow-hidden p-0">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="w-[140px]">Código</TableHead>
              <TableHead>Descripción</TableHead>
              <TableHead>Familia / Rubro</TableHead>
              <TableHead className="w-[90px]">Unidad</TableHead>
              <TableHead className="w-[130px] text-right">Costo</TableHead>
              <TableHead className="w-[130px] text-right">PVP Base</TableHead>
              <TableHead className="w-[100px]">Estado</TableHead>
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
              : items.map((a) => {
                  const fam = a.familia_id ? familiasById.get(a.familia_id) : null;
                  const rub = a.rubro_id ? rubrosById.get(a.rubro_id) : null;
                  const famRub = [fam, rub].filter(Boolean).join(" · ") || "—";
                  return (
                    <TableRow
                      key={a.id}
                      className="cursor-pointer"
                      onClick={() => openDialogFor(a)}
                    >
                      <TableCell className="font-mono text-[12px] text-muted-foreground">
                        {a.codigo}
                      </TableCell>
                      <TableCell className="font-medium text-foreground">
                        {a.descripcion}
                      </TableCell>
                      <TableCell className="text-muted-foreground text-[13px]">
                        {famRub}
                      </TableCell>
                      <TableCell className="text-muted-foreground text-[13px]">
                        {a.unidad_medida || "—"}
                      </TableCell>
                      <TableCell className="text-right tabular-nums text-[13px]">
                        {formatMoney(a.costo)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums font-medium">
                        {formatMoney(a.pvp_base)}
                      </TableCell>
                      <TableCell>
                        {a.activo ? (
                          <Badge variant="success">Activo</Badge>
                        ) : (
                          <Badge variant="secondary">Inactivo</Badge>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}

            {!isLoading && items.length === 0 && (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={7} className="py-16">
                  <div className="flex flex-col items-center gap-3 text-center">
                    <div className="rounded-full bg-muted/60 p-3">
                      <Package
                        className="h-6 w-6 text-muted-foreground"
                        strokeWidth={1.5}
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <p className="text-[14px] font-medium text-foreground">
                        {debouncedQuery
                          ? "Sin resultados"
                          : "No hay artículos cargados"}
                      </p>
                      <p className="text-[13px] text-muted-foreground">
                        {debouncedQuery
                          ? `No encontramos artículos para “${debouncedQuery}”.`
                          : "Cuando crees tu primer artículo, aparecerá acá."}
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
                    No pudimos cargar los artículos.
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
            ? "Sin artículos"
            : `Mostrando ${from}-${to} de ${total} artículos`}
          {isFetching && !isLoading && (
            <span className="ml-2 text-muted-foreground/70">actualizando…</span>
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

      <UpdatePriceDialog
        articulo={selectedArticulo}
        open={dialogOpen}
        onOpenChange={(o) => {
          setDialogOpen(o);
          if (!o) setSelectedArticulo(null);
        }}
      />

      <CreateArticleDialog open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  );
}
