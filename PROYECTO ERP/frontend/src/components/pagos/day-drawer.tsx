import { useQuery } from "@tanstack/react-query";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { listCompromisos } from "@/api/calendario-pagos";
import type { CompromisoPago } from "@/lib/types";
import { parseDecimal } from "@/lib/types";
import { formatMoney } from "@/components/facturas/format";
import {
  diasHasta,
  diasLabel,
  estadoCompromisoBadgeVariant,
  estadoCompromisoLabel,
  formatFechaLarga,
  tipoCompromisoBadgeVariant,
  tipoCompromisoLabel,
} from "./format";

interface DayDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  fecha: string | null;
  ids: number[];
  onSelectCompromiso: (id: number) => void;
}

export function DayDrawer({
  open,
  onOpenChange,
  fecha,
  ids,
  onSelectCompromiso,
}: DayDrawerProps) {
  const { data, isLoading } = useQuery({
    queryKey: ["compromisos", "day", fecha],
    queryFn: () =>
      listCompromisos({
        fecha_desde: fecha as string,
        fecha_hasta: fecha as string,
        per_page: 100,
      }),
    enabled: open && fecha !== null,
  });

  const items: CompromisoPago[] = (data?.items ?? []).filter((c) =>
    ids.includes(c.id),
  );

  const total = items.reduce((acc, c) => {
    const pendiente =
      Number(parseDecimal(c.monto_total) ?? 0) -
      Number(parseDecimal(c.monto_pagado) ?? 0);
    return acc + (pendiente > 0 ? pendiente : 0);
  }, 0);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-[420px] sm:w-[480px]">
        <SheetHeader className="px-5 pt-5">
          <SheetTitle className="text-[18px]">
            {fecha ? formatFechaLarga(fecha) : "Día"}
          </SheetTitle>
        </SheetHeader>

        <div className="px-5 pb-5 pt-4">
          <div className="flex items-baseline justify-between gap-3 rounded-[10px] bg-muted/40 px-3 py-2.5 mb-4">
            <span className="text-[12px] uppercase tracking-wider text-muted-foreground">
              Total pendiente
            </span>
            <span className="text-[16px] font-semibold tabular-nums">
              {formatMoney(total)}
            </span>
          </div>

          {isLoading && (
            <div className="flex flex-col gap-2">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          )}

          {!isLoading && items.length === 0 && (
            <p className="py-8 text-center text-[13px] text-muted-foreground">
              No hay compromisos en este día.
            </p>
          )}

          <ul className="flex flex-col gap-2">
            {items.map((c) => (
              <CompromisoCard
                key={c.id}
                compromiso={c}
                onClick={() => onSelectCompromiso(c.id)}
              />
            ))}
          </ul>
        </div>
      </SheetContent>
    </Sheet>
  );
}

function CompromisoCard({
  compromiso,
  onClick,
}: {
  compromiso: CompromisoPago;
  onClick: () => void;
}) {
  const dias = diasHasta(compromiso.fecha_vencimiento);
  const pendiente =
    Number(parseDecimal(compromiso.monto_total) ?? 0) -
    Number(parseDecimal(compromiso.monto_pagado) ?? 0);

  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        className="w-full text-left rounded-[10px] border border-border bg-card px-3 py-3 hover:bg-muted/30 transition-colors duration-200 ease-apple"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex flex-col gap-1.5 min-w-0">
            <p className="text-[13px] font-medium leading-tight truncate">
              {compromiso.descripcion}
            </p>
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge variant={tipoCompromisoBadgeVariant(compromiso.tipo)}>
                {tipoCompromisoLabel(compromiso.tipo)}
              </Badge>
              <Badge variant={estadoCompromisoBadgeVariant(compromiso.estado)}>
                {estadoCompromisoLabel(compromiso.estado)}
              </Badge>
              <span
                className={
                  "text-[11px] " +
                  (dias < 0
                    ? "text-rose-500"
                    : dias <= 3
                      ? "text-amber-500"
                      : "text-muted-foreground")
                }
              >
                {diasLabel(dias)}
              </span>
            </div>
          </div>
          <span className="text-[14px] tabular-nums font-semibold">
            {formatMoney(pendiente)}
          </span>
        </div>
      </button>
    </li>
  );
}
