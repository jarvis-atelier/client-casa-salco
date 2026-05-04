import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Sparkles } from "lucide-react";
import { ajustarStock } from "@/api/stock";
import { getSugerenciaArticulo } from "@/api/reposicion";
import type { Articulo } from "@/lib/types";
import { parseDecimal } from "@/lib/types";
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
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

export interface StockAjusteTarget {
  articulo: Articulo;
  sucursalId: number;
  sucursalNombre: string;
  cantidadActual: number;
  /** Override de sucursal (puede ser null = hereda del articulo) */
  stockMinimo?: number | null;
  stockMaximo?: number | null;
  puntoReorden?: number | null;
  leadTimeDias?: number | null;
  /** Valores efectivos (override sucursal o default articulo) — sólo display */
  efectivoMin?: number | null;
  efectivoMax?: number | null;
  efectivoReorden?: number | null;
  efectivoLeadTime?: number | null;
}

interface Props {
  target: StockAjusteTarget | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type Tab = "cantidad" | "umbrales" | "leadtime" | "sugerencias";

const TAB_LABELS: { id: Tab; label: string }[] = [
  { id: "cantidad", label: "Cantidad" },
  { id: "umbrales", label: "Umbrales" },
  { id: "leadtime", label: "Lead time" },
  { id: "sugerencias", label: "Sugerencias" },
];

function emptyToNull(v: string): string | null {
  return v.trim() === "" ? null : v.trim();
}

export function StockAjusteDialog({ target, open, onOpenChange }: Props) {
  const { toast } = useToast();
  const qc = useQueryClient();

  const [tab, setTab] = React.useState<Tab>("cantidad");

  const [cantidadNueva, setCantidadNueva] = React.useState("");
  const [motivo, setMotivo] = React.useState("");
  const [stockMin, setStockMin] = React.useState("");
  const [stockMax, setStockMax] = React.useState("");
  const [reorden, setReorden] = React.useState("");
  const [leadTime, setLeadTime] = React.useState("");
  const [errors, setErrors] = React.useState<{
    cantidad?: string;
    motivo?: string;
    umbrales?: string;
  }>({});

  React.useEffect(() => {
    if (open && target) {
      setTab("cantidad");
      setCantidadNueva(String(target.cantidadActual));
      setMotivo("");
      // Si la sucursal tiene override, lo cargamos. Si no (heredando), dejamos vacío.
      setStockMin(
        target.stockMinimo !== null && target.stockMinimo !== undefined
          ? String(target.stockMinimo)
          : "",
      );
      setStockMax(
        target.stockMaximo !== null && target.stockMaximo !== undefined
          ? String(target.stockMaximo)
          : "",
      );
      setReorden(
        target.puntoReorden !== null && target.puntoReorden !== undefined
          ? String(target.puntoReorden)
          : "",
      );
      setLeadTime(
        target.leadTimeDias !== null && target.leadTimeDias !== undefined
          ? String(target.leadTimeDias)
          : "",
      );
      setErrors({});
    }
  }, [open, target]);

  // Sugerencias — sólo se carga cuando el tab está activo
  const sugQ = useQuery({
    queryKey: [
      "stock-sugerencia",
      target?.articulo.id,
      target?.sucursalId,
      open,
    ],
    queryFn: () =>
      getSugerenciaArticulo(target!.articulo.id, target!.sucursalId),
    enabled: Boolean(open && target && tab === "sugerencias"),
    staleTime: 60_000,
  });

  const mutation = useMutation({
    mutationFn: ajustarStock,
    onSuccess: () => {
      toast({
        title: "Stock ajustado",
        description: target
          ? `${target.articulo.codigo} · ${target.sucursalNombre}`
          : undefined,
      });
      qc.invalidateQueries({ queryKey: ["stock"] });
      qc.invalidateQueries({ queryKey: ["reposicion"] });
      onOpenChange(false);
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: { error?: string } } };
      toast({
        title: "No pudimos ajustar el stock",
        description:
          e?.response?.data?.error ?? "Probá de nuevo en un momento.",
        variant: "destructive",
      });
    },
  });

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!target) return;

    const errs: typeof errors = {};
    const n = parseDecimal(cantidadNueva);
    if (n === null || n < 0) errs.cantidad = "Cantidad inválida (>= 0)";
    if (!motivo.trim()) errs.motivo = "Requerido";
    else if (motivo.length > 200) errs.motivo = "Máximo 200 caracteres";

    // Validar umbrales: si están seteados, min <= reorden <= max
    const minVal = emptyToNull(stockMin);
    const maxVal = emptyToNull(stockMax);
    const reordenVal = emptyToNull(reorden);
    const minNum = minVal ? parseDecimal(minVal) : null;
    const maxNum = maxVal ? parseDecimal(maxVal) : null;
    const reordenNum = reordenVal ? parseDecimal(reordenVal) : null;
    if (minNum !== null && reordenNum !== null && minNum > reordenNum) {
      errs.umbrales = "Mínimo debe ser <= reorden";
    }
    if (
      reordenNum !== null &&
      maxNum !== null &&
      reordenNum > maxNum
    ) {
      errs.umbrales = "Reorden debe ser <= máximo";
    }

    setErrors(errs);
    if (Object.keys(errs).length > 0) {
      // Si hay error de umbrales, saltamos al tab umbrales
      if (errs.umbrales) setTab("umbrales");
      return;
    }

    // Calcular si "limpiar" override (vacío + antes había valor) o setear nuevo valor
    const buildField = (
      raw: string,
      currentOverride: number | null | undefined,
    ): { value?: string | null; unset?: boolean } => {
      const v = emptyToNull(raw);
      const hadOverride = currentOverride !== null && currentOverride !== undefined;
      if (v === null) {
        return hadOverride ? { unset: true } : {};
      }
      return { value: v };
    };
    const buildIntField = (
      raw: string,
      currentOverride: number | null | undefined,
    ): { value?: number | null; unset?: boolean } => {
      const v = emptyToNull(raw);
      const hadOverride = currentOverride !== null && currentOverride !== undefined;
      if (v === null) {
        return hadOverride ? { unset: true } : {};
      }
      const n = Number.parseInt(v, 10);
      if (!Number.isFinite(n)) return {};
      return { value: n };
    };

    const minF = buildField(stockMin, target.stockMinimo);
    const maxF = buildField(stockMax, target.stockMaximo);
    const reordenF = buildField(reorden, target.puntoReorden);
    const ltF = buildIntField(leadTime, target.leadTimeDias);

    mutation.mutate({
      articulo_id: target.articulo.id,
      sucursal_id: target.sucursalId,
      cantidad_nueva: cantidadNueva,
      motivo: motivo.trim(),
      ...(minF.value !== undefined ? { stock_minimo: minF.value } : {}),
      ...(minF.unset ? { unset_stock_minimo: true } : {}),
      ...(maxF.value !== undefined ? { stock_maximo: maxF.value } : {}),
      ...(maxF.unset ? { unset_stock_maximo: true } : {}),
      ...(reordenF.value !== undefined ? { punto_reorden: reordenF.value } : {}),
      ...(reordenF.unset ? { unset_punto_reorden: true } : {}),
      ...(ltF.value !== undefined ? { lead_time_dias: ltF.value } : {}),
      ...(ltF.unset ? { unset_lead_time_dias: true } : {}),
    });
  };

  const aplicarSugerencia = () => {
    if (!sugQ.data) return;
    const optimo = parseDecimal(sugQ.data.stock_optimo_sugerido);
    if (optimo !== null) {
      setStockMax(String(optimo));
      // reorden sugerido ~ 0.4 * optimo
      const reordenSug = Math.max(1, Math.round(optimo * 0.4));
      setReorden(String(reordenSug));
      // mínimo sugerido ~ 0.2 * optimo
      const minSug = Math.max(0, Math.round(optimo * 0.2));
      setStockMin(String(minSug));
      setTab("umbrales");
      toast({
        title: "Sugerencia aplicada",
        description: "Revisá los umbrales antes de confirmar.",
      });
    }
  };

  const loading = mutation.isPending;

  if (!target) return null;

  const delta =
    parseDecimal(cantidadNueva) !== null
      ? Number(cantidadNueva) - target.cantidadActual
      : 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[560px] p-0 overflow-hidden">
        <DialogHeader className="px-8 pt-8 pb-2">
          <DialogTitle className="text-[20px] font-semibold tracking-tight">
            Ajustar stock
          </DialogTitle>
          <DialogDescription className="text-[13px] text-muted-foreground">
            <span className="font-medium text-foreground">
              {target.articulo.descripcion}
            </span>
            <br />
            <span className="font-mono text-[12px]">
              {target.articulo.codigo}
            </span>{" "}
            · {target.sucursalNombre}
          </DialogDescription>
        </DialogHeader>

        {/* Tabs */}
        <div className="px-8 pt-2 border-b border-border">
          <div className="flex items-center gap-1">
            {TAB_LABELS.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                className={cn(
                  "h-9 px-3 text-[13px] font-medium border-b-2 -mb-px transition-colors",
                  tab === t.id
                    ? "border-primary text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground",
                )}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        <form onSubmit={onSubmit}>
          <div className="px-8 pt-5 pb-6 flex flex-col gap-5 min-h-[280px]">
            {tab === "cantidad" && (
              <>
                <div className="grid grid-cols-2 gap-4">
                  <div className="flex flex-col gap-2">
                    <Label>Cantidad actual</Label>
                    <Input
                      value={target.cantidadActual}
                      readOnly
                      disabled
                      className="tabular-nums"
                    />
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="stk-nueva">Cantidad nueva *</Label>
                    <Input
                      id="stk-nueva"
                      type="number"
                      step="0.01"
                      min="0"
                      value={cantidadNueva}
                      onChange={(e) => {
                        setCantidadNueva(e.target.value);
                        if (errors.cantidad)
                          setErrors((p) => ({ ...p, cantidad: undefined }));
                      }}
                      disabled={loading}
                      autoFocus
                      className="tabular-nums"
                    />
                    {errors.cantidad && (
                      <p className="text-[12px] text-destructive">
                        {errors.cantidad}
                      </p>
                    )}
                  </div>
                </div>

                {!Number.isNaN(delta) && delta !== 0 && (
                  <div
                    className={cn(
                      "rounded-[10px] border px-3 py-2 text-[12px] tabular-nums",
                      delta > 0
                        ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-700 dark:text-emerald-400"
                        : "border-destructive/30 bg-destructive/5 text-destructive",
                    )}
                  >
                    Cambio: {delta > 0 ? "+" : ""}
                    {delta}
                  </div>
                )}

                <div className="flex flex-col gap-2">
                  <Label htmlFor="stk-motivo">Motivo *</Label>
                  <textarea
                    id="stk-motivo"
                    value={motivo}
                    onChange={(e) => {
                      setMotivo(e.target.value);
                      if (errors.motivo)
                        setErrors((p) => ({ ...p, motivo: undefined }));
                    }}
                    disabled={loading}
                    rows={3}
                    maxLength={200}
                    placeholder="Ej: conteo físico, rotura, devolución a proveedor…"
                    className={cn(
                      "flex w-full rounded-lg border border-input bg-background px-3 py-2 text-[14px]",
                      "ring-offset-background transition-colors resize-none",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                      "disabled:cursor-not-allowed disabled:opacity-50",
                    )}
                  />
                  {errors.motivo && (
                    <p className="text-[12px] text-destructive">
                      {errors.motivo}
                    </p>
                  )}
                  <p className="text-[11px] text-muted-foreground tabular-nums text-right">
                    {motivo.length}/200
                  </p>
                </div>
              </>
            )}

            {tab === "umbrales" && (
              <>
                <p className="text-[12px] text-muted-foreground">
                  Dejá vacío para heredar del artículo. Estos overrides aplican
                  sólo a esta sucursal.
                </p>
                <div className="grid grid-cols-3 gap-4">
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="th-min">Mínimo</Label>
                    <Input
                      id="th-min"
                      type="number"
                      step="0.01"
                      min="0"
                      value={stockMin}
                      onChange={(e) => setStockMin(e.target.value)}
                      placeholder={
                        target.efectivoMin !== null && target.efectivoMin !== undefined
                          ? `${target.efectivoMin} (art)`
                          : "—"
                      }
                      disabled={loading}
                      className="tabular-nums"
                    />
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="th-reorden">Reorden</Label>
                    <Input
                      id="th-reorden"
                      type="number"
                      step="0.01"
                      min="0"
                      value={reorden}
                      onChange={(e) => setReorden(e.target.value)}
                      placeholder={
                        target.efectivoReorden !== null && target.efectivoReorden !== undefined
                          ? `${target.efectivoReorden} (art)`
                          : "—"
                      }
                      disabled={loading}
                      className="tabular-nums"
                    />
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="th-max">Máximo</Label>
                    <Input
                      id="th-max"
                      type="number"
                      step="0.01"
                      min="0"
                      value={stockMax}
                      onChange={(e) => setStockMax(e.target.value)}
                      placeholder={
                        target.efectivoMax !== null && target.efectivoMax !== undefined
                          ? `${target.efectivoMax} (art)`
                          : "—"
                      }
                      disabled={loading}
                      className="tabular-nums"
                    />
                  </div>
                </div>
                {errors.umbrales && (
                  <p className="text-[12px] text-destructive">
                    {errors.umbrales}
                  </p>
                )}
              </>
            )}

            {tab === "leadtime" && (
              <>
                <p className="text-[12px] text-muted-foreground">
                  Lead time del proveedor en días. Vacío hereda del artículo o
                  proveedor.
                </p>
                <div className="grid grid-cols-2 gap-4">
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="lt">Días</Label>
                    <Input
                      id="lt"
                      type="number"
                      min="0"
                      step="1"
                      value={leadTime}
                      onChange={(e) => setLeadTime(e.target.value)}
                      placeholder={
                        target.efectivoLeadTime !== null && target.efectivoLeadTime !== undefined
                          ? `${target.efectivoLeadTime} (heredado)`
                          : "—"
                      }
                      disabled={loading}
                      className="tabular-nums"
                    />
                  </div>
                </div>
              </>
            )}

            {tab === "sugerencias" && (
              <>
                {sugQ.isLoading && (
                  <div className="flex items-center justify-center py-8">
                    <Loader2
                      className="animate-spin text-muted-foreground"
                      strokeWidth={1.5}
                    />
                  </div>
                )}
                {sugQ.data && (
                  <div className="flex flex-col gap-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="flex flex-col gap-1 rounded-[10px] border border-border bg-muted/30 px-3 py-2.5">
                        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                          Velocidad de venta
                        </span>
                        <span className="text-[16px] font-semibold tabular-nums">
                          {sugQ.data.velocidad.velocidad_promedio_diaria}/día
                        </span>
                        <span className="text-[11px] text-muted-foreground tabular-nums">
                          {sugQ.data.velocidad.dias_con_venta} días con venta · {sugQ.data.velocidad.dias} días
                        </span>
                      </div>
                      <div className="flex flex-col gap-1 rounded-[10px] border border-border bg-muted/30 px-3 py-2.5">
                        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                          Lead time
                        </span>
                        <span className="text-[16px] font-semibold tabular-nums">
                          {sugQ.data.lead_time_dias} días
                        </span>
                      </div>
                    </div>
                    <div className="rounded-[10px] border border-primary/20 bg-primary/5 px-4 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex flex-col gap-0.5">
                          <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
                            Stock óptimo sugerido
                          </span>
                          <span className="text-[20px] font-semibold tabular-nums text-primary">
                            {sugQ.data.stock_optimo_sugerido}
                          </span>
                          <span className="text-[11px] text-muted-foreground">
                            Velocidad × lead time × 1.5
                          </span>
                        </div>
                        <Button
                          type="button"
                          variant="outline"
                          onClick={aplicarSugerencia}
                          disabled={loading}
                        >
                          <Sparkles strokeWidth={1.5} />
                          Aplicar
                        </Button>
                      </div>
                    </div>
                  </div>
                )}
                {sugQ.isError && (
                  <p className="text-[12px] text-destructive">
                    No pudimos calcular sugerencias.
                  </p>
                )}
              </>
            )}
          </div>

          <DialogFooter className="px-8 py-5 border-t border-border bg-muted/30">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={loading}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={loading}>
              {loading && (
                <Loader2 className="animate-spin" strokeWidth={1.5} />
              )}
              {loading ? "Ajustando…" : "Confirmar ajuste"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
