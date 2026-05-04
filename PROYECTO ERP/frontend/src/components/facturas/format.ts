import type {
  EstadoComprobante,
  MedioPago,
  TipoComprobante,
} from "@/lib/types";
import { parseDecimal } from "@/lib/types";

export function formatMoney(v?: string | number | null): string {
  const n = parseDecimal(v);
  if (n === null) return "—";
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n);
}

export function formatNumber(v?: string | number | null): string {
  const n = parseDecimal(v);
  if (n === null) return "—";
  return new Intl.NumberFormat("es-AR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n);
}

export function formatDateShort(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDateLong(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("es-AR", {
    day: "2-digit",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatTimeShort(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("es-AR", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatComprobanteNumero(pv: number, nro: number): string {
  return `${String(pv).padStart(4, "0")}-${String(nro).padStart(8, "0")}`;
}

const TIPO_LABEL: Record<TipoComprobante, string> = {
  ticket: "Ticket",
  factura_a: "Factura A",
  factura_b: "Factura B",
  factura_c: "Factura C",
  nc_a: "NC A",
  nc_b: "NC B",
  nc_c: "NC C",
  remito: "Remito",
  presupuesto: "Presupuesto",
};

export function comprobanteLabel(t: TipoComprobante): string {
  return TIPO_LABEL[t] ?? t;
}

export function tipoComprobanteBadgeVariant(
  t: TipoComprobante,
):
  | "default"
  | "secondary"
  | "destructive"
  | "success"
  | "outline" {
  if (t === "factura_a" || t === "factura_b" || t === "factura_c")
    return "default";
  if (t === "nc_a" || t === "nc_b" || t === "nc_c") return "destructive";
  if (t === "remito" || t === "presupuesto") return "outline";
  return "secondary"; // ticket
}

export function estadoLabel(e: EstadoComprobante): string {
  if (e === "emitida") return "Emitida";
  if (e === "anulada") return "Anulada";
  return "Borrador";
}

const MEDIO_LABEL: Record<MedioPago, string> = {
  efectivo: "efectivo",
  tarjeta_debito: "tarjeta_debito",
  tarjeta_credito: "tarjeta_credito",
  transferencia: "transferencia",
  qr_mercadopago: "qr_mp",
  qr_modo: "qr_modo",
  cheque: "cheque",
  cuenta_corriente: "cta_cte",
  vale: "vale",
};

export function medioPagoLabel(m: MedioPago): string {
  return MEDIO_LABEL[m] ?? m;
}

const MEDIO_LABEL_HUMAN: Record<MedioPago, string> = {
  efectivo: "Efectivo",
  tarjeta_debito: "Tarjeta débito",
  tarjeta_credito: "Tarjeta crédito",
  transferencia: "Transferencia",
  qr_mercadopago: "QR MercadoPago",
  qr_modo: "QR MODO",
  cheque: "Cheque",
  cuenta_corriente: "Cuenta corriente",
  vale: "Vale",
};

export function medioPagoLabelHuman(m: MedioPago): string {
  return MEDIO_LABEL_HUMAN[m] ?? m;
}

/** Devuelve la fecha en formato YYYY-MM-DD para inputs date. */
export function dateToInputValue(d: Date): string {
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

export function todayInputValue(): string {
  return dateToInputValue(new Date());
}

export function daysAgoInputValue(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return dateToInputValue(d);
}
