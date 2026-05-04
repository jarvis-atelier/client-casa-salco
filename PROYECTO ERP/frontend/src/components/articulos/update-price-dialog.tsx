import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import {
  actualizarPrecios,
  listPreciosByArticulo,
  type PrecioCambio,
} from "@/api/precios";
import { listSucursales } from "@/api/sucursales";
import type { Articulo, Sucursal } from "@/lib/types";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";

interface UpdatePriceDialogProps {
  articulo: Articulo | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface SucursalRow {
  sucursal: Sucursal;
  precioActual: string | null; // string decimal o null si no hay precio
  precioInput: string; // lo que el usuario tipea
}

function isValidPrecio(raw: string): boolean {
  if (raw.trim() === "") return false;
  const n = Number(raw.replace(",", "."));
  return Number.isFinite(n) && n > 0;
}

export function UpdatePriceDialog({
  articulo,
  open,
  onOpenChange,
}: UpdatePriceDialogProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const sucursalesQ = useQuery({
    queryKey: ["sucursales"],
    queryFn: listSucursales,
    enabled: open,
  });

  const preciosQ = useQuery({
    queryKey: ["precios", articulo?.id],
    queryFn: () => listPreciosByArticulo(articulo!.id),
    enabled: open && !!articulo?.id,
  });

  const [motivo, setMotivo] = React.useState("");
  const [rows, setRows] = React.useState<SucursalRow[]>([]);
  const [aplicarATodas, setAplicarATodas] = React.useState(false);

  // Inicializar rows cuando los queries llegan
  React.useEffect(() => {
    if (!open) return;
    const sucursales = (sucursalesQ.data ?? []).filter((s) => s.activa);
    if (sucursales.length === 0) {
      setRows([]);
      return;
    }
    const preciosBySuc = new Map<number, string>();
    (preciosQ.data ?? []).forEach((p) =>
      preciosBySuc.set(p.sucursal.id, p.precio),
    );
    setRows(
      sucursales.map((s) => ({
        sucursal: s,
        precioActual: preciosBySuc.get(s.id) ?? null,
        precioInput: "",
      })),
    );
  }, [open, sucursalesQ.data, preciosQ.data]);

  // Resetear state al cerrar
  React.useEffect(() => {
    if (!open) {
      setMotivo("");
      setAplicarATodas(false);
      setRows([]);
    }
  }, [open]);

  const handleRowChange = (sucursalId: number, value: string) => {
    setRows((prev) =>
      prev.map((r) =>
        r.sucursal.id === sucursalId ? { ...r, precioInput: value } : r,
      ),
    );
    // si está el checkbox, propagar a todos
    if (aplicarATodas) {
      setRows((prev) => prev.map((r) => ({ ...r, precioInput: value })));
    }
  };

  const handleToggleAll = (checked: boolean) => {
    setAplicarATodas(checked);
    if (checked) {
      // al activarlo, tomamos el primer valor no vacío como fuente
      const fuente = rows.find((r) => r.precioInput.trim() !== "");
      if (fuente) {
        setRows((prev) =>
          prev.map((r) => ({ ...r, precioInput: fuente.precioInput })),
        );
      }
    }
  };

  const mutation = useMutation({
    mutationFn: async () => {
      if (!articulo) throw new Error("articulo requerido");
      if (aplicarATodas) {
        const precio = rows[0]?.precioInput ?? "";
        return actualizarPrecios({
          articulo_id: articulo.id,
          motivo: motivo.trim() || undefined,
          precio,
          aplicar_a_todas: true,
        });
      }
      const cambios: PrecioCambio[] = rows
        .filter((r) => r.precioInput.trim() !== "" && isValidPrecio(r.precioInput))
        .map((r) => ({
          sucursal_id: r.sucursal.id,
          precio: r.precioInput.replace(",", "."),
        }));
      return actualizarPrecios({
        articulo_id: articulo.id,
        motivo: motivo.trim() || undefined,
        cambios,
      });
    },
    onSuccess: (data) => {
      toast({
        title: "Precio sincronizado",
        description: `Actualizado en ${data.actualizados} sucursal${data.actualizados === 1 ? "" : "es"}.`,
      });
      queryClient.invalidateQueries({ queryKey: ["articulos"] });
      if (articulo) {
        queryClient.invalidateQueries({ queryKey: ["precios", articulo.id] });
      }
      onOpenChange(false);
    },
    onError: (err: unknown) => {
      const detail =
        err instanceof Error ? err.message : "No pudimos actualizar el precio.";
      toast({
        title: "Error al actualizar",
        description: detail,
        variant: "destructive",
      });
    },
  });

  // Validaciones de UI
  const motivoOk = motivo.trim().length >= 3;
  const rowsWithInput = rows.filter((r) => r.precioInput.trim() !== "");
  const allRowsValid =
    rowsWithInput.length > 0 &&
    rowsWithInput.every((r) => isValidPrecio(r.precioInput));
  const canSubmit = motivoOk && allRowsValid && !mutation.isPending;

  const loading = sucursalesQ.isLoading || preciosQ.isLoading;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Actualizar precio</DialogTitle>
          <DialogDescription asChild>
            <div className="flex items-center gap-2 text-[13px]">
              <span className="rounded-md bg-muted/60 px-2 py-0.5 font-mono text-[11px] text-muted-foreground">
                {articulo?.codigo ?? "—"}
              </span>
              <span className="truncate">{articulo?.descripcion ?? ""}</span>
            </div>
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-5">
          <div className="flex flex-col gap-2">
            <Label htmlFor="motivo">Motivo del cambio</Label>
            <Input
              id="motivo"
              placeholder="Ej. ajuste semanal, actualización proveedor…"
              value={motivo}
              onChange={(e) => setMotivo(e.target.value)}
              maxLength={255}
            />
            {motivo.length > 0 && !motivoOk && (
              <p className="text-[12px] text-destructive">
                El motivo debe tener al menos 3 caracteres.
              </p>
            )}
          </div>

          <div className="flex items-center gap-2">
            <input
              id="aplicar-todas"
              type="checkbox"
              checked={aplicarATodas}
              onChange={(e) => handleToggleAll(e.target.checked)}
              className="h-4 w-4 rounded border-border text-primary focus:ring-primary"
            />
            <Label htmlFor="aplicar-todas" className="cursor-pointer">
              Aplicar el mismo precio a todas las sucursales
            </Label>
          </div>

          <div className="overflow-hidden rounded-[10px] border border-border">
            <table className="w-full text-[13px]">
              <thead className="bg-muted/40">
                <tr className="text-left text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  <th className="px-4 py-2.5">Sucursal</th>
                  <th className="px-4 py-2.5 text-right w-[160px]">
                    Precio actual
                  </th>
                  <th className="px-4 py-2.5 text-right w-[180px]">
                    Precio nuevo
                  </th>
                </tr>
              </thead>
              <tbody>
                {loading && (
                  <tr>
                    <td colSpan={3} className="px-4 py-4">
                      <Skeleton className="h-8 w-full" />
                    </td>
                  </tr>
                )}
                {!loading && rows.length === 0 && (
                  <tr>
                    <td
                      colSpan={3}
                      className="px-4 py-8 text-center text-muted-foreground"
                    >
                      No hay sucursales activas.
                    </td>
                  </tr>
                )}
                {!loading &&
                  rows.map((row) => (
                    <tr key={row.sucursal.id} className="border-t border-border">
                      <td className="px-4 py-3">
                        <div className="flex flex-col">
                          <span className="font-medium text-foreground">
                            {row.sucursal.nombre}
                          </span>
                          <span className="text-[11px] font-mono text-muted-foreground">
                            {row.sucursal.codigo}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">
                        {row.precioActual ?? "—"}
                      </td>
                      <td className="px-4 py-3">
                        <Input
                          type="number"
                          step="0.01"
                          min="0"
                          inputMode="decimal"
                          placeholder="0.00"
                          value={row.precioInput}
                          onChange={(e) =>
                            handleRowChange(row.sucursal.id, e.target.value)
                          }
                          className="h-9 text-right tabular-nums"
                        />
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>

        <DialogFooter className="gap-2">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={mutation.isPending}
          >
            Cancelar
          </Button>
          <Button onClick={() => mutation.mutate()} disabled={!canSubmit}>
            {mutation.isPending && (
              <Loader2 className="animate-spin" strokeWidth={1.5} />
            )}
            Confirmar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
