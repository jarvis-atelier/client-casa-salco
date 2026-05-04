import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AxiosError } from "axios";
import {
  Calendar,
  CheckCircle2,
  CreditCard,
  Trash2,
  XCircle,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertDialog } from "@/components/ui/alert-dialog";
import {
  deleteCompromiso,
  getCompromiso,
  patchCompromiso,
} from "@/api/calendario-pagos";
import { useToast } from "@/hooks/use-toast";
import type { CompromisoPago } from "@/lib/types";
import { parseDecimal } from "@/lib/types";
import { formatMoney } from "@/components/facturas/format";
import {
  diasHasta,
  diasLabel,
  estadoCompromisoBadgeVariant,
  estadoCompromisoLabel,
  formatFechaCompacta,
  formatFechaLarga,
  tipoCompromisoBadgeVariant,
  tipoCompromisoLabel,
} from "./format";
import { PagarCompromisoDialog } from "./pagar-compromiso-dialog";

interface CompromisoDetailDialogProps {
  compromisoId: number | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CompromisoDetailDialog({
  compromisoId,
  open,
  onOpenChange,
}: CompromisoDetailDialogProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [pagarOpen, setPagarOpen] = React.useState(false);
  const [confirmDelete, setConfirmDelete] = React.useState(false);
  const [confirmCancel, setConfirmCancel] = React.useState(false);

  const { data: compromiso, isLoading } = useQuery({
    queryKey: ["compromiso", compromisoId],
    queryFn: () => getCompromiso(compromisoId as number),
    enabled: open && compromisoId !== null,
  });

  const cancelMutation = useMutation({
    mutationFn: () =>
      patchCompromiso(compromisoId as number, { estado: "cancelado" }),
    onSuccess: () => {
      toast({ title: "Compromiso cancelado" });
      queryClient.invalidateQueries({ queryKey: ["compromisos"] });
      queryClient.invalidateQueries({ queryKey: ["compromiso"] });
      queryClient.invalidateQueries({ queryKey: ["compromisos-resumen"] });
      onOpenChange(false);
    },
    onError: (err) => {
      const msg =
        (err as AxiosError<{ error?: string }>).response?.data?.error ??
        "No pudimos cancelar el compromiso.";
      toast({ variant: "destructive", title: "Error", description: msg });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteCompromiso(compromisoId as number),
    onSuccess: () => {
      toast({ title: "Compromiso eliminado" });
      queryClient.invalidateQueries({ queryKey: ["compromisos"] });
      queryClient.invalidateQueries({ queryKey: ["compromisos-resumen"] });
      onOpenChange(false);
    },
    onError: (err) => {
      const msg =
        (err as AxiosError<{ error?: string }>).response?.data?.error ??
        "No pudimos eliminar el compromiso.";
      toast({ variant: "destructive", title: "Error", description: msg });
    },
  });

  const compromisoBase: CompromisoPago | null = compromiso
    ? (compromiso as CompromisoPago)
    : null;
  const pendiente = compromiso
    ? Number(parseDecimal(compromiso.monto_total) ?? 0) -
      Number(parseDecimal(compromiso.monto_pagado) ?? 0)
    : 0;
  const dias = compromiso ? diasHasta(compromiso.fecha_vencimiento) : 0;

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Compromiso de pago</DialogTitle>
          </DialogHeader>

          {isLoading && (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-6 w-3/4" />
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-32 w-full" />
            </div>
          )}

          {compromiso && !isLoading && (
            <div className="flex flex-col gap-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex flex-col gap-1.5">
                  <h3 className="text-[18px] font-semibold tracking-tight">
                    {compromiso.descripcion}
                  </h3>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={tipoCompromisoBadgeVariant(compromiso.tipo)}>
                      {tipoCompromisoLabel(compromiso.tipo)}
                    </Badge>
                    <Badge variant={estadoCompromisoBadgeVariant(compromiso.estado)}>
                      {estadoCompromisoLabel(compromiso.estado)}
                    </Badge>
                    {compromiso.proveedor_nombre && (
                      <span className="text-[12px] text-muted-foreground">
                        {compromiso.proveedor_nombre}
                      </span>
                    )}
                    {compromiso.tarjeta_nombre && (
                      <span className="text-[12px] text-muted-foreground inline-flex items-center gap-1">
                        <CreditCard className="h-3 w-3" strokeWidth={1.5} />
                        {compromiso.tarjeta_nombre}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Stat
                  label="Total"
                  value={formatMoney(compromiso.monto_total)}
                />
                <Stat
                  label="Pagado"
                  value={formatMoney(compromiso.monto_pagado)}
                  muted
                />
                <Stat
                  label="Pendiente"
                  value={formatMoney(pendiente)}
                  highlight={pendiente > 0}
                />
                <Stat
                  label="Vence"
                  value={formatFechaCompacta(compromiso.fecha_vencimiento)}
                  hint={diasLabel(dias)}
                  hintTone={
                    dias < 0
                      ? "destructive"
                      : dias <= 3
                        ? "warning"
                        : "muted"
                  }
                />
              </div>

              <Separator />

              <div className="flex flex-col gap-2">
                <h4 className="text-[12px] uppercase tracking-wider text-muted-foreground">
                  Pagos registrados
                </h4>
                {compromiso.pagos.length === 0 ? (
                  <p className="text-[13px] text-muted-foreground py-4 text-center">
                    Aún no se registraron pagos.
                  </p>
                ) : (
                  <ul className="flex flex-col gap-1.5">
                    {compromiso.pagos.map((p) => (
                      <li
                        key={p.id}
                        className="flex items-center justify-between gap-3 rounded-[8px] border border-border bg-card/50 px-3 py-2 text-[13px]"
                      >
                        <div className="flex items-center gap-2 text-muted-foreground">
                          <Calendar className="h-3.5 w-3.5" strokeWidth={1.5} />
                          <span>{formatFechaCompacta(p.fecha_pago)}</span>
                          <span className="capitalize">{p.medio_pago.replaceAll("_", " ")}</span>
                          {p.referencia && (
                            <span className="text-[12px] text-muted-foreground/70">
                              · {p.referencia}
                            </span>
                          )}
                        </div>
                        <span className="tabular-nums font-medium">
                          {formatMoney(p.monto)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {compromiso.fecha_emision && (
                <p className="text-[12px] text-muted-foreground">
                  Emitido: {formatFechaLarga(compromiso.fecha_emision)}
                </p>
              )}
              {compromiso.nota && (
                <p className="text-[13px] rounded-[8px] bg-muted/40 px-3 py-2">
                  {compromiso.nota}
                </p>
              )}

              <div className="flex flex-wrap items-center justify-end gap-2 pt-2">
                {compromiso.estado === "pendiente" && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setConfirmDelete(true)}
                    className="text-muted-foreground"
                  >
                    <Trash2 className="mr-1 h-4 w-4" strokeWidth={1.5} />
                    Eliminar
                  </Button>
                )}
                {(compromiso.estado === "pendiente" ||
                  compromiso.estado === "parcial" ||
                  compromiso.estado === "vencido") && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setConfirmCancel(true)}
                  >
                    <XCircle className="mr-1 h-4 w-4" strokeWidth={1.5} />
                    Cancelar
                  </Button>
                )}
                {(compromiso.estado === "pendiente" ||
                  compromiso.estado === "parcial" ||
                  compromiso.estado === "vencido") && (
                  <Button onClick={() => setPagarOpen(true)} size="sm">
                    <CheckCircle2 className="mr-1 h-4 w-4" strokeWidth={1.5} />
                    Pagar
                  </Button>
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <PagarCompromisoDialog
        compromiso={compromisoBase}
        open={pagarOpen}
        onOpenChange={setPagarOpen}
        onPaid={() => onOpenChange(false)}
      />

      <AlertDialog
        open={confirmCancel}
        onOpenChange={setConfirmCancel}
        title="Cancelar compromiso"
        description="El compromiso quedará en estado cancelado y no aparecerá en alertas. Esta acción se puede revertir editando el estado."
        confirmLabel="Sí, cancelar"
        onConfirm={() => {
          cancelMutation.mutate();
          setConfirmCancel(false);
        }}
        loading={cancelMutation.isPending}
      />

      <AlertDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title="Eliminar compromiso"
        description="Esta acción no se puede deshacer. Solo se puede eliminar si el compromiso aún no tiene pagos."
        confirmLabel="Sí, eliminar"
        destructive
        onConfirm={() => {
          deleteMutation.mutate();
          setConfirmDelete(false);
        }}
        loading={deleteMutation.isPending}
      />
    </>
  );
}

function Stat({
  label,
  value,
  hint,
  hintTone,
  muted,
  highlight,
}: {
  label: string;
  value: string;
  hint?: string;
  hintTone?: "muted" | "warning" | "destructive";
  muted?: boolean;
  highlight?: boolean;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <span
        className={
          "text-[16px] font-semibold tabular-nums " +
          (muted ? "text-muted-foreground " : "") +
          (highlight ? "text-foreground" : "")
        }
      >
        {value}
      </span>
      {hint && (
        <span
          className={
            "text-[11px] " +
            (hintTone === "destructive"
              ? "text-rose-500"
              : hintTone === "warning"
                ? "text-amber-500"
                : "text-muted-foreground")
          }
        >
          {hint}
        </span>
      )}
    </div>
  );
}
