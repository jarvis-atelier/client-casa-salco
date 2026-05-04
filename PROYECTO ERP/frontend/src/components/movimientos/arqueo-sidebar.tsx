import * as React from "react";
import { useMutation } from "@tanstack/react-query";
import { Lock, Printer } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { AlertDialog } from "@/components/ui/alert-dialog";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/store/auth";
import type { ArqueoTotales } from "@/api/movimientos";
import {
  formatMoney,
  medioPagoLabelHuman,
} from "@/components/facturas/format";
import type { MedioPago } from "@/lib/types";

interface ArqueoSidebarProps {
  totales: ArqueoTotales;
  fechaCaja: string;
  cajaNumero: number;
  sucursalNombre: string | null;
  onPrint: () => void;
}

const MEDIOS_ORDER: MedioPago[] = [
  "efectivo",
  "tarjeta_debito",
  "tarjeta_credito",
  "transferencia",
  "qr_mercadopago",
  "qr_modo",
  "cheque",
  "cuenta_corriente",
  "vale",
];

export function ArqueoSidebar({
  totales,
  fechaCaja,
  cajaNumero,
  sucursalNombre,
  onPrint,
}: ArqueoSidebarProps) {
  const { toast } = useToast();
  const authUser = useAuth((s) => s.user);
  const isAdmin = authUser?.rol === "admin";
  const [confirmCierre, setConfirmCierre] = React.useState(false);

  // Cierre de caja: el endpoint todavía no existe en backend (Fase 2.3+).
  // TODO: cuando exista POST /api/v1/cajas/cierre, conectar acá.
  const cierreMutation = useMutation({
    mutationFn: async () => {
      // Placeholder — no llamamos al backend.
      await new Promise((r) => setTimeout(r, 300));
      return { ok: false };
    },
    onSuccess: () => {
      toast({
        title: "Próximamente",
        description: "Cierre de caja: falta endpoint en backend (Fase 2.3+).",
      });
      setConfirmCierre(false);
    },
  });

  return (
    <>
      <Card
        data-print-target="arqueo"
        className="p-5 sticky top-6 flex flex-col gap-4"
      >
        <div className="flex flex-col gap-0.5">
          <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
            {sucursalNombre ?? "Todas las sucursales"} · Caja #{cajaNumero}
          </span>
          <h3 className="text-[16px] font-semibold tracking-tight">
            Arqueo del día
          </h3>
          <span className="text-[12px] text-muted-foreground">{fechaCaja}</span>
        </div>

        <Separator />

        <div className="flex flex-col gap-1.5">
          <span className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1">
            Por medio de pago
          </span>
          {MEDIOS_ORDER.map((medio) => {
            const monto = totales.porMedio[medio] ?? 0;
            if (Math.abs(monto) < 0.01) return null;
            return (
              <div
                key={medio}
                className="flex justify-between text-[13px]"
              >
                <span className="text-muted-foreground">
                  {medioPagoLabelHuman(medio)}
                </span>
                <span className="tabular-nums">{formatMoney(monto)}</span>
              </div>
            );
          })}
          {Object.values(totales.porMedio).every((v) => Math.abs(v) < 0.01) && (
            <p className="text-[12px] text-muted-foreground italic">
              Sin movimientos por medio de pago.
            </p>
          )}
        </div>

        <Separator />

        <div className="flex flex-col gap-1.5">
          <div className="flex justify-between text-[13px]">
            <span className="text-muted-foreground">Ingresos</span>
            <span className="tabular-nums text-emerald-600 dark:text-emerald-400 font-medium">
              {formatMoney(totales.ingresos)}
            </span>
          </div>
          <div className="flex justify-between text-[13px]">
            <span className="text-muted-foreground">Egresos</span>
            <span className="tabular-nums text-destructive font-medium">
              −{formatMoney(totales.egresos)}
            </span>
          </div>
        </div>

        <Separator />

        <div className="flex items-baseline justify-between">
          <span className="text-[13px] font-medium">Saldo neto</span>
          <span className="text-[24px] font-semibold tabular-nums tracking-tight">
            {formatMoney(totales.saldoNeto)}
          </span>
        </div>

        <div className="flex flex-col gap-2">
          <Button variant="outline" onClick={onPrint} className="w-full">
            <Printer className="h-4 w-4" strokeWidth={1.5} />
            Imprimir arqueo
          </Button>
          {isAdmin && (
            <Button
              variant="default"
              onClick={() => setConfirmCierre(true)}
              className="w-full"
            >
              <Lock className="h-4 w-4" strokeWidth={1.5} />
              Cerrar caja
            </Button>
          )}
        </div>

        <p className="text-[11px] text-muted-foreground/80">
          {totales.cantidadMovimientos} movimiento
          {totales.cantidadMovimientos === 1 ? "" : "s"} en el filtro.
        </p>
      </Card>

      <AlertDialog
        open={confirmCierre}
        onOpenChange={setConfirmCierre}
        title="¿Cerrar la caja del día?"
        description="Esta acción cerrará la caja, marcará el cierre en el ledger y bloqueará nuevos movimientos hasta la próxima apertura."
        confirmLabel={
          cierreMutation.isPending ? "Cerrando…" : "Cerrar caja"
        }
        onConfirm={() => cierreMutation.mutate()}
        loading={cierreMutation.isPending}
      />
    </>
  );
}
