/**
 * Helpers para mapear ComercioConfig (backend) → ComercioPayload (agente).
 */
import type { ComercioConfig } from "./comercio";
import type { ComercioPayload } from "./agent";

const FALLBACK: ComercioPayload = {
  razon_social: "Comercio sin configurar",
  cuit: "",
  direccion: null,
  telefono: null,
  iibb: null,
  inicio_actividades: null,
  condicion_iva: null,
};

export function comercioToAgentPayload(
  cfg: ComercioConfig | null | undefined,
): ComercioPayload {
  if (!cfg) return FALLBACK;
  const partes = [cfg.domicilio, cfg.localidad, cfg.provincia]
    .map((p) => (p ?? "").trim())
    .filter(Boolean);
  const direccion = partes.length ? partes.join(", ") : null;
  return {
    razon_social: cfg.razon_social || FALLBACK.razon_social,
    cuit: cfg.cuit || "",
    direccion,
    telefono: cfg.telefono ?? null,
    iibb: cfg.iibb ?? null,
    inicio_actividades: cfg.inicio_actividades ?? null,
    condicion_iva: cfg.condicion_iva || null,
  };
}
