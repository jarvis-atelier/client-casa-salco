import { create } from "zustand";

/**
 * Evento de actualización de precio emitido por el backend en el namespace /prices.
 * Matcheja el payload que produce `app/services/price_sync.py::broadcast_price_update`.
 */
export interface PriceUpdateEvent {
  articulo: {
    id: number;
    codigo: string;
    descripcion: string;
  };
  sucursal: {
    id: number;
    codigo: string;
    nombre: string;
  };
  precio_anterior: string | null;
  precio_nuevo: string;
  motivo: string | null;
  cambiado_por: {
    id: number;
    email: string;
    nombre: string;
  } | null;
  timestamp: string; // ISO UTC
}

interface PriceFeedEntry extends PriceUpdateEvent {
  /** ID local para render keyed — timestamp + sucursal_id + articulo_id */
  _localId: string;
  /** ms epoch al momento de recibir, para ordenar y calcular tiempo relativo. */
  _receivedAt: number;
}

const FEED_CAP = 20;

interface PriceFeedState {
  events: PriceFeedEntry[];
  addEvent: (e: PriceUpdateEvent) => void;
  clear: () => void;
}

export const usePriceFeedStore = create<PriceFeedState>((set) => ({
  events: [],
  addEvent: (e) =>
    set((state) => {
      const receivedAt = Date.now();
      const _localId = `${e.timestamp}:${e.articulo.id}:${e.sucursal.id}:${receivedAt}`;
      const entry: PriceFeedEntry = { ...e, _localId, _receivedAt: receivedAt };
      return {
        events: [entry, ...state.events].slice(0, FEED_CAP),
      };
    }),
  clear: () => set({ events: [] }),
}));
