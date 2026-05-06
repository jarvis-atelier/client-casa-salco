/**
 * Builder de payloads para el agente local de impresión.
 *
 * Toma la Factura emitida por el backend + datos de Sucursal + Comercio y
 * arma el JSON que espera `POST /print/ticket` del agente.
 *
 * Hoy el "comercio" (razón social, CUIT, IIBB, dirección) está hardcoded
 * acá — más adelante (Fase 3) será configuración global persistida en la DB.
 */
import type { Cliente, Factura, Sucursal, TipoComprobante } from "@/lib/types";
import { parseDecimal } from "@/lib/types";
import type {
  AfipAgentPayload,
  ComercioPayload,
  TicketAgentPayload,
  TipoComprobanteAgent,
} from "@/api/agent";

// ---------------------------------------------------------------------------
// Comercio (config global hardcoded por ahora)
// ---------------------------------------------------------------------------

export const DEFAULT_COMERCIO: ComercioPayload = {
  razon_social: "CASA SALCO",
  cuit: "30-12345678-9",
  direccion: "Av. San Martín 1200, Río Cuarto, Córdoba",
  telefono: "0358-4636700",
  iibb: "900-123456",
  inicio_actividades: "2010-01-01",
  condicion_iva: "Responsable Inscripto",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const TIPO_LETRA_MAP: Record<TipoComprobante, string> = {
  ticket: "X",
  factura_a: "A",
  factura_b: "B",
  factura_c: "C",
  nc_a: "A",
  nc_b: "B",
  nc_c: "C",
  remito: "R",
  presupuesto: "P",
};

/** AFIP doc type codes (a8): 80=CUIT, 86=CUIL, 96=DNI, 99=CF anónimo */
function tipoDocReceptor(cliente: Cliente | null | undefined): number {
  if (!cliente || !cliente.cuit) return 99; // consumidor final anónimo
  const digits = cliente.cuit.replace(/\D/g, "");
  if (digits.length === 11) return 80; // CUIT
  if (digits.length === 8) return 96; // DNI
  return 99;
}

function condicionIvaLabel(c: Cliente | null | undefined): string {
  if (!c) return "Consumidor Final";
  return c.condicion_iva.replace(/_/g, " ").replace(/\b\w/g, (m) => m.toUpperCase());
}

function razonSocialReceptor(c: Cliente | null | undefined): string {
  return c ? c.razon_social : "Consumidor Final";
}

function nroDocReceptor(c: Cliente | null | undefined): string {
  if (!c) return "0";
  return c.cuit ?? "0";
}

// ---------------------------------------------------------------------------
// Tipo conversion factura backend → agente
// ---------------------------------------------------------------------------

function mapTipoToAgent(tipo: TipoComprobante): TipoComprobanteAgent {
  // Same string for all currently-supported types.
  return tipo as TipoComprobanteAgent;
}

// ---------------------------------------------------------------------------
// IVA desglose: agrupa items por alícuota
// ---------------------------------------------------------------------------

function buildIvaDesglose(factura: Factura) {
  const grouped = new Map<string, { base: number; iva: number }>();
  for (const it of factura.items) {
    const alic = parseDecimal(it.iva_porc) ?? 0;
    const base = parseDecimal(it.subtotal) ?? 0;
    const iva = parseDecimal(it.iva_monto) ?? 0;
    const key = alic.toFixed(2);
    const prev = grouped.get(key) ?? { base: 0, iva: 0 };
    grouped.set(key, { base: prev.base + base, iva: prev.iva + iva });
  }
  return Array.from(grouped.entries())
    .map(([alic, { base, iva }]) => ({
      alic: alic.replace(/\.00$/, ""),
      base: base.toFixed(2),
      iva: iva.toFixed(2),
    }))
    .filter((d) => Number(d.iva) > 0)
    .sort((a, b) => Number(b.alic) - Number(a.alic));
}

// ---------------------------------------------------------------------------
// Builder principal
// ---------------------------------------------------------------------------

export interface BuildTicketArgs {
  factura: Factura;
  sucursal: Sucursal | null | undefined;
  cliente?: Cliente | null;
  cajero?: { nombre?: string | null; email?: string | null } | null;
  comercio?: ComercioPayload;
  anchoPapelMm?: number;
}

export function buildTicketPayload({
  factura,
  sucursal,
  cliente,
  cajero,
  comercio = DEFAULT_COMERCIO,
  anchoPapelMm = 80,
}: BuildTicketArgs): TicketAgentPayload {
  const items = factura.items.map((it) => ({
    codigo: it.codigo,
    descripcion: it.descripcion,
    cantidad: it.cantidad,
    unidad: "unidad",
    precio_unitario: it.precio_unitario,
    subtotal: it.subtotal,
    iva_porc: it.iva_porc,
    descuento_porc: it.descuento_porc,
  }));

  const pagos = factura.pagos.map((p) => ({
    medio: p.medio,
    monto: p.monto,
    referencia: p.referencia ?? null,
  }));

  const afip: AfipAgentPayload | null =
    factura.cae && factura.cae_vencimiento
      ? {
          cae: factura.cae,
          vencimiento: factura.cae_vencimiento,
          // El QR completo lo arma el backend (Fase 2.2). Si no está, usamos el CAE como fallback.
          qr_url: `https://www.afip.gob.ar/fe/qr/?p=${factura.cae}`,
        }
      : null;

  return {
    tipo: mapTipoToAgent(factura.tipo),
    comercio,
    sucursal: {
      codigo: sucursal?.codigo ?? `SUC${factura.sucursal_id}`,
      nombre: sucursal?.nombre ?? `Sucursal ${factura.sucursal_id}`,
      punto_venta: factura.punto_venta,
    },
    comprobante: {
      tipo_letra: TIPO_LETRA_MAP[factura.tipo] ?? null,
      numero: factura.numero,
      fecha: factura.fecha,
      tipo_doc_receptor: tipoDocReceptor(cliente),
      nro_doc_receptor: nroDocReceptor(cliente),
      razon_social_receptor: razonSocialReceptor(cliente),
      condicion_iva_receptor: condicionIvaLabel(cliente),
    },
    items,
    totales: {
      subtotal: factura.subtotal,
      total_descuento: factura.total_descuento,
      total_iva: factura.total_iva,
      iva_desglosado: buildIvaDesglose(factura),
      total: factura.total,
    },
    pagos,
    afip,
    cajero: cajero?.nombre ?? cajero?.email ?? null,
    observacion: factura.observacion ?? null,
    ancho_papel_mm: anchoPapelMm,
  };
}
