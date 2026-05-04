import { apiClient } from "./client";
import type { Area, Sucursal } from "@/lib/types";

export async function listSucursales(): Promise<Sucursal[]> {
  const { data } = await apiClient.get<Sucursal[] | { items: Sucursal[] }>(
    "/sucursales",
  );
  return Array.isArray(data) ? data : data.items ?? [];
}

export async function listAreasBySucursal(sucursalId: number): Promise<Area[]> {
  const { data } = await apiClient.get<Area[] | { items: Area[] }>(
    `/sucursales/${sucursalId}/areas`,
  );
  return Array.isArray(data) ? data : data.items ?? [];
}

// ---------------------------------------------------------------------------
// CRUD wrappers
// ---------------------------------------------------------------------------

export interface SucursalPayload {
  codigo: string;
  nombre: string;
  direccion?: string | null;
  ciudad?: string | null;
  provincia?: string | null;
  telefono?: string | null;
  lat?: number | string | null;
  lng?: number | string | null;
  activa?: boolean;
}

export async function createSucursal(p: SucursalPayload): Promise<Sucursal> {
  const { data } = await apiClient.post<Sucursal>("/sucursales", p);
  return data;
}

export async function updateSucursal(
  id: number,
  p: Partial<SucursalPayload>,
): Promise<Sucursal> {
  const { data } = await apiClient.patch<Sucursal>(`/sucursales/${id}`, p);
  return data;
}

export async function deactivateSucursal(id: number): Promise<void> {
  await apiClient.delete(`/sucursales/${id}`);
}

export interface AreaPayload {
  codigo: string;
  nombre: string;
  descripcion?: string | null;
  activa?: boolean;
  orden?: number;
}

export async function createArea(
  sucursalId: number,
  p: AreaPayload,
): Promise<Area> {
  const { data } = await apiClient.post<Area>(
    `/sucursales/${sucursalId}/areas`,
    p,
  );
  return data;
}

export async function updateArea(
  areaId: number,
  p: Partial<AreaPayload>,
): Promise<Area> {
  const { data } = await apiClient.patch<Area>(`/areas/${areaId}`, p);
  return data;
}

export async function deleteArea(areaId: number): Promise<void> {
  await apiClient.delete(`/areas/${areaId}`);
}
