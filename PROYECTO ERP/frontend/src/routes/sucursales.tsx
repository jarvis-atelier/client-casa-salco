import { createRoute } from "@tanstack/react-router";
import { useQueries, useQuery } from "@tanstack/react-query";
import { MapPin, Phone, Plus, Store as StoreIcon } from "lucide-react";
import { listAreasBySucursal, listSucursales } from "@/api/sucursales";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";
import { requireAccess } from "@/lib/permissions";
import { appLayoutRoute } from "./app-layout";

export const sucursalesRoute = createRoute({
  getParentRoute: () => appLayoutRoute,
  path: "/sucursales",
  beforeLoad: requireAccess("/sucursales"),
  component: SucursalesPage,
});

function SucursalesPage() {
  const { toast } = useToast();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["sucursales"],
    queryFn: listSucursales,
  });

  const items = data ?? [];

  const areasResults = useQueries({
    queries: items.map((s) => ({
      queryKey: ["sucursal-areas", s.id],
      queryFn: () => listAreasBySucursal(s.id),
      staleTime: 60_000,
    })),
  });

  return (
    <div className="flex flex-col gap-8 max-w-[1280px]">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-[28px] font-semibold tracking-tight leading-tight">
            Sucursales
          </h2>
          <p className="mt-1.5 text-[14px] text-muted-foreground">
            Nodos operativos de la red.
          </p>
        </div>
        <Button
          onClick={() =>
            toast({
              title: "Próximamente",
              description: "Alta de sucursales en Fase 2.",
            })
          }
        >
          <Plus strokeWidth={1.5} />
          Nueva sucursal
        </Button>
      </div>

      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="p-6">
              <Skeleton className="h-5 w-40 mb-3" />
              <Skeleton className="h-4 w-24 mb-6" />
              <Skeleton className="h-4 w-full mb-2" />
              <Skeleton className="h-4 w-3/4" />
            </Card>
          ))}
        </div>
      )}

      {isError && (
        <Card className="p-8 text-center">
          <p className="text-[13px] text-destructive">
            No pudimos cargar las sucursales.
          </p>
        </Card>
      )}

      {!isLoading && !isError && items.length === 0 && (
        <Card className="p-12 text-center">
          <div className="mx-auto mb-3 inline-flex rounded-full bg-muted/60 p-3">
            <StoreIcon
              className="h-6 w-6 text-muted-foreground"
              strokeWidth={1.5}
            />
          </div>
          <p className="text-[14px] font-medium text-foreground">
            No hay sucursales cargadas
          </p>
          <p className="mt-1 text-[13px] text-muted-foreground">
            Cuando crees la primera, aparecerá acá.
          </p>
        </Card>
      )}

      {!isLoading && !isError && items.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {items.map((s, i) => {
            const areas = areasResults[i]?.data ?? [];
            return (
              <Card
                key={s.id}
                className={cn(
                  "group p-6 flex flex-col gap-4 cursor-pointer transition-all duration-200 ease-apple",
                  "hover:-translate-y-0.5 hover:shadow-apple-md",
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex flex-col gap-1 min-w-0">
                    <h3 className="text-[16px] font-semibold tracking-tight truncate">
                      {s.nombre}
                    </h3>
                    <Badge variant="outline" className="w-fit font-mono">
                      {s.codigo}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <span
                      className={cn(
                        "h-2 w-2 rounded-full",
                        s.activa ? "bg-emerald-500" : "bg-muted-foreground/40",
                      )}
                    />
                    <span className="text-[11px] text-muted-foreground">
                      {s.activa ? "Activa" : "Inactiva"}
                    </span>
                  </div>
                </div>

                <div className="flex flex-col gap-2 text-[13px] text-muted-foreground">
                  {(s.direccion || s.ciudad) && (
                    <div className="flex items-start gap-2">
                      <MapPin
                        className="h-[14px] w-[14px] mt-0.5 shrink-0"
                        strokeWidth={1.5}
                      />
                      <span className="leading-relaxed">
                        {[s.direccion, s.ciudad, s.provincia]
                          .filter(Boolean)
                          .join(", ")}
                      </span>
                    </div>
                  )}
                  {s.telefono && (
                    <div className="flex items-center gap-2">
                      <Phone
                        className="h-[14px] w-[14px] shrink-0"
                        strokeWidth={1.5}
                      />
                      <span>{s.telefono}</span>
                    </div>
                  )}
                </div>

                {areas.length > 0 && (
                  <div className="mt-auto pt-3 border-t border-border flex flex-wrap gap-1.5">
                    {areas.map((a) => (
                      <Badge key={a.id} variant="secondary">
                        {a.nombre}
                      </Badge>
                    ))}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
