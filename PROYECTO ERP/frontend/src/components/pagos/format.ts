import type {
  EstadoCompromiso,
  TipoCompromiso,
} from "@/lib/types";

const TIPO_LABEL: Record<TipoCompromiso, string> = {
  factura_compra: "Factura compra",
  cuenta_corriente_proveedor: "Ctacte proveedor",
  tarjeta_corporativa: "Tarjeta",
  servicio: "Servicio",
  impuesto: "Impuesto",
  otro: "Otro",
};

export function tipoCompromisoLabel(t: TipoCompromiso): string {
  return TIPO_LABEL[t] ?? t;
}

const TIPO_BADGE: Record<
  TipoCompromiso,
  "default" | "secondary" | "destructive" | "outline" | "success"
> = {
  factura_compra: "secondary",
  cuenta_corriente_proveedor: "outline",
  tarjeta_corporativa: "default",
  servicio: "outline",
  impuesto: "outline",
  otro: "outline",
};

export function tipoCompromisoBadgeVariant(
  t: TipoCompromiso,
): "default" | "secondary" | "destructive" | "outline" | "success" {
  return TIPO_BADGE[t] ?? "secondary";
}

const ESTADO_LABEL: Record<EstadoCompromiso, string> = {
  pendiente: "Pendiente",
  parcial: "Parcial",
  pagado: "Pagado",
  vencido: "Vencido",
  cancelado: "Cancelado",
};

export function estadoCompromisoLabel(e: EstadoCompromiso): string {
  return ESTADO_LABEL[e] ?? e;
}

export function estadoCompromisoBadgeVariant(
  e: EstadoCompromiso,
): "default" | "secondary" | "destructive" | "outline" | "success" {
  if (e === "pagado") return "success";
  if (e === "vencido") return "destructive";
  if (e === "parcial") return "default";
  if (e === "cancelado") return "outline";
  return "secondary";
}

/**
 * Días entre `today` y la fecha. Negativo si ya venció.
 */
export function diasHasta(fechaIso: string): number {
  const d = new Date(fechaIso + "T00:00:00");
  const hoy = new Date();
  hoy.setHours(0, 0, 0, 0);
  const diffMs = d.getTime() - hoy.getTime();
  return Math.round(diffMs / (1000 * 60 * 60 * 24));
}

export function severidadColor(
  sev: "baja" | "media" | "alta" | "critica",
): string {
  switch (sev) {
    case "critica":
      return "bg-rose-500";
    case "alta":
      return "bg-amber-500";
    case "media":
      return "bg-amber-400";
    default:
      return "bg-emerald-500";
  }
}

export function severidadDeDias(
  dias: number,
  estado: EstadoCompromiso,
): "baja" | "media" | "alta" | "critica" {
  if (estado === "pagado" || estado === "cancelado") return "baja";
  if (dias < 0) return "critica";
  if (dias === 0) return "alta";
  if (dias <= 3) return "media";
  return "baja";
}

export function formatFechaCompacta(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
  });
}

export function formatFechaLarga(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("es-AR", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}

export function diasLabel(dias: number): string {
  if (dias === 0) return "Hoy";
  if (dias === 1) return "Mañana";
  if (dias === -1) return "Ayer";
  if (dias < 0) return `Hace ${-dias} días`;
  return `En ${dias} días`;
}
