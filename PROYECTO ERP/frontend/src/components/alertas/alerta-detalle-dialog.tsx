import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Building2,
  Check,
  Clock,
  Receipt,
  Truck,
  User as UserIcon,
  X,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { useToast } from "@/hooks/use-toast";
import { getAlerta, patchAlerta } from "@/api/alertas";
import type { EstadoAlerta } from "@/lib/types";
import {
  estadoAlertaLabel,
  estadoBadgeVariant,
  formatAbsolute,
  relativeTime,
  severidadBadgeVariant,
  severidadLabel,
  tipoAlertaLabel,
} from "./format";

interface Props {
  alertaId: number | null;
  open: boolean;
  onOpenChange: (o: boolean) => void;
}

export function AlertaDetalleDialog({ alertaId, open, onOpenChange }: Props) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [nota, setNota] = React.useState("");

  const detalleQ = useQuery({
    enabled: open && alertaId !== null,
    queryKey: ["alerta", alertaId],
    queryFn: () => getAlerta(alertaId!),
  });

  React.useEffect(() => {
    if (detalleQ.data) {
      setNota(detalleQ.data.nota_resolucion ?? "");
    }
  }, [detalleQ.data]);

  const patchMut = useMutation({
    mutationFn: (estado: EstadoAlerta) =>
      patchAlerta(alertaId!, {
        estado,
        nota_resolucion: nota.trim() || undefined,
      }),
    onSuccess: (_, estado) => {
      toast({
        title: "Alerta actualizada",
        description: `Pasó a estado: ${estadoAlertaLabel(estado)}`,
      });
      qc.invalidateQueries({ queryKey: ["alertas"] });
      qc.invalidateQueries({ queryKey: ["alertas-resumen"] });
      qc.invalidateQueries({ queryKey: ["alerta", alertaId] });
      onOpenChange(false);
    },
    onError: () => {
      toast({
        title: "No se pudo actualizar",
        description: "Volvé a intentar en unos segundos.",
        variant: "destructive",
      });
    },
  });

  const a = detalleQ.data;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <AlertTriangle
              className="h-5 w-5 text-destructive"
              strokeWidth={1.5}
            />
            <DialogTitle>Detalle de alerta</DialogTitle>
          </div>
          <DialogDescription>
            Verificá el contexto, marcá la alerta como confirmada o descartala
            con una nota explicativa.
          </DialogDescription>
        </DialogHeader>

        {detalleQ.isLoading || !a ? (
          <div className="space-y-3">
            <Skeleton className="h-6 w-2/3" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        ) : (
          <div className="flex flex-col gap-5">
            {/* Cabecera */}
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2 flex-wrap">
                <Badge variant={severidadBadgeVariant(a.severidad)}>
                  {severidadLabel(a.severidad)}
                </Badge>
                <Badge variant="outline">{tipoAlertaLabel(a.tipo)}</Badge>
                <Badge variant={estadoBadgeVariant(a.estado)}>
                  {estadoAlertaLabel(a.estado)}
                </Badge>
                <span className="text-[12px] text-muted-foreground tabular-nums">
                  {relativeTime(a.detected_at)} ·{" "}
                  {formatAbsolute(a.detected_at)}
                </span>
              </div>
              <h3 className="text-[18px] font-semibold tracking-tight">
                {a.titulo}
              </h3>
              <p className="text-[13px] text-muted-foreground leading-relaxed">
                {a.descripcion}
              </p>
            </div>

            <Separator />

            {/* Entidades relacionadas */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {a.factura && (
                <RelatedCard
                  icon={Receipt}
                  label="Factura relacionada"
                  primary={`${String(a.factura.punto_venta).padStart(4, "0")}-${String(a.factura.numero).padStart(8, "0")}`}
                  secondary={`${a.factura.tipo} · $${a.factura.total} · ${a.factura.estado}`}
                />
              )}
              {a.user_relacionado && (
                <RelatedCard
                  icon={UserIcon}
                  label="Usuario relacionado"
                  primary={a.user_relacionado.nombre}
                  secondary={`${a.user_relacionado.email} · ${a.user_relacionado.rol ?? "—"}`}
                />
              )}
              {a.proveedor && (
                <RelatedCard
                  icon={Truck}
                  label="Proveedor"
                  primary={a.proveedor.razon_social}
                  secondary={`${a.proveedor.codigo}${a.proveedor.cuit ? ` · CUIT ${a.proveedor.cuit}` : ""}`}
                />
              )}
              {a.sucursal && (
                <RelatedCard
                  icon={Building2}
                  label="Sucursal"
                  primary={a.sucursal.nombre}
                  secondary={a.sucursal.codigo}
                />
              )}
            </div>

            {/* Contexto JSON */}
            {a.contexto && Object.keys(a.contexto).length > 0 && (
              <div className="flex flex-col gap-2">
                <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
                  Contexto
                </span>
                <pre className="rounded-[8px] border border-border bg-muted/30 p-3 text-[11px] leading-relaxed font-mono overflow-auto max-h-[200px]">
                  {JSON.stringify(a.contexto, null, 2)}
                </pre>
              </div>
            )}

            {a.resolved_at && (
              <div className="flex items-start gap-2 rounded-[8px] border border-border bg-muted/30 p-3">
                <Clock
                  className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0"
                  strokeWidth={1.5}
                />
                <div className="flex flex-col gap-1 text-[12px]">
                  <span className="text-muted-foreground">
                    Resuelta {relativeTime(a.resolved_at)} ·{" "}
                    {formatAbsolute(a.resolved_at)}
                  </span>
                  {a.nota_resolucion && (
                    <span className="text-foreground">
                      Nota: {a.nota_resolucion}
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Nota + acciones */}
            <Separator />
            <div className="flex flex-col gap-2">
              <label className="text-[11px] uppercase tracking-wider text-muted-foreground">
                Nota de resolución (opcional)
              </label>
              <textarea
                value={nota}
                onChange={(e) => setNota(e.target.value)}
                rows={3}
                placeholder="Por qué confirmás o descartás esta alerta..."
                className="w-full rounded-[8px] border border-border bg-background px-3 py-2 text-[13px] focus:outline-none focus:ring-2 focus:ring-ring resize-none"
              />
            </div>

            <div className="flex flex-wrap gap-2 justify-end">
              <Button
                variant="outline"
                size="sm"
                disabled={patchMut.isPending || a.estado === "en_revision"}
                onClick={() => patchMut.mutate("en_revision")}
              >
                <Clock strokeWidth={1.5} />
                En revisión
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={patchMut.isPending || a.estado === "descartada"}
                onClick={() => patchMut.mutate("descartada")}
              >
                <X strokeWidth={1.5} />
                Descartar
              </Button>
              <Button
                variant="destructive"
                size="sm"
                disabled={patchMut.isPending || a.estado === "confirmada"}
                onClick={() => patchMut.mutate("confirmada")}
              >
                <AlertTriangle strokeWidth={1.5} />
                Confirmar
              </Button>
              <Button
                size="sm"
                disabled={patchMut.isPending || a.estado === "resuelta"}
                onClick={() => patchMut.mutate("resuelta")}
              >
                <Check strokeWidth={1.5} />
                Resolver
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function RelatedCard({
  icon: Icon,
  label,
  primary,
  secondary,
}: {
  icon: typeof Receipt;
  label: string;
  primary: string;
  secondary?: string;
}) {
  return (
    <div className="flex items-start gap-3 rounded-[10px] border border-border p-3">
      <div className="rounded-full bg-muted/60 p-2 mt-0.5 shrink-0">
        <Icon
          className="h-[14px] w-[14px] text-muted-foreground"
          strokeWidth={1.5}
        />
      </div>
      <div className="flex flex-col gap-0.5 min-w-0">
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
        <span className="text-[13px] font-medium truncate">{primary}</span>
        {secondary && (
          <span className="text-[12px] text-muted-foreground truncate">
            {secondary}
          </span>
        )}
      </div>
    </div>
  );
}
