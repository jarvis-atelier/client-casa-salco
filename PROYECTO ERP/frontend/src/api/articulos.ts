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
  /** Backend lo persiste como `ArticuloCodigo` con `tipo='principal'`.
   *  Antes era `codigo_barras` — renombrado en `articulo-multi-codigo-migration`. */
  codigo_principal?: string | null;
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

/**
 * Lookup exacto por código. Usado en la hot path del POS (scanner) para
 * evitar el LIKE de `/articulos?q=…`. Devuelve 404 si el código no existe.
 */
export async function getArticuloByCodigo(codigo: string): Promise<Articulo> {
  const { data } = await apiClient.get<Articulo>(
    `/articulos/by-codigo/${encodeURIComponent(codigo)}`,
  );
  return data;
}
