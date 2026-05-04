import * as React from "react";
import { Activity, ArrowRight } from "lucide-react";
import { Card } from "@/components/ui/card";
import { usePriceFeedStore, type PriceUpdateEvent } from "@/store/price-feed";

function formatPrecio(v: string | null | undefined): string {
  if (v === null || v === undefined) return "—";
  const n = parseFloat(v);
  if (!Number.isFinite(n)) return v;
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n);
}

function relativeFrom(receivedAt: number, now: number): string {
  const diffSec = Math.max(0, Math.floor((now - receivedAt) / 1000));
  if (diffSec < 5) return "hace un instante";
  if (diffSec < 60) return `hace ${diffSec}s`;
  const m = Math.floor(diffSec / 60);
  if (m < 60) return `hace ${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `hace ${h}h`;
  const d = Math.floor(h / 24);
  return `hace ${d}d`;
}

interface FeedRowProps {
  event: PriceUpdateEvent & { _localId: string; _receivedAt: number };
  now: number;
}

function FeedRow({ event, now }: FeedRowProps) {
  return (
    <div
      className="flex items-start gap-3 py-3 px-1 animate-in slide-in-from-top-2 fade-in-0 duration-[250ms] ease-apple"
      data-event-id={event._localId}
    >
      <span className="mt-1.5 relative flex h-2 w-2 shrink-0">
        <span className="absolute inline-flex h-full w-full rounded-full bg-emerald-400/60 opacity-70 animate-ping" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-medium text-[13px] text-foreground truncate">
            {event.articulo.descripcion}
          </span>
          <span className="rounded-md bg-muted/60 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
            {event.articulo.codigo}
          </span>
        </div>
        <div className="mt-1 flex items-center gap-2 text-[12px] text-muted-foreground">
          <span>{event.sucursal.nombre}</span>
          <span className="tabular-nums">
            {formatPrecio(event.precio_anterior)}
          </span>
          <ArrowRight className="h-3 w-3" strokeWidth={1.5} />
          <span className="tabular-nums font-medium text-foreground">
            {formatPrecio(event.precio_nuevo)}
          </span>
        </div>
        {event.cambiado_por && (
          <div className="mt-0.5 text-[11px] text-muted-foreground/80">
            {event.cambiado_por.nombre}
            {event.motivo ? ` · ${event.motivo}` : ""}
          </div>
        )}
      </div>
      <span className="shrink-0 text-[11px] text-muted-foreground tabular-nums">
        {relativeFrom(event._receivedAt, now)}
      </span>
    </div>
  );
}

export function PriceFeedPanel() {
  const events = usePriceFeedStore((s) => s.events);
  const [now, setNow] = React.useState(() => Date.now());

  // Re-render cada 10s para que los relativos ("hace 3s") se actualicen
  React.useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 10_000);
    return () => clearInterval(id);
  }, []);

  return (
    <Card className="p-6">
      <div className="flex items-start gap-4">
        <div className="rounded-[10px] bg-primary/10 p-2.5 shrink-0">
          <Activity
            className="h-[20px] w-[20px] text-primary"
            strokeWidth={1.5}
          />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <h3 className="text-[16px] font-semibold tracking-tight">
                Sync de precios · en vivo
              </h3>
              <span className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60 animate-ping" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
                </span>
                conectado
              </span>
            </div>
            {events.length > 0 && (
              <span className="text-[11px] text-muted-foreground tabular-nums">
                {events.length} evento{events.length === 1 ? "" : "s"}
              </span>
            )}
          </div>

          <div className="mt-4 flex flex-col divide-y divide-border">
            {events.length === 0 && (
              <div className="py-10 text-center">
                <p className="text-[13px] text-muted-foreground">
                  Los cambios de precio aparecerán acá en tiempo real.
                </p>
                <p className="mt-1 text-[12px] text-muted-foreground/70">
                  Abrí el sistema en otra pestaña o sucursal para verlo sincronizar.
                </p>
              </div>
            )}
            {events.map((e) => (
              <FeedRow key={e._localId} event={e} now={now} />
            ))}
          </div>
        </div>
      </div>
    </Card>
  );
}
