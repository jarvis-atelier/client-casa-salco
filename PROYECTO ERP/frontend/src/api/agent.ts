/**
 * Cliente HTTP del agente local de impresión (Jarvis POS Agent).
 *
 * El agente corre en el equipo del cajero (típicamente 127.0.0.1:9123). Va
 * por afuera de `apiClient` porque NO usa JWT del backend ni el baseURL /api/v1.
 */
import axios, { type AxiosInstance } from "axios";

const AGENT_BASE: string =
  (import.meta.env.VITE_AGENT_URL as string | undefined) ??
  "http://localhost:9123";

const agentClient: AxiosInstance = axios.create({
  baseURL: AGENT_BASE,
  timeout: 8_000,
});

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------

export type PrinterDriver = "mock" | "usb" | "network";

export type PrinterStatusValue = "ready" | "error" | "offline" | "no_paper";

export type PaperState = "ok" | "low" | "out" | "unknown";

export interface PrinterStatusResponse {
  status: PrinterStatusValue;
  driver: PrinterDriver;
  model: string;
  papel: PaperState;
  online: boolean;
  detail?: string | null;
  extra?: Record<string, string>;
}

export interface ComercioPayload {
  razon_social: string;
  cuit: string;
  direccion?: string | null;
  telefono?: string | null;
  iibb?: string | null;
  inicio_actividades?: string | null;
  condicion_iva?: string | null;
}

export interface SucursalAgentPayload {
  codigo: string;
  nombre: string;
  punto_venta: number;
}

export interface ComprobanteAgentPayload {
  tipo_letra?: string | null; // "A" | "B" | "C" | "X"
  numero: number;
  fecha: string; // ISO datetime
  tipo_doc_receptor?: number | null;
  nro_doc_receptor?: string | null;
  razon_social_receptor?: string | null;
  condicion_iva_receptor?: string | null;
}

export interface ItemAgentPayload {
  codigo: string;
  descripcion: string;
  cantidad: string;
  unidad?: string | null;
  precio_unitario: string;
  subtotal: string;
  iva_porc?: string | null;
  descuento_porc?: string | null;
}

export interface IvaDesglosePayload {
  alic: string;
  base: string;
  iva: string;
}

export interface TotalesAgentPayload {
  subtotal: string;
  total_descuento?: string;
  total_iva?: string;
  iva_desglosado?: IvaDesglosePayload[];
  total: string;
}

export interface PagoAgentPayload {
  medio: string;
  monto: string;
  referencia?: string | null;
}

export interface AfipAgentPayload {
  cae: string;
  vencimiento: string;
  qr_url: string;
}

export type TipoComprobanteAgent =
  | "ticket"
  | "factura_a"
  | "factura_b"
  | "factura_c"
  | "nc_a"
  | "nc_b"
  | "nc_c"
  | "remito"
  | "presupuesto"
  | "comanda";

export interface TicketAgentPayload {
  tipo: TipoComprobanteAgent;
  comercio: ComercioPayload;
  sucursal: SucursalAgentPayload;
  comprobante: ComprobanteAgentPayload;
  items: ItemAgentPayload[];
  totales: TotalesAgentPayload;
  pagos?: PagoAgentPayload[];
  afip?: AfipAgentPayload | null;
  cajero?: string | null;
  observacion?: string | null;
  ancho_papel_mm?: number;
}

export interface PrintTicketResponse {
  printed: boolean;
  driver: PrinterDriver;
  duration_ms: number;
  metadata: Record<string, string>;
  preview_id?: string;
  preview_url?: string;
  error?: string;
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

export async function getPrinterStatus(): Promise<PrinterStatusResponse> {
  const { data } = await agentClient.get<PrinterStatusResponse>("/status");
  return data;
}

export async function printTicket(
  payload: TicketAgentPayload,
): Promise<PrintTicketResponse> {
  const { data } = await agentClient.post<PrintTicketResponse>(
    "/print/ticket",
    payload,
  );
  return data;
}

/**
 * Devuelve la URL absoluta para abrir el PDF preview en una pestaña.
 */
export function previewUrl(previewId: string): string {
  return `${AGENT_BASE.replace(/\/$/, "")}/preview/${previewId}`;
}

export const AGENT_BASE_URL = AGENT_BASE;

// ---------------------------------------------------------------------------
// Balanza (scale) — Kretz / Systel / Network / Mock
// ---------------------------------------------------------------------------

export type ScaleDriver = "mock" | "kretz" | "systel" | "network";
export type ScaleStatusValue = "ready" | "error" | "offline";

export interface ScaleStatusResponse {
  status: ScaleStatusValue;
  driver: ScaleDriver;
  model: string;
  online: boolean;
  port?: string | null;
  last_weight_kg?: string | null; // string decimal (kg)
  detail?: string | null;
  error?: string | null;
  extra?: Record<string, string>;
}

export interface WeightReadingResponse {
  ok: boolean;
  driver: ScaleDriver;
  weight_kg: string; // decimal kg
  stable: boolean;
  tare_kg: string;
  unit: "kg" | "g";
  timestamp: string; // ISO datetime
  raw?: string | null;
}

export interface TareResponse {
  ok: boolean;
  driver: ScaleDriver;
  tare_kg: string;
}

export async function getScaleStatus(): Promise<ScaleStatusResponse> {
  const { data } = await agentClient.get<ScaleStatusResponse>("/scale/status");
  return data;
}

export async function readWeight(): Promise<WeightReadingResponse> {
  const { data } = await agentClient.get<WeightReadingResponse>("/scale/weight");
  return data;
}

export async function tareScale(): Promise<TareResponse> {
  const { data } = await agentClient.post<TareResponse>("/scale/tare");
  return data;
}
