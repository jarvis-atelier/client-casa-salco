/**
 * Helpers de formateo monetario / numérico para el dashboard.
 * Todos en es-AR + ARS.
 */

const ARS_FULL = new Intl.NumberFormat("es-AR", {
  style: "currency",
  currency: "ARS",
  maximumFractionDigits: 0,
});

const ARS_DETAIL = new Intl.NumberFormat("es-AR", {
  style: "currency",
  currency: "ARS",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const NUM = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 0 });

/**
 * `$234.567` (sin decimales). Si v es null/undefined → "—".
 * Para tarjetas grandes y ejes.
 */
export function formatARS(v: string | number | null | undefined): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = typeof v === "string" ? parseFloat(v) : v;
  if (!Number.isFinite(n)) return "—";
  return ARS_FULL.format(n);
}

/**
 * `$234.567,89` (con decimales). Para tooltips y tablas.
 */
export function formatARSDetail(v: string | number | null | undefined): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = typeof v === "string" ? parseFloat(v) : v;
  if (!Number.isFinite(n)) return "—";
  return ARS_DETAIL.format(n);
}

/**
 * `$234k` `$1.2M`. Compacto para ejes.
 */
export function formatARSCompact(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  const abs = Math.abs(v);
  if (abs >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `$${Math.round(v / 1_000)}k`;
  return `$${Math.round(v)}`;
}

export function formatNumber(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  return NUM.format(v);
}

export function formatPercent(
  v: number | null | undefined,
  withSign = false,
): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  const sign = withSign && v > 0 ? "+" : "";
  return `${sign}${v.toFixed(1)}%`;
}

/**
 * dd/MM
 */
export function formatDateShort(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  if (isNaN(d.getTime())) return iso;
  const day = String(d.getDate()).padStart(2, "0");
  const month = String(d.getMonth() + 1).padStart(2, "0");
  return `${day}/${month}`;
}

/**
 * Domingo, 23 de abril
 */
export function formatDateLong(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("es-AR", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

export const MEDIO_PAGO_LABEL: Record<string, string> = {
  efectivo: "Efectivo",
  tarjeta_debito: "Tarjeta débito",
  tarjeta_credito: "Tarjeta crédito",
  transferencia: "Transferencia",
  qr_mercadopago: "QR Mercado Pago",
  qr_modo: "QR MODO",
  cheque: "Cheque",
  cuenta_corriente: "Cuenta corriente",
  vale: "Vale",
};

export function labelMedioPago(medio: string): string {
  return MEDIO_PAGO_LABEL[medio] ?? medio;
}

export const DIA_SEMANA_SHORT = [
  "Lun",
  "Mar",
  "Mié",
  "Jue",
  "Vie",
  "Sáb",
  "Dom",
];

export const DIA_SEMANA_LONG = [
  "Lunes",
  "Martes",
  "Miércoles",
  "Jueves",
  "Viernes",
  "Sábado",
  "Domingo",
];
