export interface User {
  id: number;
  email: string;
  nombre?: string | null;
  rol?: string | null;
  sucursal_id?: number | null;
  activo?: boolean;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  user: User;
}

export interface RefreshResponse {
  access_token: string;
}

export interface Paginated<T> {
  items: T[];
  page: number;
  per_page: number;
  total: number;
  pages: number;
}

export interface Area {
  id: number;
  nombre: string;
  codigo?: string | null;
  sucursal_id: number;
  activa?: boolean;
}

export interface Sucursal {
  id: number;
  nombre: string;
  codigo: string;
  direccion?: string | null;
  ciudad?: string | null;
  provincia?: string | null;
  telefono?: string | null;
  lat?: number | null;
  lng?: number | null;
  activa: boolean;
  areas?: Area[];
  created_at?: string;
  updated_at?: string;
}

export interface Familia {
  id: number;
  nombre: string;
  codigo?: string | null;
  orden?: number;
}

export interface Rubro {
  id: number;
  nombre: string;
  codigo?: string | null;
  familia_id?: number | null;
}

export interface Marca {
  id: number;
  nombre: string;
  codigo?: string | null;
}

export interface Proveedor {
  id: number;
  nombre: string;
  cuit?: string | null;
  telefono?: string | null;
  email?: string | null;
}

/**
 * Tipo de código asociado a un artículo. Sólo `principal` se popula en
 * Change A; `alterno`, `empaquetado`, e `interno` los escribe Change B.
 */
export type TipoCodigoArticulo =
  | "principal"
  | "alterno"
  | "empaquetado"
  | "interno";

/**
 * Fila hija de `articulo_codigos`. El backend la devuelve en `Articulo.codigos`
 * vía `lazy="selectin"`. Para create/update usar `codigo_principal` en el
 * payload (sólo Change A — multi-código se gestiona en Change B).
 */
export interface ArticuloCodigo {
  id: number;
  articulo_id: number;
  codigo: string;
  tipo: TipoCodigoArticulo;
}

/**
 * El backend devuelve decimales como string (ej "890.0000").
 * Convertir con `parseDecimal` antes de mostrar.
 */
export interface Articulo {
  id: number;
  codigo: string;
  /** Sólo se usa en el payload de creación; el backend lo persiste como
   *  `ArticuloCodigo` con `tipo='principal'`. NO viene en la respuesta. */
  codigo_principal?: string | null;
  /** Lista de códigos asociados al artículo (lectura — populated server-side
   *  via selectin). Reemplaza al antiguo `codigo_barras`. */
  codigos?: ArticuloCodigo[];
  descripcion: string;
  descripcion_corta?: string | null;
  unidad_medida?: string | null;
  costo?: string | number | null;
  pvp_base?: string | number | null;
  iva_porc?: string | number | null;
  familia_id?: number | null;
  rubro_id?: number | null;
  subrubro_id?: number | null;
  marca_id?: number | null;
  proveedor_principal_id?: number | null;
  controla_stock?: boolean;
  controla_vencimiento?: boolean;
  activo: boolean;
  created_at?: string;
  updated_at?: string;
}

export function parseDecimal(v: string | number | null | undefined): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "string" ? parseFloat(v) : v;
  return Number.isFinite(n) ? n : null;
}

// --- Clientes ---

export type CondicionIva =
  | "responsable_inscripto"
  | "monotributo"
  | "consumidor_final"
  | "exento"
  | "no_categorizado";

export interface Cliente {
  id: number;
  codigo: string;
  razon_social: string;
  cuit?: string | null;
  condicion_iva: CondicionIva;
  condicion_iva_receptor_id?: number | null;
  telefono?: string | null;
  email?: string | null;
  direccion?: string | null;
  cuenta_corriente: boolean;
  limite_cuenta_corriente?: string | number;
  saldo?: string | number;
  activo: boolean;
  created_at?: string;
  updated_at?: string;
}

// --- Proveedores ---

export interface ProveedorFull {
  id: number;
  codigo: string;
  razon_social: string;
  cuit?: string | null;
  telefono?: string | null;
  email?: string | null;
  direccion?: string | null;
  activo: boolean;
  created_at?: string;
  updated_at?: string;
}

// --- Movimientos (ledger) ---

export type TipoMovimiento =
  | "venta"
  | "devolucion"
  | "cobranza"
  | "pago_proveedor"
  | "apertura_caja"
  | "cierre_caja"
  | "ingreso_efectivo"
  | "egreso_efectivo"
  | "ajuste"
  | "cheque_recibido"
  | "cheque_entregado";

export interface MovimientoCaja {
  id: number;
  sucursal_id: number;
  caja_numero: number;
  fecha_caja: string;
  fecha: string;
  tipo: TipoMovimiento;
  medio?: MedioPago | null;
  monto: string;
  factura_id?: number | null;
  cliente_id?: number | null;
  proveedor_id?: number | null;
  descripcion: string;
  user_id?: number | null;
  created_at: string;
  updated_at: string;
}

// --- Facturación ---

export type TipoComprobante =
  | "factura_a"
  | "factura_b"
  | "factura_c"
  | "ticket"
  | "nc_a"
  | "nc_b"
  | "nc_c"
  | "remito"
  | "presupuesto";

export type EstadoComprobante = "borrador" | "emitida" | "anulada";

export type MedioPago =
  | "efectivo"
  | "tarjeta_debito"
  | "tarjeta_credito"
  | "transferencia"
  | "qr_mercadopago"
  | "qr_modo"
  | "cheque"
  | "cuenta_corriente"
  | "vale";

export interface FacturaItem {
  id: number;
  articulo_id: number;
  codigo: string;
  descripcion: string;
  cantidad: string;
  precio_unitario: string;
  descuento_porc: string;
  iva_porc: string;
  iva_monto: string;
  subtotal: string;
  total: string;
  orden: number;
}

export interface FacturaPago {
  id: number;
  medio: MedioPago;
  monto: string;
  referencia?: string | null;
  orden: number;
}

export interface ClienteResumen {
  id: number;
  razon_social: string;
  cuit?: string | null;
}

export interface Factura {
  id: number;
  sucursal_id: number;
  punto_venta: number;
  tipo: TipoComprobante;
  numero: number;
  fecha: string;
  cliente_id: number | null;
  cajero_id: number;
  estado: EstadoComprobante;
  subtotal: string;
  total_iva: string;
  total_descuento: string;
  total: string;
  moneda: string;
  observacion?: string | null;
  cae?: string | null;
  cae_vencimiento?: string | null;
  items: FacturaItem[];
  pagos: FacturaPago[];
  cliente_nombre?: string | null;
  cliente_resumen?: ClienteResumen | null;
  created_at: string;
  updated_at: string;
}

export type EstadoReposicion =
  | "agotado"
  | "critico"
  | "reorden"
  | "sobrestock"
  | "ok";

export interface StockArticuloEmbedded {
  id: number;
  codigo: string;
  descripcion: string;
  costo?: string | null;
  pvp_base?: string | null;
}

export interface StockSucursalRow {
  id: number;
  articulo_id: number;
  sucursal_id: number;
  cantidad: string;
  // Stock inteligente — opción C
  stock_minimo?: string | null;
  stock_maximo?: string | null;
  punto_reorden?: string | null;
  lead_time_dias?: number | null;
  stock_optimo_calculado?: string | null;
  ultima_recalculacion?: string | null;
  // Resueltos (sucursal -> articulo default)
  efectivo_minimo?: string | null;
  efectivo_maximo?: string | null;
  efectivo_reorden?: string | null;
  efectivo_lead_time?: number | null;
  estado_reposicion?: EstadoReposicion | null;
  // Articulo embebido (codigo, descripcion, costo, pvp_base) — desde 2026-05-07.
  articulo?: StockArticuloEmbedded | null;
  created_at?: string;
  updated_at?: string;
}

export interface StockResumen {
  total: number;
  agotado: number;
  critico: number;
  reorden: number;
  sobrestock: number;
  ok: number;
}

export interface StockAjustePayload {
  articulo_id: number;
  sucursal_id: number;
  cantidad_nueva: number | string;
  motivo: string;
  // Stock inteligente — opcionales
  stock_minimo?: number | string | null;
  stock_maximo?: number | string | null;
  punto_reorden?: number | string | null;
  lead_time_dias?: number | null;
  unset_stock_minimo?: boolean;
  unset_stock_maximo?: boolean;
  unset_punto_reorden?: boolean;
  unset_lead_time_dias?: boolean;
}

// --- Reposición (stock inteligente) ---

export interface VelocidadVenta {
  velocidad_promedio_diaria: string;
  velocidad_dias_activos: string;
  cantidad_total_vendida: string;
  dias_con_venta: number;
  dias: number;
}

export interface SugerenciaArticulo {
  articulo_id: number;
  sucursal_id: number;
  cantidad_actual: string;
  lead_time_dias: number;
  velocidad: VelocidadVenta;
  stock_optimo_sugerido: string;
  stock_optimo_calculado: string | null;
}

export interface ReposicionItemArticulo {
  id: number;
  codigo: string;
  descripcion: string;
  unidad_medida: string;
  costo: string;
  controla_vencimiento: boolean;
}

export interface ReposicionItemSucursal {
  id: number;
  codigo: string;
  nombre: string;
}

export type UrgenciaReposicion = "critica" | "alta" | "media";

export interface ReposicionItem {
  articulo: ReposicionItemArticulo;
  sucursal: ReposicionItemSucursal;
  cantidad_actual: string;
  stock_minimo: string;
  punto_reorden: string;
  stock_maximo: string;
  cantidad_a_pedir: string;
  costo_unitario: string;
  total_linea: string;
  urgencia: UrgenciaReposicion;
  estado: EstadoReposicion;
}

export interface ReposicionProveedor {
  id: number;
  codigo: string;
  razon_social: string;
  cuit?: string | null;
  telefono?: string | null;
  email?: string | null;
  lead_time_dias_default?: number | null;
}

export interface ReposicionGrupo {
  proveedor: ReposicionProveedor | null;
  items: ReposicionItem[];
  total_items: number;
  total_estimado: string;
}

export interface ReposicionSugerencia {
  totales: {
    sucursales: number;
    articulos_a_reponer: number;
    valor_estimado: string;
  };
  por_proveedor: ReposicionGrupo[];
}

export interface OrdenCompraItem {
  articulo_id: number;
  cantidad: number | string;
  costo_unitario?: number | string;
}

export interface OrdenCompraPayload {
  proveedor_id?: number | null;
  sucursal_id: number;
  items: OrdenCompraItem[];
  fecha_estimada_recepcion?: string;
  observacion?: string;
}

export interface OrdenCompraResult {
  id: number;
  tipo: string;
  numero: number;
  punto_venta: number;
  estado: string;
  sucursal_id: number;
  subtotal: string;
  total_iva: string;
  total: string;
  items_count: number;
  proveedor_id: number | null;
  fecha_estimada_recepcion: string | null;
  created_at: string | null;
}

export interface RecalcularResult {
  filas_recalculadas: number;
  reorden_seteado: number;
  sin_velocidad: number;
}

// --- Alertas ---

export type TipoAlerta =
  | "pago_duplicado"
  | "factura_compra_repetida"
  | "items_repetidos_diff_nro"
  | "anulaciones_frecuentes"
  | "ajuste_stock_sospechoso"
  | "nota_credito_sospechosa"
  | "venta_fuera_horario"
  | "descuento_excesivo"
  | "vencimiento_proximo"
  | "stock_bajo_minimo"
  | "sobrestock"
  | "rotacion_lenta"
  | "rotacion_rapida_faltante";

export type Severidad = "baja" | "media" | "alta" | "critica";

export type EstadoAlerta =
  | "nueva"
  | "en_revision"
  | "descartada"
  | "confirmada"
  | "resuelta";

export interface Alerta {
  id: number;
  tipo: TipoAlerta;
  severidad: Severidad;
  estado: EstadoAlerta;
  titulo: string;
  descripcion: string;
  contexto: Record<string, unknown>;
  factura_id: number | null;
  user_relacionado_id: number | null;
  proveedor_id: number | null;
  sucursal_id: number | null;
  detected_at: string;
  resolved_at: string | null;
  resolved_by_user_id: number | null;
  nota_resolucion: string | null;
  deteccion_hash: string;
  created_at: string;
  updated_at: string;
}

export interface AlertaDetalle extends Alerta {
  factura: {
    id: number;
    tipo: string;
    numero: number;
    punto_venta: number;
    fecha: string;
    total: string;
    estado: string;
    sucursal_id: number;
    cliente_id: number | null;
    cajero_id: number;
  } | null;
  user_relacionado: {
    id: number;
    email: string;
    nombre: string;
    rol: string | null;
    sucursal_id: number | null;
  } | null;
  proveedor: {
    id: number;
    codigo: string;
    razon_social: string;
    cuit: string | null;
  } | null;
  sucursal: {
    id: number;
    codigo: string;
    nombre: string;
  } | null;
}

export interface AlertaResumen {
  nuevas: number;
  en_revision: number;
  criticas: number;
  ultimas_24h: number;
  total_abiertas: number;
}

export interface AlertaRunResult {
  creadas: number;
  detectores: number;
  detalle: Record<string, number>;
}

// --- Calendario de pagos ---

export type TipoCompromiso =
  | "factura_compra"
  | "cuenta_corriente_proveedor"
  | "tarjeta_corporativa"
  | "servicio"
  | "impuesto"
  | "otro";

export type EstadoCompromiso =
  | "pendiente"
  | "parcial"
  | "pagado"
  | "vencido"
  | "cancelado";

export interface CompromisoPago {
  id: number;
  tipo: TipoCompromiso;
  estado: EstadoCompromiso;
  descripcion: string;
  monto_total: string;
  monto_pagado: string;
  fecha_emision: string | null;
  fecha_vencimiento: string;
  fecha_pago_real: string | null;
  proveedor_id: number | null;
  factura_id: number | null;
  tarjeta_id: number | null;
  sucursal_id: number | null;
  creado_por_user_id: number;
  pagado_por_user_id: number | null;
  nota: string | null;
  created_at: string;
  updated_at: string;
}

export interface PagoCompromisoRow {
  id: number;
  compromiso_id: number;
  fecha_pago: string;
  monto: string;
  medio_pago: string;
  referencia: string | null;
  movimiento_caja_id: number | null;
  user_id: number;
  created_at: string;
}

export interface CompromisoDetalle extends CompromisoPago {
  pagos: PagoCompromisoRow[];
  proveedor_nombre: string | null;
  tarjeta_nombre: string | null;
}

export interface CompromisoResumen {
  vencidos: number;
  vence_hoy: number;
  esta_semana: number;
  este_mes: number;
  total_pendiente: string;
  total_vencido: string;
}

export interface CalendarDay {
  fecha: string;
  cantidad: number;
  monto_total: string;
  severidad_max: "baja" | "media" | "alta" | "critica";
  compromisos_ids: number[];
}

export interface CalendarResponse {
  items: CalendarDay[];
  mes: string;
}

export interface TarjetaCorporativa {
  id: number;
  nombre: string;
  banco: string | null;
  ultimos_4: string;
  titular: string | null;
  limite_total: string | null;
  dia_cierre: number;
  dia_vencimiento: number;
  activa: boolean;
  created_at: string;
  updated_at: string;
}

export interface TarjetasResponse {
  items: TarjetaCorporativa[];
}

export interface AutoGenerarResultado {
  creados: number;
  desde_facturas: number;
  desde_tarjetas: number;
}
