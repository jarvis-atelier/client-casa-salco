import { apiClient } from "./client";
import type { Sucursal } from "@/lib/types";

export interface PrecioListadoItem {
  sucursal: Pick<Sucursal, "id" | "codigo" | "nombre">;
  precio: string;
  vigente_desde: string;
}

export interface PrecioCambio {
  sucursal_id: number;
  precio: string;
}

export interface PrecioUpdateRequest {
  articulo_id: number;
  motivo?: string;
  cambios?: PrecioCambio[];
  precio?: string;
  aplicar_a_todas?: boolean;
}

export interface PrecioUpdateResponseItem {
  sucursal_id: number;
  precio_anterior: string | null;
  precio_nuevo: string;
}

export interface PrecioUpdateResponse {
  articulo_id: number;
  actualizados: number;
  items: PrecioUpdateResponseItem[];
}

export async function listPreciosByArticulo(
  articuloId: number,
): Promise<PrecioListadoItem[]> {
  const { data } = await apiClient.get<PrecioListadoItem[]>("/precios", {
    params: { articulo_id: articuloId },
  });
  return data;
}

export async function actualizarPrecios(
  payload: PrecioUpdateRequest,
): Promise<PrecioUpdateResponse> {
  const { data } = await apiClient.post<PrecioUpdateResponse>(
    "/precios/actualizar",
    payload,
  );
  return data;
}
