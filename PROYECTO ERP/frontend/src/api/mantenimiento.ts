/**
 * Wrappers CRUD de catálogos maestros: familias, rubros, subrubros, marcas, users.
 * Movemos los wrappers nuevos acá para no contaminar `catalogos.ts` (legacy).
 */
import { apiClient } from "./client";

// ---------------------------------------------------------------------------
// Familias
// ---------------------------------------------------------------------------

export interface Familia {
  id: number;
  codigo: string;
  nombre: string;
  orden: number;
  created_at?: string;
}

export interface FamiliaPayload {
  codigo: string;
  nombre: string;
  orden?: number;
}

export async function listFamilias(): Promise<Familia[]> {
  const { data } = await apiClient.get<Familia[]>("/familias");
  return data;
}

export async function createFamilia(p: FamiliaPayload): Promise<Familia> {
  const { data } = await apiClient.post<Familia>("/familias", p);
  return data;
}

export async function updateFamilia(
  id: number,
  p: Partial<FamiliaPayload>,
): Promise<Familia> {
  const { data } = await apiClient.patch<Familia>(`/familias/${id}`, p);
  return data;
}

export async function deleteFamilia(id: number): Promise<void> {
  await apiClient.delete(`/familias/${id}`);
}

// ---------------------------------------------------------------------------
// Rubros
// ---------------------------------------------------------------------------

export interface Rubro {
  id: number;
  familia_id: number;
  codigo: string;
  nombre: string;
  orden: number;
}

export interface RubroPayload {
  codigo: string;
  nombre: string;
  orden?: number;
}

export async function listRubrosByFamilia(familiaId: number): Promise<Rubro[]> {
  const { data } = await apiClient.get<Rubro[]>(
    `/familias/${familiaId}/rubros`,
  );
  return data;
}

export async function createRubro(
  familiaId: number,
  p: RubroPayload,
): Promise<Rubro> {
  const { data } = await apiClient.post<Rubro>(
    `/familias/${familiaId}/rubros`,
    p,
  );
  return data;
}

export async function updateRubro(
  id: number,
  p: Partial<RubroPayload>,
): Promise<Rubro> {
  const { data } = await apiClient.patch<Rubro>(`/rubros/${id}`, p);
  return data;
}

export async function deleteRubro(id: number): Promise<void> {
  await apiClient.delete(`/rubros/${id}`);
}

// ---------------------------------------------------------------------------
// Subrubros
// ---------------------------------------------------------------------------

export interface Subrubro {
  id: number;
  rubro_id: number;
  codigo: string;
  nombre: string;
  orden: number;
}

export interface SubrubroPayload {
  codigo: string;
  nombre: string;
  orden?: number;
}

export async function listSubrubrosByRubro(
  rubroId: number,
): Promise<Subrubro[]> {
  const { data } = await apiClient.get<Subrubro[]>(
    `/rubros/${rubroId}/subrubros`,
  );
  return data;
}

export async function createSubrubro(
  rubroId: number,
  p: SubrubroPayload,
): Promise<Subrubro> {
  const { data } = await apiClient.post<Subrubro>(
    `/rubros/${rubroId}/subrubros`,
    p,
  );
  return data;
}

export async function updateSubrubro(
  id: number,
  p: Partial<SubrubroPayload>,
): Promise<Subrubro> {
  const { data } = await apiClient.patch<Subrubro>(`/subrubros/${id}`, p);
  return data;
}

export async function deleteSubrubro(id: number): Promise<void> {
  await apiClient.delete(`/subrubros/${id}`);
}

// ---------------------------------------------------------------------------
// Marcas
// ---------------------------------------------------------------------------

export interface MarcaFull {
  id: number;
  nombre: string;
  activa: boolean;
  created_at?: string;
}

export interface MarcaPayload {
  nombre: string;
  activa?: boolean;
}

export async function listMarcasFull(): Promise<MarcaFull[]> {
  const { data } = await apiClient.get<MarcaFull[]>("/marcas");
  return data;
}

export async function createMarca(p: MarcaPayload): Promise<MarcaFull> {
  const { data } = await apiClient.post<MarcaFull>("/marcas", p);
  return data;
}

export async function updateMarca(
  id: number,
  p: Partial<MarcaPayload>,
): Promise<MarcaFull> {
  const { data } = await apiClient.patch<MarcaFull>(`/marcas/${id}`, p);
  return data;
}

export async function deleteMarca(id: number): Promise<void> {
  await apiClient.delete(`/marcas/${id}`);
}

// ---------------------------------------------------------------------------
// Usuarios
// ---------------------------------------------------------------------------

export type Rol =
  | "admin"
  | "supervisor"
  | "cajero"
  | "fiambrero"
  | "repositor"
  | "contador";

export interface UserFull {
  id: number;
  email: string;
  nombre: string;
  rol: Rol;
  sucursal_id: number | null;
  activo: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface UserCreatePayload {
  email: string;
  password: string;
  nombre: string;
  rol: Rol;
  sucursal_id?: number | null;
  activo?: boolean;
}

export interface UserUpdatePayload {
  nombre?: string;
  rol?: Rol;
  sucursal_id?: number | null;
  activo?: boolean;
  password?: string;
}

export async function listUsers(): Promise<UserFull[]> {
  const { data } = await apiClient.get<UserFull[]>("/auth/users");
  return data;
}

export async function createUser(p: UserCreatePayload): Promise<UserFull> {
  const { data } = await apiClient.post<UserFull>("/auth/register", p);
  return data;
}

export async function updateUser(
  id: number,
  p: UserUpdatePayload,
): Promise<UserFull> {
  const { data } = await apiClient.patch<UserFull>(`/auth/users/${id}`, p);
  return data;
}

export async function deactivateUser(id: number): Promise<void> {
  await apiClient.delete(`/auth/users/${id}`);
}
