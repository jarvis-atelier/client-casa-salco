import { apiClient } from "./client";
import type { ProveedorFull } from "@/lib/types";

export interface ProveedorPayload {
  codigo: string;
  razon_social: string;
  cuit?: string | null;
  telefono?: string | null;
  email?: string | null;
  direccion?: string | null;
  activo?: boolean;
}

export type ProveedorUpdatePayload = Partial<ProveedorPayload>;

export async function listProveedoresFull(): Promise<ProveedorFull[]> {
  const { data } = await apiClient.get<ProveedorFull[]>("/proveedores");
  return data;
}

export async function getProveedor(id: number): Promise<ProveedorFull> {
  const { data } = await apiClient.get<ProveedorFull>(`/proveedores/${id}`);
  return data;
}

export async function createProveedor(
  payload: ProveedorPayload,
): Promise<ProveedorFull> {
  const { data } = await apiClient.post<ProveedorFull>("/proveedores", payload);
  return data;
}

export async function updateProveedor(
  id: number,
  payload: ProveedorUpdatePayload,
): Promise<ProveedorFull> {
  const { data } = await apiClient.patch<ProveedorFull>(
    `/proveedores/${id}`,
    payload,
  );
  return data;
}

export async function deactivateProveedor(id: number): Promise<void> {
  await apiClient.delete(`/proveedores/${id}`);
}
