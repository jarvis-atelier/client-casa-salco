import { apiClient } from "./client";
import type {
  EstadoReposicion,
  Paginated,
  StockAjustePayload,
  StockResumen,
  StockSucursalRow,
} from "@/lib/types";

export async function stockByArticulo(
  articuloId: number,
): Promise<StockSucursalRow[]> {
  const { data } = await apiClient.get<StockSucursalRow[]>("/stock", {
    params: { articulo_id: articuloId },
  });
  return data;
}

export interface StockBySucursalParams {
  sucursalId: number;
  page?: number;
  perPage?: number;
  q?: string;
  estado?: EstadoReposicion;
}

export async function stockBySucursal(
  params: StockBySucursalParams,
): Promise<Paginated<StockSucursalRow>> {
  const { data } = await apiClient.get<Paginated<StockSucursalRow>>("/stock", {
    params: {
      sucursal_id: params.sucursalId,
      page: params.page ?? 1,
      per_page: params.perPage ?? 50,
      ...(params.q ? { q: params.q } : {}),
      ...(params.estado ? { estado: params.estado } : {}),
    },
  });
  return data;
}

export async function stockResumen(sucursalId: number): Promise<StockResumen> {
  const { data } = await apiClient.get<StockResumen>("/stock/resumen", {
    params: { sucursal_id: sucursalId },
  });
  return data;
}

export async function ajustarStock(
  payload: StockAjustePayload,
): Promise<StockSucursalRow> {
  const { data } = await apiClient.post<StockSucursalRow>(
    "/stock/ajuste",
    payload,
  );
  return data;
}
