import { apiClient } from "./client";
import type {
  Alerta,
  AlertaDetalle,
  AlertaResumen,
  AlertaRunResult,
  EstadoAlerta,
  Paginated,
  Severidad,
  TipoAlerta,
} from "@/lib/types";

export interface AlertasQuery {
  tipo?: TipoAlerta;
  severidad?: Severidad;
  estado?: EstadoAlerta;
  fecha_desde?: string;
  fecha_hasta?: string;
  incluir_cerradas?: boolean;
  page?: number;
  per_page?: number;
}

export interface AlertaPatchPayload {
  estado?: EstadoAlerta;
  nota_resolucion?: string;
}

export async function listAlertas(
  params: AlertasQuery = {},
): Promise<Paginated<Alerta>> {
  const { data } = await apiClient.get<Paginated<Alerta>>("/alertas", {
    params: {
      ...params,
      incluir_cerradas: params.incluir_cerradas ? 1 : undefined,
    },
  });
  return data;
}

export async function getAlerta(id: number): Promise<AlertaDetalle> {
  const { data } = await apiClient.get<AlertaDetalle>(`/alertas/${id}`);
  return data;
}

export async function getAlertasResumen(): Promise<AlertaResumen> {
  const { data } = await apiClient.get<AlertaResumen>("/alertas/resumen");
  return data;
}

export async function runAlertasDetection(
  ventanaDias = 90,
): Promise<AlertaRunResult> {
  const { data } = await apiClient.post<AlertaRunResult>(
    "/alertas/run",
    {},
    { params: { ventana_dias: ventanaDias } },
  );
  return data;
}

export async function patchAlerta(
  id: number,
  payload: AlertaPatchPayload,
): Promise<Alerta> {
  const { data } = await apiClient.patch<Alerta>(`/alertas/${id}`, payload);
  return data;
}

export async function deleteAlerta(id: number): Promise<void> {
  await apiClient.delete(`/alertas/${id}`);
}
