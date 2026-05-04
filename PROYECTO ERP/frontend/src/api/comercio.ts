import { apiClient } from "./client";

export interface ComercioConfig {
  id: number;
  razon_social: string;
  nombre_fantasia: string | null;
  cuit: string;
  condicion_iva: string;
  domicilio: string | null;
  localidad: string | null;
  provincia: string | null;
  cp: string | null;
  telefono: string | null;
  email: string | null;
  iibb: string | null;
  inicio_actividades: string | null;
  logo_path: string | null;
  pie_ticket: string | null;
  created_at: string;
  updated_at: string;
}

export type ComercioUpdatePayload = Partial<
  Omit<ComercioConfig, "id" | "created_at" | "updated_at">
>;

export async function getComercio(): Promise<ComercioConfig> {
  const { data } = await apiClient.get<ComercioConfig>("/comercio");
  return data;
}

export async function updateComercio(
  payload: ComercioUpdatePayload,
): Promise<ComercioConfig> {
  const { data } = await apiClient.patch<ComercioConfig>("/comercio", payload);
  return data;
}
