import { apiClient } from "./client";
import type { StockAjustePayload, StockSucursalRow } from "@/lib/types";

export async function stockByArticulo(
  articuloId: number,
): Promise<StockSucursalRow[]> {
  const { data } = await apiClient.get<StockSucursalRow[]>("/stock", {
    params: { articulo_id: articuloId },
  });
  return data;
}

export async function stockBySucursal(
  sucursalId: number,
): Promise<StockSucursalRow[]> {
  const { data } = await apiClient.get<StockSucursalRow[]>("/stock", {
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
