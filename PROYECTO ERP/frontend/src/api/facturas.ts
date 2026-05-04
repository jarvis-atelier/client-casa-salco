import { apiClient } from "./client";
import type {
  Factura,
  MedioPago,
  Paginated,
  TipoComprobante,
} from "@/lib/types";

export interface FacturaItemPayload {
  articulo_id: number;
  cantidad: string;
  precio_unitario: string;
  descuento_porc?: string;
}

export interface FacturaPagoPayload {
  medio: MedioPago;
  monto: string;
  referencia?: string | null;
}

export interface FacturaCreatePayload {
  sucursal_id: number;
  punto_venta?: number;
  tipo: TipoComprobante;
  cliente_id?: number | null;
  observacion?: string | null;
  items: FacturaItemPayload[];
  pagos: FacturaPagoPayload[];
}

export interface FacturasQuery {
  sucursal_id?: number;
  tipo?: TipoComprobante;
  fecha_desde?: string;
  fecha_hasta?: string;
  cliente_id?: number;
  page?: number;
  per_page?: number;
}

export async function createFactura(
  payload: FacturaCreatePayload,
): Promise<Factura> {
  const { data } = await apiClient.post<Factura>("/facturas", payload);
  return data;
}

export async function listFacturas(
  params: FacturasQuery = {},
): Promise<Paginated<Factura>> {
  const { data } = await apiClient.get<Paginated<Factura>>("/facturas", {
    params,
  });
  return data;
}

export async function getFactura(id: number): Promise<Factura> {
  const { data } = await apiClient.get<Factura>(`/facturas/${id}`);
  return data;
}

export async function anularFactura(id: number): Promise<Factura> {
  const { data } = await apiClient.post<Factura>(`/facturas/${id}/anular`, {});
  return data;
}

export interface EmitirCaeResponse {
  factura_id: number;
  cae: string;
  fecha_vencimiento: string;
  numero_comprobante: number;
  punto_venta: number;
  tipo_afip: number;
  qr_url: string;
  proveedor: string;
  resultado: string;
  reproceso: boolean;
  obs_afip?: string | null;
}

export async function emitirCae(id: number): Promise<EmitirCaeResponse> {
  const { data } = await apiClient.post<EmitirCaeResponse>(
    `/facturas/${id}/emitir-cae`,
    {},
  );
  return data;
}
