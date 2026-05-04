import { apiClient } from "./client";
import type { MedioPago } from "@/lib/types";

export interface ReportsParams {
  fecha_desde?: string;
  fecha_hasta?: string;
  sucursal_id?: number;
}

export interface VentasResumenSucursal {
  sucursal_id: number;
  codigo: string;
  nombre: string;
  cantidad: number;
  total: string;
}

export interface VentasResumen {
  fecha_desde: string;
  fecha_hasta: string;
  sucursal_id: number | null;
  total_facturas: number;
  total_facturado: string;
  total_iva: string;
  ticket_promedio: string;
  var_total_pct: number | null;
  var_cantidad_pct: number | null;
  var_ticket_pct: number | null;
  var_iva_pct: number | null;
  prev_total_facturado: string;
  prev_total_facturas: number;
  por_sucursal: VentasResumenSucursal[];
}

export interface VentasPorDia {
  fecha: string;
  total: string;
  cantidad: number;
  por_sucursal: Record<string, string>;
}

export interface TopProducto {
  articulo_id: number;
  codigo: string;
  descripcion: string;
  cantidad_vendida: string;
  total_facturado: string;
}

export interface VentasPorHora {
  dia_semana: number; // 0=Lunes ... 6=Domingo
  hora: number; // 0..23
  cantidad: number;
  total: string;
}

export interface MedioPagoStat {
  medio: MedioPago;
  cantidad: number;
  total: string;
  porc: number;
}

export async function getVentasResumen(
  params: ReportsParams = {},
): Promise<VentasResumen> {
  const { data } = await apiClient.get<VentasResumen>(
    "/reports/ventas-resumen",
    { params },
  );
  return data;
}

export async function getVentasPorDia(
  params: ReportsParams = {},
): Promise<VentasPorDia[]> {
  const { data } = await apiClient.get<VentasPorDia[]>(
    "/reports/ventas-por-dia",
    { params },
  );
  return data;
}

export async function getTopProductos(
  params: ReportsParams & { limit?: number } = {},
): Promise<TopProducto[]> {
  const { data } = await apiClient.get<TopProducto[]>(
    "/reports/top-productos",
    { params },
  );
  return data;
}

export async function getVentasPorHora(
  params: ReportsParams = {},
): Promise<VentasPorHora[]> {
  const { data } = await apiClient.get<VentasPorHora[]>(
    "/reports/ventas-por-hora",
    { params },
  );
  return data;
}

export async function getMediosPago(
  params: ReportsParams = {},
): Promise<MedioPagoStat[]> {
  const { data } = await apiClient.get<MedioPagoStat[]>(
    "/reports/medios-pago",
    { params },
  );
  return data;
}

// --- Correlaciones (Apriori / Market Basket) -----------------------------------

export interface CorrelacionRegla {
  antecedentes_ids: number[];
  antecedentes_codigos: string[];
  antecedentes_desc: string[];
  consecuentes_ids: number[];
  consecuentes_codigos: string[];
  consecuentes_desc: string[];
  soporte: number;
  confianza: number;
  lift: number;
}

export interface CorrelacionesParams extends ReportsParams {
  soporte_min?: number;
  confianza_min?: number;
  lift_min?: number;
  top_n?: number;
  force_recompute?: boolean;
}

export interface CorrelacionesResponse {
  fecha_desde: string;
  fecha_hasta: string;
  sucursal_id: number | null;
  transacciones_analizadas: number;
  items_unicos: number;
  params: {
    soporte_min: number;
    confianza_min: number;
    lift_min: number;
    top_n?: number;
    max_len?: number;
  };
  reglas: CorrelacionRegla[];
  cached: boolean;
}

export async function getCorrelaciones(
  params: CorrelacionesParams = {},
): Promise<CorrelacionesResponse> {
  const { data } = await apiClient.get<CorrelacionesResponse>(
    "/reports/correlaciones",
    { params },
  );
  return data;
}
