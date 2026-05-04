import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { connectPricesSocket, disconnectPricesSocket } from "@/lib/socket";
import { useAuth } from "@/store/auth";
import { usePriceFeedStore, type PriceUpdateEvent } from "@/store/price-feed";
import { useToast } from "@/hooks/use-toast";

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

/**
 * Instala el listener de `price:updated` una sola vez por layout protegido.
 *
 * - Conecta al socket con el JWT actual del authStore.
 * - Al recibir evento:
 *     1. Pushea al feed (zustand).
 *     2. Invalida queries TanStack (articulos, precios por artículo).
 *     3. Muestra toast — EXCEPTO si el emisor es el mismo usuario (eco).
 * - Al desmontar / logout: desconecta y limpia listener.
 */
export function usePriceSyncListener(): void {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const accessToken = useAuth((s) => s.accessToken);
  const userId = useAuth((s) => s.user?.id ?? null);
  const addEvent = usePriceFeedStore((s) => s.addEvent);

  React.useEffect(() => {
    if (!accessToken) {
      disconnectPricesSocket();
      return;
    }
    const socket = connectPricesSocket();
    if (!socket) return;

    const onPriceUpdated = (payload: PriceUpdateEvent) => {
      // 1. feed
      addEvent(payload);

      // 2. invalidate queries afectadas
      queryClient.invalidateQueries({ queryKey: ["articulos"] });
      queryClient.invalidateQueries({
        queryKey: ["precios", payload.articulo.id],
      });

      // 3. toast — ocultar si el emisor soy yo (evita eco)
      const emitidoPorMi =
        userId !== null && payload.cambiado_por?.id === userId;
      if (emitidoPorMi) return;

      const anterior = formatPrecio(payload.precio_anterior);
      const nuevo = formatPrecio(payload.precio_nuevo);
      toast({
        title: "Precio actualizado",
        description: `${payload.articulo.descripcion} · ${payload.sucursal.nombre}: ${anterior} → ${nuevo}`,
      });
    };

    socket.on("price:updated", onPriceUpdated);

    // Listener de facturación cross-sucursal (Fase 2.1+).
    interface FacturaEmitidaEvent {
      id: number;
      sucursal: { id: number; codigo: string; nombre: string };
      tipo: string;
      punto_venta: number;
      numero: number;
      total: string;
      fecha: string;
    }

    const onFacturaEmitida = (payload: FacturaEmitidaEvent) => {
      queryClient.invalidateQueries({ queryKey: ["facturas"] });
      queryClient.invalidateQueries({ queryKey: ["movimientos"] });
      queryClient.invalidateQueries({ queryKey: ["stock"] });

      // No mostramos toast si la emitimos nosotros (echo check vía sucursal_id del user).
      // Por ahora siempre mostramos para dashboards externos — si molesta, filtrar.
      const totalNum = parseFloat(payload.total);
      toast({
        title: `Venta en ${payload.sucursal.nombre}`,
        description: `#${payload.numero} · ${formatPrecio(totalNum.toString())}`,
      });
    };
    socket.on("factura:emitida", onFacturaEmitida);

    return () => {
      socket.off("price:updated", onPriceUpdated);
      socket.off("factura:emitida", onFacturaEmitida);
    };
  }, [accessToken, userId, queryClient, toast, addEvent]);
}
