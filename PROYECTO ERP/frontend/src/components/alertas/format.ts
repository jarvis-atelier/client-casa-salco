import type { EstadoAlerta, Severidad, TipoAlerta } from "@/lib/types";

const TIPO_LABEL: Record<TipoAlerta, string> = {
  pago_duplicado: "Pago duplicado",
  factura_compra_repetida: "Factura compra repetida",
  items_repetidos_diff_nro: "Items repetidos",
  anulaciones_frecuentes: "Anulaciones frecuentes",
  ajuste_stock_sospechoso: "Ajuste stock sospechoso",
  nota_credito_sospechosa: "NC sospechosa",
  venta_fuera_horario: "Venta fuera horario",
  descuento_excesivo: "Descuento excesivo",
  vencimiento_proximo: "Vencimiento próximo",
  stock_bajo_minimo: "Stock bajo mínimo",
  sobrestock: "Sobrestock",
  rotacion_lenta: "Rotación lenta",
  rotacion_rapida_faltante: "Rotación rápida sin stock",
};

export function tipoAlertaLabel(t: TipoAlerta): string {
  return TIPO_LABEL[t] ?? t;
}

const SEVERIDAD_LABEL: Record<Severidad, string> = {
  baja: "Baja",
  media: "Media",
  alta: "Alta",
  critica: "Crítica",
};

export function severidadLabel(s: Severidad): string {
  return SEVERIDAD_LABEL[s] ?? s;
}

export function severidadBadgeVariant(
  s: Severidad,
): "default" | "secondary" | "destructive" | "success" | "outline" {
  if (s === "critica") return "destructive";
  if (s === "alta") return "destructive";
  if (s === "media") return "secondary";
  return "outline";
}

const ESTADO_LABEL: Record<EstadoAlerta, string> = {
  nueva: "Nueva",
  en_revision: "En revisión",
  descartada: "Descartada",
  confirmada: "Confirmada",
  resuelta: "Resuelta",
};

export function estadoAlertaLabel(e: EstadoAlerta): string {
  return ESTADO_LABEL[e] ?? e;
}

export function estadoBadgeVariant(
  e: EstadoAlerta,
): "default" | "secondary" | "destructive" | "success" | "outline" {
  if (e === "nueva") return "default";
  if (e === "en_revision") return "secondary";
  if (e === "confirmada") return "destructive";
  if (e === "resuelta") return "success";
  return "outline"; // descartada
}

export function relativeTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const diff = Date.now() - d.getTime();
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "ahora";
  if (minutes < 60) return `hace ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `hace ${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `hace ${days}d`;
  const months = Math.floor(days / 30);
  if (months < 12) return `hace ${months} mes${months > 1 ? "es" : ""}`;
  const years = Math.floor(months / 12);
  return `hace ${years} año${years > 1 ? "s" : ""}`;
}

export function formatAbsolute(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
