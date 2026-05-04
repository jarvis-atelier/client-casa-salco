import { apiClient } from "./client";
import type { Articulo, Paginated } from "@/lib/types";

export interface ArticulosQuery {
  page?: number;
  per_page?: number;
  q?: string;
  familia_id?: number;
  rubro_id?: number;
  subrubro_id?: number;
  marca_id?: number;
  proveedor_id?: number;
  solo_activos?: 0 | 1;
}

export interface ArticuloCreatePayload {
  codigo: string;
  descripcion: string;
  codigo_barras?: string | null;
  descripcion_corta?: string | null;
  familia_id?: number | null;
  rubro_id?: number | null;
  subrubro_id?: number | null;
  marca_id?: number | null;
  proveedor_principal_id?: number | null;
  unidad_medida?: "unidad" | "kg" | "gr" | "lt" | "ml";
  controla_stock?: boolean;
  controla_vencimiento?: boolean;
  costo?: string;
  pvp_base?: string;
  iva_porc?: string;
  activo?: boolean;
}

export async function listArticulos(
  params: ArticulosQuery = {},
): Promise<Paginated<Articulo>> {
  const { data } = await apiClient.get<Paginated<Articulo>>("/articulos", {
    params,
  });
  return data;
}

export async function createArticulo(
  payload: ArticuloCreatePayload,
): Promise<Articulo> {
  const { data } = await apiClient.post<Articulo>("/articulos", payload);
  return data;
}
