import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AxiosError } from "axios";
import { Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { listProveedoresFull } from "@/api/proveedores";
import { listSucursales } from "@/api/sucursales";
import {
  createCompromiso,
  listTarjetas,
  type CompromisoCreatePayload,
} from "@/api/calendario-pagos";
import { useToast } from "@/hooks/use-toast";
import type { TipoCompromiso } from "@/lib/types";
import { tipoCompromisoLabel } from "./format";

interface NuevoCompromisoDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const TIPOS: TipoCompromiso[] = [
  "factura_compra",
  "cuenta_corriente_proveedor",
  "tarjeta_corporativa",
  "servicio",
  "impuesto",
  "otro",
];

export function NuevoCompromisoDialog({
  open,
  onOpenChange,
}: NuevoCompromisoDialogProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [tipo, setTipo] = React.useState<TipoCompromiso>("factura_compra");
  const [descripcion, setDescripcion] = React.useState("");
  const [montoTotal, setMontoTotal] = React.useState("");
  const [fechaEmision, setFechaEmision] = React.useState("");
  const [fechaVencimiento, setFechaVencimiento] = React.useState("");
  const [proveedorId, setProveedorId] = React.useState<number | "">("");
  const [tarjetaId, setTarjetaId] = React.useState<number | "">("");
  const [sucursalId, setSucursalId] = React.useState<number | "">("");
  const [nota, setNota] = React.useState("");

  const { data: proveedores = [] } = useQuery({
    queryKey: ["proveedores-full"],
    queryFn: listProveedoresFull,
    enabled: open,
  });
  const { data: tarjetas = [] } = useQuery({
    queryKey: ["tarjetas"],
    queryFn: listTarjetas,
    enabled: open,
  });
  const { data: sucursales = [] } = useQuery({
    queryKey: ["sucursales"],
    queryFn: listSucursales,
    enabled: open,
  });

  React.useEffect(() => {
    if (open) {
      setTipo("factura_compra");
      setDescripcion("");
      setMontoTotal("");
      setFechaEmision("");
      setFechaVencimiento("");
      setProveedorId("");
      setTarjetaId("");
      setSucursalId("");
      setNota("");
    }
  }, [open]);

  const mutation = useMutation({
    mutationFn: () => {
      const payload: CompromisoCreatePayload = {
        tipo,
        descripcion: descripcion.trim(),
        monto_total: montoTotal,
        fecha_emision: fechaEmision || null,
        fecha_vencimiento: fechaVencimiento,
        proveedor_id: proveedorId === "" ? null : Number(proveedorId),
        tarjeta_id: tarjetaId === "" ? null : Number(tarjetaId),
        sucursal_id: sucursalId === "" ? null : Number(sucursalId),
        nota: nota.trim() || null,
      };
      return createCompromiso(payload);
    },
    onSuccess: () => {
      toast({ title: "Compromiso creado" });
      queryClient.invalidateQueries({ queryKey: ["compromisos"] });
      queryClient.invalidateQueries({ queryKey: ["compromisos-resumen"] });
      queryClient.invalidateQueries({ queryKey: ["compromisos-calendar"] });
      onOpenChange(false);
    },
    onError: (err) => {
      const msg =
        (err as AxiosError<{ error?: string }>).response?.data?.error ??
        "No pudimos crear el compromiso.";
      toast({ variant: "destructive", title: "Error", description: msg });
    },
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!descripcion.trim() || !montoTotal || !fechaVencimiento) {
      toast({
        variant: "destructive",
        title: "Faltan datos",
        description: "Descripción, monto y vencimiento son obligatorios.",
      });
      return;
    }
    mutation.mutate();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nuevo compromiso de pago</DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label className="text-[11px] uppercase tracking-wider text-muted-foreground">
                Tipo
              </Label>
              <select
                value={tipo}
                onChange={(e) => setTipo(e.target.value as TipoCompromiso)}
                className="h-10 rounded-[8px] border border-border bg-background px-3 text-[13px] focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {TIPOS.map((t) => (
                  <option key={t} value={t}>
                    {tipoCompromisoLabel(t)}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-[11px] uppercase tracking-wider text-muted-foreground">
                Monto total
              </Label>
              <Input
                type="number"
                step="0.01"
                min="0.01"
                value={montoTotal}
                onChange={(e) => setMontoTotal(e.target.value)}
                className="tabular-nums"
                required
              />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label className="text-[11px] uppercase tracking-wider text-muted-foreground">
              Descripción
            </Label>
            <Input
              value={descripcion}
              onChange={(e) => setDescripcion(e.target.value)}
              placeholder="Ej: Factura C 0001-00000123 — Coca Cola"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label className="text-[11px] uppercase tracking-wider text-muted-foreground">
                Emisión
              </Label>
              <Input
                type="date"
                value={fechaEmision}
                onChange={(e) => setFechaEmision(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-[11px] uppercase tracking-wider text-muted-foreground">
                Vencimiento
              </Label>
              <Input
                type="date"
                value={fechaVencimiento}
                onChange={(e) => setFechaVencimiento(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label className="text-[11px] uppercase tracking-wider text-muted-foreground">
                Proveedor
              </Label>
              <select
                value={proveedorId}
                onChange={(e) =>
                  setProveedorId(
                    e.target.value === "" ? "" : Number(e.target.value),
                  )
                }
                className="h-10 rounded-[8px] border border-border bg-background px-3 text-[13px] focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="">—</option>
                {proveedores.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.razon_social}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-[11px] uppercase tracking-wider text-muted-foreground">
                Tarjeta
              </Label>
              <select
                value={tarjetaId}
                onChange={(e) =>
                  setTarjetaId(
                    e.target.value === "" ? "" : Number(e.target.value),
                  )
                }
                className="h-10 rounded-[8px] border border-border bg-background px-3 text-[13px] focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="">—</option>
                {tarjetas.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.nombre} ****{t.ultimos_4}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label className="text-[11px] uppercase tracking-wider text-muted-foreground">
              Sucursal
            </Label>
            <select
              value={sucursalId}
              onChange={(e) =>
                setSucursalId(e.target.value === "" ? "" : Number(e.target.value))
              }
              className="h-10 rounded-[8px] border border-border bg-background px-3 text-[13px] focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="">—</option>
              {sucursales.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.codigo} · {s.nombre}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label className="text-[11px] uppercase tracking-wider text-muted-foreground">
              Nota (opcional)
            </Label>
            <Input
              value={nota}
              onChange={(e) => setNota(e.target.value)}
              placeholder="Notas internas"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={mutation.isPending}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" strokeWidth={1.5} />
              )}
              Crear compromiso
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
