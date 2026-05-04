import { apiClient } from "./client";
import type {
  MedioPago,
  MovimientoCaja,
  Paginated,
  TipoMovimiento,
} from "@/lib/types";
import { parseDecimal } from "@/lib/types";

export interface MovimientosQuery {
  sucursal_id?: number;
  tipo?: TipoMovimiento;
  fecha_desde?: string;
  fecha_hasta?: string;
  caja_numero?: number;
  page?: number;
  per_page?: number;
}

export async function listMovimientos(
  params: MovimientosQuery = {},
): Promise<Paginated<MovimientoCaja>> {
  const { data } = await apiClient.get<Paginated<MovimientoCaja>>(
    "/movimientos",
    { params },
  );
  return data;
}

// ---------------------------------------------------------------------------
// Helpers de agregación (frontend-side) — el backend hoy no agrega.
// ---------------------------------------------------------------------------

export interface ArqueoTotales {
  porMedio: Record<MedioPago, number>;
  ingresos: number;
  egresos: number;
  saldoNeto: number;
  cantidadMovimientos: number;
}

/**
 * Tipos que cuentan como ingreso (suman) vs egreso (restan) al arqueo.
 * Las "ventas" y "cobranzas" suman; "devoluciones" y "pago_proveedor" / "egreso_efectivo" restan.
 */
const TIPOS_INGRESO: ReadonlySet<TipoMovimiento> = new Set([
  "venta",
  "cobranza",
  "ingreso_efectivo",
  "cheque_recibido",
]);

const TIPOS_EGRESO: ReadonlySet<TipoMovimiento> = new Set([
  "devolucion",
  "pago_proveedor",
  "egreso_efectivo",
  "cheque_entregado",
]);

const MEDIOS_INIT: Record<MedioPago, number> = {
  efectivo: 0,
  tarjeta_debito: 0,
  tarjeta_credito: 0,
  transferencia: 0,
  qr_mercadopago: 0,
  qr_modo: 0,
  cheque: 0,
  cuenta_corriente: 0,
  vale: 0,
};

export function calcularArqueo(movs: MovimientoCaja[]): ArqueoTotales {
  const porMedio: Record<MedioPago, number> = { ...MEDIOS_INIT };
  let ingresos = 0;
  let egresos = 0;

  for (const m of movs) {
    const monto = parseDecimal(m.monto) ?? 0;
    if (m.medio) {
      // Sumamos firmado: ingreso suma, egreso resta al medio.
      const signed = TIPOS_EGRESO.has(m.tipo) ? -Math.abs(monto) : monto;
      porMedio[m.medio] = (porMedio[m.medio] ?? 0) + signed;
    }
    if (TIPOS_INGRESO.has(m.tipo)) {
      ingresos += Math.abs(monto);
    } else if (TIPOS_EGRESO.has(m.tipo)) {
      egresos += Math.abs(monto);
    }
  }

  return {
    porMedio,
    ingresos,
    egresos,
    saldoNeto: ingresos - egresos,
    cantidadMovimientos: movs.length,
  };
}

/**
 * Decide si un movimiento debe mostrarse con monto positivo o negativo en la UI.
 * Devolución, pago a proveedor, egreso de efectivo, cheque entregado → negativo.
 */
export function isMovimientoEgreso(tipo: TipoMovimiento): boolean {
  return TIPOS_EGRESO.has(tipo);
}
