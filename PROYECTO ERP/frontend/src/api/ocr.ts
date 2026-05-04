import { apiClient } from "./client";
import type { Paginated } from "@/lib/types";

export type EstadoOcr =
  | "pendiente"
  | "procesando"
  | "extraido"
  | "confirmado"
  | "descartado"
  | "error";

export type TipoComprobanteOcr =
  | "factura"
  | "remito"
  | "presupuesto"
  | "desconocido";

export interface OcrItemExtraido {
  descripcion: string;
  cantidad: number | string;
  unidad: string;
  precio_unitario: string;
  subtotal?: string;
  articulo_id_match?: number | null;
}

export interface ProveedorMatchOcr {
  id: number;
  codigo: string;
  razon_social: string;
  cuit?: string | null;
}

export interface FacturaResumenOcr {
  id: number;
  numero: number;
  punto_venta: number;
  tipo: string;
  total: string;
}

export interface ComprobanteOcr {
  id: number;
  estado: EstadoOcr;
  tipo_detectado: TipoComprobanteOcr;
  letra: string | null;
  confianza: string | null;

  archivo_path: string;
  archivo_size_bytes: number;
  archivo_mime: string;

  proveedor_nombre_raw: string | null;
  proveedor_cuit_raw: string | null;
  proveedor_id_match: number | null;
  proveedor_match: ProveedorMatchOcr | null;

  numero_comprobante: string | null;
  fecha_comprobante: string | null;

  subtotal: string | null;
  iva_total: string | null;
  total: string | null;

  items_extraidos: OcrItemExtraido[];
  error_message: string | null;

  uploaded_by_user_id: number;
  sucursal_id: number | null;
  factura_creada_id: number | null;
  factura_creada: FacturaResumenOcr | null;

  duracion_extraccion_ms: number | null;
  modelo_ia_usado: string | null;

  created_at: string;
  updated_at: string;
}

export interface OcrItemOverridePayload {
  descripcion: string;
  cantidad: string;
  unidad: string;
  precio_unitario: string;
  iva_porc?: string;
  descuento_porc?: string;
  articulo_id?: number | null;
  crear_articulo_si_falta?: boolean;
}

export interface OcrConfirmarPayload {
  sucursal_id: number;
  proveedor_id?: number | null;
  numero_override?: string | null;
  fecha_override?: string | null;
  observacion?: string | null;
  items: OcrItemOverridePayload[];
}

export async function uploadComprobante(
  file: File,
  sucursalId?: number,
): Promise<ComprobanteOcr> {
  const fd = new FormData();
  fd.append("file", file);
  if (sucursalId) fd.append("sucursal_id", String(sucursalId));
  const { data } = await apiClient.post<ComprobanteOcr>(
    "/ocr/comprobante",
    fd,
    {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 60_000,
    },
  );
  return data;
}

export async function listComprobantes(params: {
  estado?: EstadoOcr;
  page?: number;
  per_page?: number;
} = {}): Promise<Paginated<ComprobanteOcr>> {
  const { data } = await apiClient.get<Paginated<ComprobanteOcr>>(
    "/ocr/comprobantes",
    { params },
  );
  return data;
}

export async function getComprobante(id: number): Promise<ComprobanteOcr> {
  const { data } = await apiClient.get<ComprobanteOcr>(
    `/ocr/comprobantes/${id}`,
  );
  return data;
}

export function getImagenUrl(id: number): string {
  return `/api/v1/ocr/comprobantes/${id}/imagen`;
}

export async function confirmarComprobante(
  id: number,
  payload: OcrConfirmarPayload,
): Promise<ComprobanteOcr> {
  const { data } = await apiClient.post<ComprobanteOcr>(
    `/ocr/comprobantes/${id}/confirmar`,
    payload,
  );
  return data;
}

export async function descartarComprobante(
  id: number,
): Promise<ComprobanteOcr> {
  const { data } = await apiClient.post<ComprobanteOcr>(
    `/ocr/comprobantes/${id}/descartar`,
    {},
  );
  return data;
}
