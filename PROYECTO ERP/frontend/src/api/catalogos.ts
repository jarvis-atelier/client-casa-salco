import { apiClient } from "./client";
import type { Familia, Marca, Paginated, Proveedor, Rubro } from "@/lib/types";

type AnyList<T> = T[] | Paginated<T> | { items: T[] };

function extractItems<T>(data: AnyList<T>): T[] {
  if (Array.isArray(data)) return data;
  if ("items" in data && Array.isArray(data.items)) return data.items;
  return [];
}

export async function listFamilias(): Promise<Familia[]> {
  const { data } = await apiClient.get<AnyList<Familia>>("/familias");
  return extractItems(data);
}

export async function listRubros(): Promise<Rubro[]> {
  const { data } = await apiClient.get<AnyList<Rubro>>("/rubros");
  return extractItems(data);
}

export async function listMarcas(): Promise<Marca[]> {
  const { data } = await apiClient.get<AnyList<Marca>>("/marcas");
  return extractItems(data);
}

export async function listProveedores(): Promise<Proveedor[]> {
  const { data } = await apiClient.get<AnyList<Proveedor>>("/proveedores");
  return extractItems(data);
}
