import { apiClient } from "./client";
import type {
  OrdenCompraPayload,
  OrdenCompraResult,
  RecalcularResult,
  ReposicionSugerencia,
  SugerenciaArticulo,
} from "@/lib/types";

export async function getReposicion(
  sucursalId?: number,
): Promise<ReposicionSugerencia> {
  const { data } = await apiClient.get<ReposicionSugerencia>("/reposicion", {
    params: sucursalId ? { sucursal_id: sucursalId } : {},
  });
  return data;
}

export async function crearOrdenCompra(
  payload: OrdenCompraPayload,
): Promise<OrdenCompraResult> {
  const { data } = await apiClient.post<OrdenCompraResult>(
    "/reposicion/orden-compra",
    payload,
  );
  return data;
}

export async function recalcularReposicion(
  sucursalId?: number,
): Promise<RecalcularResult> {
  const { data } = await apiClient.post<RecalcularResult>(
    "/reposicion/recalcular",
    null,
    {
      params: sucursalId ? { sucursal_id: sucursalId } : {},
    },
  );
  return data;
}

export async function getSugerenciaArticulo(
  articuloId: number,
  sucursalId: number,
): Promise<SugerenciaArticulo> {
  const { data } = await apiClient.get<SugerenciaArticulo>(
    `/stock/${articuloId}/sugerencia/${sucursalId}`,
  );
  return data;
}

export function downloadListaReposicionXlsx(sucursalId?: number): string {
  const base = "/api/v1/reports/lista-reposicion.xlsx";
  return sucursalId ? `${base}?sucursal_id=${sucursalId}` : base;
}
