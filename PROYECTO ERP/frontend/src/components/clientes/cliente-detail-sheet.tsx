import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Pencil, Power } from "lucide-react";
import {
  deactivateCliente,
  listMovimientosCliente,
} from "@/api/clientes";
import type { Cliente, MovimientoCaja } from "@/lib/types";
import { parseDecimal } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/store/auth";

const CONDICION_LABEL: Record<string, string> = {
  responsable_inscripto: "Responsable Inscripto",
  monotributo: "Monotributo",
  consumidor_final: "Consumidor Final",
  exento: "Exento",
  no_categorizado: "No categorizado",
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

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat("es-AR", {
      day: "2-digit",
      month: "2-digit",
      year: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

interface DataRowProps {
  label: string;
  value: React.ReactNode;
}
function DataRow({ label, value }: DataRowProps) {
  return (
    <div className="grid grid-cols-[120px_1fr] gap-3 py-1.5">
      <span className="text-[12px] uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <span className="text-[13px] text-foreground break-words">
        {value ?? "—"}
      </span>
    </div>
  );
}

interface Props {
  cliente: Cliente | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onEdit: (cliente: Cliente) => void;
}

export function ClienteDetailSheet({
  cliente,
  open,
  onOpenChange,
  onEdit,
}: Props) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const user = useAuth((s) => s.user);
  const isAdmin = user?.rol === "admin";

  const enabled = open && Boolean(cliente?.cuenta_corriente && cliente?.id);

  const movimientosQ = useQuery({
    queryKey: ["movimientos", "cliente", cliente?.id],
    queryFn: () =>
      cliente ? listMovimientosCliente(cliente.id) : Promise.resolve([]),
    enabled,
    staleTime: 30_000,
  });

  const deactivateM = useMutation({
    mutationFn: (id: number) => deactivateCliente(id),
    onSuccess: () => {
      toast({
        title: "Cliente desactivado",
        description: cliente?.razon_social,
      });
      qc.invalidateQueries({ queryKey: ["clientes"] });
      onOpenChange(false);
    },
    onError: () => {
      toast({
        title: "No pudimos desactivar",
        description: "Probá de nuevo en un momento.",
        variant: "destructive",
      });
    },
  });

  if (!cliente) return null;

  const condicionLabel =
    CONDICION_LABEL[cliente.condicion_iva] ?? cliente.condicion_iva;

  const saldo = parseDecimal(cliente.saldo);
  const movimientos: MovimientoCaja[] = (movimientosQ.data ?? []).slice(0, 20);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-[480px] overflow-y-auto p-0"
      >
        <div className="px-6 py-6">
          <SheetHeader>
            <SheetTitle className="text-[20px] font-semibold tracking-tight">
              {cliente.razon_social}
            </SheetTitle>
            <SheetDescription className="font-mono text-[12px]">
              {cliente.codigo}
            </SheetDescription>
          </SheetHeader>

          <div className="mt-5 flex items-center gap-2 flex-wrap">
            <Badge variant={cliente.activo ? "success" : "secondary"}>
              {cliente.activo ? "Activo" : "Inactivo"}
            </Badge>
            <Badge variant="outline">{condicionLabel}</Badge>
            {cliente.cuenta_corriente && (
              <Badge variant="default">Cta cte habilitada</Badge>
            )}
          </div>

          <Separator className="my-5" />

          <div className="flex flex-col">
            <DataRow label="CUIT" value={cliente.cuit ?? "—"} />
            <DataRow label="Email" value={cliente.email ?? "—"} />
            <DataRow label="Teléfono" value={cliente.telefono ?? "—"} />
            <DataRow label="Dirección" value={cliente.direccion ?? "—"} />
            <DataRow
              label="Receptor RG 5616"
              value={cliente.condicion_iva_receptor_id ?? "—"}
            />
          </div>

          {cliente.cuenta_corriente && (
            <>
              <Separator className="my-5" />

              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-[14px] font-semibold tracking-tight">
                    Cuenta corriente
                  </h3>
                  <span
                    className={
                      saldo && saldo > 0
                        ? "text-[14px] font-semibold tabular-nums text-destructive"
                        : "text-[14px] font-semibold tabular-nums text-foreground"
                    }
                  >
                    {formatMoney(cliente.saldo)}
                  </span>
                </div>
                <div className="text-[12px] text-muted-foreground tabular-nums">
                  Límite: {formatMoney(cliente.limite_cuenta_corriente)}
                </div>

                <div className="mt-2 flex flex-col">
                  {movimientosQ.isLoading ? (
                    <div className="flex flex-col gap-2">
                      {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-10 w-full" />
                      ))}
                    </div>
                  ) : movimientos.length === 0 ? (
                    <p className="text-[13px] text-muted-foreground py-2">
                      Sin movimientos registrados.
                    </p>
                  ) : (
                    <ul className="flex flex-col divide-y divide-border">
                      {movimientos.map((m) => {
                        const monto = parseDecimal(m.monto) ?? 0;
                        const haber =
                          m.tipo === "cobranza" ||
                          m.tipo === "devolucion" ||
                          m.tipo === "ajuste";
                        return (
                          <li
                            key={m.id}
                            className="flex items-center justify-between gap-3 py-2.5"
                          >
                            <div className="flex flex-col min-w-0">
                              <span className="text-[12px] text-muted-foreground tabular-nums">
                                {formatDate(m.fecha)}
                              </span>
                              <span className="text-[13px] text-foreground truncate">
                                {m.descripcion || m.tipo}
                              </span>
                            </div>
                            <span
                              className={
                                haber
                                  ? "text-[13px] tabular-nums text-emerald-600 dark:text-emerald-400"
                                  : "text-[13px] tabular-nums text-foreground"
                              }
                            >
                              {haber ? "−" : "+"}
                              {formatMoney(monto)}
                            </span>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>
              </div>
            </>
          )}

          <Separator className="my-5" />

          <div className="flex items-center gap-2">
            <Button
              variant="default"
              onClick={() => onEdit(cliente)}
              disabled={deactivateM.isPending}
            >
              <Pencil strokeWidth={1.5} />
              Editar
            </Button>
            {isAdmin && cliente.activo && (
              <Button
                variant="outline"
                onClick={() => deactivateM.mutate(cliente.id)}
                disabled={deactivateM.isPending}
              >
                {deactivateM.isPending ? (
                  <Loader2 className="animate-spin" strokeWidth={1.5} />
                ) : (
                  <Power strokeWidth={1.5} />
                )}
                Desactivar
              </Button>
            )}
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
