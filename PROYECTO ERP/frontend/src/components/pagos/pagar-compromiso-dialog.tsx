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
import { listSucursales } from "@/api/sucursales";
import { pagarCompromiso } from "@/api/calendario-pagos";
import { useToast } from "@/hooks/use-toast";
import type { CompromisoPago } from "@/lib/types";
import { parseDecimal } from "@/lib/types";
import { todayInputValue } from "@/components/facturas/format";
import { formatMoney } from "@/components/facturas/format";

interface PagarCompromisoDialogProps {
  compromiso: CompromisoPago | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPaid?: () => void;
}

const MEDIOS = [
  { value: "efectivo", label: "Efectivo" },
  { value: "transferencia", label: "Transferencia" },
  { value: "cheque", label: "Cheque" },
  { value: "tarjeta_credito", label: "Tarjeta crédito" },
  { value: "tarjeta_debito", label: "Tarjeta débito" },
  { value: "qr_mercadopago", label: "QR MercadoPago" },
];

export function PagarCompromisoDialog({
  compromiso,
  open,
  onOpenChange,
  onPaid,
}: PagarCompromisoDialogProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const pendiente = compromiso
    ? Number(parseDecimal(compromiso.monto_total) ?? 0) -
      Number(parseDecimal(compromiso.monto_pagado) ?? 0)
    : 0;

  const [monto, setMonto] = React.useState<string>("");
  const [fechaPago, setFechaPago] = React.useState<string>(todayInputValue());
  const [medio, setMedio] = React.useState<string>("efectivo");
  const [referencia, setReferencia] = React.useState<string>("");
  const [registrarMov, setRegistrarMov] = React.useState<boolean>(false);
  const [sucursalId, setSucursalId] = React.useState<number | "">("");

  const { data: sucursales = [] } = useQuery({
    queryKey: ["sucursales"],
    queryFn: listSucursales,
  });

  // Reset al abrir
  React.useEffect(() => {
    if (open && compromiso) {
      setMonto(String(pendiente.toFixed(2)));
      setFechaPago(todayInputValue());
      setMedio("efectivo");
      setReferencia("");
      setRegistrarMov(false);
      setSucursalId(compromiso.sucursal_id ?? "");
    }
  }, [open, compromiso, pendiente]);

  const mutation = useMutation({
    mutationFn: () => {
      if (!compromiso) throw new Error("compromiso requerido");
      return pagarCompromiso(compromiso.id, {
        monto: monto,
        fecha_pago: fechaPago,
        medio_pago: medio,
        referencia: referencia.trim() || null,
        registrar_movimiento_caja: registrarMov,
        sucursal_id:
          registrarMov && sucursalId !== "" ? Number(sucursalId) : null,
      });
    },
    onSuccess: () => {
      toast({
        title: "Pago registrado",
        description: "El compromiso fue actualizado.",
      });
      queryClient.invalidateQueries({ queryKey: ["compromisos"] });
      queryClient.invalidateQueries({ queryKey: ["compromiso"] });
      queryClient.invalidateQueries({ queryKey: ["compromisos-resumen"] });
      queryClient.invalidateQueries({ queryKey: ["compromisos-calendar"] });
      onOpenChange(false);
      onPaid?.();
    },
    onError: (err) => {
      const msg =
        (err as AxiosError<{ error?: string }>).response?.data?.error ??
        "No pudimos registrar el pago.";
      toast({
        variant: "destructive",
        title: "Error",
        description: msg,
      });
    },
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!monto || Number(monto) <= 0) {
      toast({
        variant: "destructive",
        title: "Monto inválido",
        description: "Ingresá un monto mayor a cero.",
      });
      return;
    }
    if (Number(monto) > pendiente + 0.01) {
      toast({
        variant: "destructive",
        title: "Monto excede pendiente",
        description: `El pendiente es ${formatMoney(pendiente)}.`,
      });
      return;
    }
    if (registrarMov && !sucursalId) {
      toast({
        variant: "destructive",
        title: "Sucursal requerida",
        description: "Para registrar movimiento de caja necesitás indicar la sucursal.",
      });
      return;
    }
    mutation.mutate();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Registrar pago</DialogTitle>
        </DialogHeader>

        {compromiso && (
          <form onSubmit={submit} className="flex flex-col gap-4">
            <div className="rounded-[10px] bg-muted/50 p-3">
              <p className="text-[12px] text-muted-foreground">
                {compromiso.descripcion}
              </p>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
                  Pendiente
                </span>
                <span className="text-[18px] font-semibold tabular-nums">
                  {formatMoney(pendiente)}
                </span>
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label className="text-[11px] uppercase tracking-wider text-muted-foreground">
                Monto a pagar
              </Label>
              <Input
                type="number"
                step="0.01"
                min="0.01"
                max={pendiente.toFixed(2)}
                value={monto}
                onChange={(e) => setMonto(e.target.value)}
                className="tabular-nums"
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <Label className="text-[11px] uppercase tracking-wider text-muted-foreground">
                  Fecha
                </Label>
                <Input
                  type="date"
                  value={fechaPago}
                  onChange={(e) => setFechaPago(e.target.value)}
                  required
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label className="text-[11px] uppercase tracking-wider text-muted-foreground">
                  Medio
                </Label>
                <select
                  value={medio}
                  onChange={(e) => setMedio(e.target.value)}
                  className="h-10 rounded-[8px] border border-border bg-background px-3 text-[13px] focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  {MEDIOS.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label className="text-[11px] uppercase tracking-wider text-muted-foreground">
                Referencia
              </Label>
              <Input
                value={referencia}
                onChange={(e) => setReferencia(e.target.value)}
                placeholder="Nro de transferencia, cheque, etc."
              />
            </div>

            <div className="rounded-[10px] border border-border p-3">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={registrarMov}
                  onChange={(e) => setRegistrarMov(e.target.checked)}
                  className="h-4 w-4 rounded border-border"
                />
                <span className="text-[13px] font-medium">
                  Registrar movimiento de caja
                </span>
              </label>
              <p className="mt-1 ml-6 text-[12px] text-muted-foreground">
                Crea un egreso en el ledger de la sucursal.
              </p>

              {registrarMov && (
                <div className="ml-6 mt-2 flex flex-col gap-1.5">
                  <Label className="text-[11px] uppercase tracking-wider text-muted-foreground">
                    Sucursal
                  </Label>
                  <select
                    value={sucursalId}
                    onChange={(e) =>
                      setSucursalId(
                        e.target.value === "" ? "" : Number(e.target.value),
                      )
                    }
                    className="h-10 rounded-[8px] border border-border bg-background px-3 text-[13px] focus:outline-none focus:ring-2 focus:ring-ring"
                    required
                  >
                    <option value="">Elegí una sucursal</option>
                    {sucursales.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.codigo} · {s.nombre}
                      </option>
                    ))}
                  </select>
                </div>
              )}
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
                Registrar pago
              </Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
