/**
 * Cliente para los endpoints de exportación XLSX.
 *
 * Cada función pide el .xlsx con `responseType: 'blob'`, lee el filename del
 * header `Content-Disposition` cuando viene, y dispara la descarga creando
 * un `<a>` temporal en memoria.
 */
import { apiClient } from "./client";

export interface ExportRange {
  fecha_desde: string; // ISO date YYYY-MM-DD
  fecha_hasta: string;
}

function parseFilename(disposition: string | null, fallback: string): string {
  if (!disposition) return fallback;
  // RFC 5987 / standard: filename="..."
  const match = disposition.match(/filename\*?=(?:UTF-8''|"?)([^";]+)"?/i);
  return match ? decodeURIComponent(match[1]) : fallback;
}

async function downloadXlsx(
  path: string,
  params: Record<string, string | number | undefined>,
  fallbackName: string,
): Promise<void> {
  const cleanParams = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ""),
  );
  const res = await apiClient.get<Blob>(path, {
    params: cleanParams,
    responseType: "blob",
  });

  const disposition = res.headers["content-disposition"] as string | undefined;
  const filename = parseFilename(disposition ?? null, fallbackName);

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
    // Liberar el blob URL en el siguiente tick.
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
}

export async function downloadLibroIvaDigital(range: ExportRange): Promise<void> {
  await downloadXlsx(
    "/reports/libro-iva-digital.xlsx",
    { fecha_desde: range.fecha_desde, fecha_hasta: range.fecha_hasta },
    `libro-iva-digital_${range.fecha_desde}_${range.fecha_hasta}.xlsx`,
  );
}

export async function downloadVentasExport(
  range: ExportRange,
  sucursalId?: number | null,
): Promise<void> {
  await downloadXlsx(
    "/reports/ventas-export.xlsx",
    {
      fecha_desde: range.fecha_desde,
      fecha_hasta: range.fecha_hasta,
      sucursal_id: sucursalId ?? undefined,
    },
    `ventas_${range.fecha_desde}_${range.fecha_hasta}.xlsx`,
  );
}

export async function downloadStockExport(
  sucursalId?: number | null,
): Promise<void> {
  const today = new Date().toISOString().slice(0, 10);
  await downloadXlsx(
    "/reports/stock-export.xlsx",
    { sucursal_id: sucursalId ?? undefined },
    `stock_${today}.xlsx`,
  );
}

export async function downloadComprasExport(
  range: ExportRange,
  proveedorId?: number | null,
  sucursalId?: number | null,
): Promise<void> {
  await downloadXlsx(
    "/reports/compras-export.xlsx",
    {
      fecha_desde: range.fecha_desde,
      fecha_hasta: range.fecha_hasta,
      proveedor_id: proveedorId ?? undefined,
      sucursal_id: sucursalId ?? undefined,
    },
    `compras_${range.fecha_desde}_${range.fecha_hasta}.xlsx`,
  );
}

export async function downloadCobranzasExport(
  range: ExportRange,
  clienteId?: number | null,
  sucursalId?: number | null,
): Promise<void> {
  await downloadXlsx(
    "/reports/cobranzas-export.xlsx",
    {
      fecha_desde: range.fecha_desde,
      fecha_hasta: range.fecha_hasta,
      cliente_id: clienteId ?? undefined,
      sucursal_id: sucursalId ?? undefined,
    },
    `cobranzas_${range.fecha_desde}_${range.fecha_hasta}.xlsx`,
  );
}

export async function downloadPagosExport(
  range: ExportRange,
  proveedorId?: number | null,
  sucursalId?: number | null,
): Promise<void> {
  await downloadXlsx(
    "/reports/pagos-export.xlsx",
    {
      fecha_desde: range.fecha_desde,
      fecha_hasta: range.fecha_hasta,
      proveedor_id: proveedorId ?? undefined,
      sucursal_id: sucursalId ?? undefined,
    },
    `pagos_${range.fecha_desde}_${range.fecha_hasta}.xlsx`,
  );
}

export async function downloadResumenClientes(): Promise<void> {
  const today = new Date().toISOString().slice(0, 10);
  await downloadXlsx(
    "/reports/resumen-clientes.xlsx",
    {},
    `resumen-clientes_${today}.xlsx`,
  );
}

export async function downloadResumenProveedores(): Promise<void> {
  const today = new Date().toISOString().slice(0, 10);
  await downloadXlsx(
    "/reports/resumen-proveedores.xlsx",
    {},
    `resumen-proveedores_${today}.xlsx`,
  );
}

export async function downloadCtaCteCliente(
  clienteId: number,
  range?: Partial<ExportRange>,
): Promise<void> {
  const today = new Date().toISOString().slice(0, 10);
  await downloadXlsx(
    "/reports/cta-cte-cliente.xlsx",
    {
      cliente_id: clienteId,
      fecha_desde: range?.fecha_desde,
      fecha_hasta: range?.fecha_hasta,
    },
    `cta-cte-cliente-${clienteId}_${today}.xlsx`,
  );
}

export async function downloadCtaCteProveedor(
  proveedorId: number,
  range?: Partial<ExportRange>,
): Promise<void> {
  const today = new Date().toISOString().slice(0, 10);
  await downloadXlsx(
    "/reports/cta-cte-proveedor.xlsx",
    {
      proveedor_id: proveedorId,
      fecha_desde: range?.fecha_desde,
      fecha_hasta: range?.fecha_hasta,
    },
    `cta-cte-proveedor-${proveedorId}_${today}.xlsx`,
  );
}

export async function downloadStockValorizado(
  sucursalId?: number | null,
): Promise<void> {
  const today = new Date().toISOString().slice(0, 10);
  await downloadXlsx(
    "/reports/stock-valorizado.xlsx",
    { sucursal_id: sucursalId ?? undefined },
    `stock-valorizado_${today}.xlsx`,
  );
}

export async function downloadVentasDetallado(
  range: ExportRange,
  sucursalId?: number | null,
): Promise<void> {
  await downloadXlsx(
    "/reports/ventas-detallado.xlsx",
    {
      fecha_desde: range.fecha_desde,
      fecha_hasta: range.fecha_hasta,
      sucursal_id: sucursalId ?? undefined,
    },
    `ventas-detallado_${range.fecha_desde}_${range.fecha_hasta}.xlsx`,
  );
}
