import { apiClient } from "./client";
import type {
  AutoGenerarResultado,
  CalendarResponse,
  CompromisoDetalle,
  CompromisoPago,
  CompromisoResumen,
  EstadoCompromiso,
  Paginated,
  TarjetaCorporativa,
  TarjetasResponse,
  TipoCompromiso,
} from "@/lib/types";

// ---------------------------------------------------------------------------
// Compromisos
// ---------------------------------------------------------------------------

export interface CompromisosQuery {
  estado?: EstadoCompromiso;
  tipo?: TipoCompromiso;
  proveedor_id?: number;
  tarjeta_id?: number;
  fecha_desde?: string;
  fecha_hasta?: string;
  page?: number;
  per_page?: number;
}

export interface CompromisoCreatePayload {
  tipo: TipoCompromiso;
  descripcion: string;
  monto_total: string | number;
  fecha_emision?: string | null;
  fecha_vencimiento: string;
  proveedor_id?: number | null;
  factura_id?: number | null;
  tarjeta_id?: number | null;
  sucursal_id?: number | null;
  nota?: string | null;
}

export interface CompromisoPatchPayload {
  tipo?: TipoCompromiso;
  descripcion?: string;
  monto_total?: string | number;
  fecha_emision?: string | null;
  fecha_vencimiento?: string;
  proveedor_id?: number | null;
  factura_id?: number | null;
  tarjeta_id?: number | null;
  sucursal_id?: number | null;
  nota?: string | null;
  estado?: EstadoCompromiso;
}

export interface PagoCompromisoPayload {
  monto: string | number;
  fecha_pago: string;
  medio_pago: string;
  referencia?: string | null;
  registrar_movimiento_caja?: boolean;
  sucursal_id?: number | null;
}

export async function listCompromisos(
  params: CompromisosQuery = {},
): Promise<Paginated<CompromisoPago>> {
  const { data } = await apiClient.get<Paginated<CompromisoPago>>(
    "/compromisos",
    { params },
  );
  return data;
}

export async function getCompromiso(id: number): Promise<CompromisoDetalle> {
  const { data } = await apiClient.get<CompromisoDetalle>(`/compromisos/${id}`);
  return data;
}

export async function createCompromiso(
  payload: CompromisoCreatePayload,
): Promise<CompromisoPago> {
  const { data } = await apiClient.post<CompromisoPago>("/compromisos", payload);
  return data;
}

export async function patchCompromiso(
  id: number,
  payload: CompromisoPatchPayload,
): Promise<CompromisoPago> {
  const { data } = await apiClient.patch<CompromisoPago>(
    `/compromisos/${id}`,
    payload,
  );
  return data;
}

export async function deleteCompromiso(id: number): Promise<void> {
  await apiClient.delete(`/compromisos/${id}`);
}

export async function pagarCompromiso(
  id: number,
  payload: PagoCompromisoPayload,
): Promise<{ pago: unknown; compromiso: CompromisoPago }> {
  const { data } = await apiClient.post<{
    pago: unknown;
    compromiso: CompromisoPago;
  }>(`/compromisos/${id}/pagar`, payload);
  return data;
}

export async function getCompromisosResumen(): Promise<CompromisoResumen> {
  const { data } = await apiClient.get<CompromisoResumen>(
    "/compromisos/resumen",
  );
  return data;
}

export async function getCompromisosCalendar(
  mes: string,
): Promise<CalendarResponse> {
  const { data } = await apiClient.get<CalendarResponse>(
    "/compromisos/calendar",
    { params: { mes } },
  );
  return data;
}

export async function autoGenerarCompromisos(
  desde?: string,
): Promise<AutoGenerarResultado> {
  const { data } = await apiClient.post<AutoGenerarResultado>(
    "/compromisos/auto-generar",
    desde ? { desde } : {},
  );
  return data;
}

// ---------------------------------------------------------------------------
// Tarjetas
// ---------------------------------------------------------------------------

export interface TarjetaCreatePayload {
  nombre: string;
  banco?: string | null;
  ultimos_4: string;
  titular?: string | null;
  limite_total?: string | number | null;
  dia_cierre: number;
  dia_vencimiento: number;
  activa?: boolean;
}

export interface TarjetaPatchPayload {
  nombre?: string;
  banco?: string | null;
  ultimos_4?: string;
  titular?: string | null;
  limite_total?: string | number | null;
  dia_cierre?: number;
  dia_vencimiento?: number;
  activa?: boolean;
}

export async function listTarjetas(): Promise<TarjetaCorporativa[]> {
  const { data } = await apiClient.get<TarjetasResponse>("/tarjetas");
  return data.items;
}

export async function createTarjeta(
  payload: TarjetaCreatePayload,
): Promise<TarjetaCorporativa> {
  const { data } = await apiClient.post<TarjetaCorporativa>(
    "/tarjetas",
    payload,
  );
  return data;
}

export async function patchTarjeta(
  id: number,
  payload: TarjetaPatchPayload,
): Promise<TarjetaCorporativa> {
  const { data } = await apiClient.patch<TarjetaCorporativa>(
    `/tarjetas/${id}`,
    payload,
  );
  return data;
}

export async function deleteTarjeta(id: number): Promise<void> {
  await apiClient.delete(`/tarjetas/${id}`);
}
