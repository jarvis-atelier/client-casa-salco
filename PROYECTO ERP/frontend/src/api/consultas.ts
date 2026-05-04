/**
 * API wrapper para los endpoints de Consultas (F3 del sistema viejo).
 *
 * Cada entidad expone:
 *   GET /consultas/<entidad>      → JSON paginado
 *   GET /consultas/<entidad>.xlsx → descarga Excel
 */
import { apiClient } from "./client";

export type EntidadConsulta =
  | "clientes"
  | "proveedores"
  | "articulos"
  | "ventas"
  | "compras"
  | "cobranzas"
  | "pagos"
  | "movimientos"
  | "stock-bajo"
  | "caes"
  | "alertas";

export interface ConsultaPage {
  items: Record<string, unknown>[];
  page: number;
  per_page: number;
  total: number;
  pages: number;
  entidad: string;
}

export interface ConsultaParams {
  page?: number;
  per_page?: number;
  q?: string;
  fecha_desde?: string;
  fecha_hasta?: string;
  sucursal_id?: number | null;
  proveedor_id?: number | null;
  cliente_id?: number | null;
  tipo?: string;
  estado?: string;
  severidad?: string;
  medio?: string;
  minimo?: number;
  activo?: string;
}

function cleanParams(p: ConsultaParams): Record<string, string | number> {
  const out: Record<string, string | number> = {};
  for (const [k, v] of Object.entries(p)) {
    if (v === undefined || v === null || v === "") continue;
    out[k] = v as string | number;
  }
  return out;
}

export async function listConsulta(
  entidad: EntidadConsulta,
  params: ConsultaParams = {},
): Promise<ConsultaPage> {
  const { data } = await apiClient.get<ConsultaPage>(`/consultas/${entidad}`, {
    params: cleanParams(params),
  });
  return data;
}

export async function downloadConsultaXlsx(
  entidad: EntidadConsulta,
  params: ConsultaParams = {},
): Promise<void> {
  const res = await apiClient.get<Blob>(`/consultas/${entidad}.xlsx`, {
    params: cleanParams(params),
    responseType: "blob",
  });

  const disposition = res.headers["content-disposition"] as string | undefined;
  const today = new Date().toISOString().slice(0, 10);
  const fallback = `consulta-${entidad}_${today}.xlsx`;
  const match = disposition?.match(/filename\*?=(?:UTF-8''|"?)([^";]+)"?/i);
  const filename = match ? decodeURIComponent(match[1]) : fallback;

  const blob = new Blob([res.data], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  const url = URL.createObjectURL(blob);
  try {
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } finally {
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
}
