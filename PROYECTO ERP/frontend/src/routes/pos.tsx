import * as React from "react";
import { createRoute } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AxiosError } from "axios";
import {
  CheckCircle2,
  Keyboard,
  Loader2,
  Minus,
  Plus,
  Printer,
  Scale,
  Search,
  ShoppingCart,
  Trash2,
  User,
} from "lucide-react";
import {
  createFactura,
  type FacturaCreatePayload,
} from "@/api/facturas";
import { listArticulos } from "@/api/articulos";
import { listClientes } from "@/api/clientes";
import { listSucursales } from "@/api/sucursales";
import {
  previewUrl,
  printTicket,
  readWeight,
  tareScale,
} from "@/api/agent";
import { getComercio } from "@/api/comercio";
import { comercioToAgentPayload } from "@/api/comercio-context";
import { buildTicketPayload } from "@/lib/ticket-payload";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { WeighDialog } from "@/components/pos/weigh-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/store/auth";
import type {
  Articulo,
  Cliente,
  Factura,
  MedioPago,
  Sucursal,
  TipoComprobante,
} from "@/lib/types";
import { parseDecimal } from "@/lib/types";
import { cn } from "@/lib/utils";
import { appLayoutRoute } from "./app-layout";

export const posRoute = createRoute({
  getParentRoute: () => appLayoutRoute,
  path: "/pos",
  component: PosPage,
});

// ---------------------------------------------------------------------------
// Tipos + helpers
// ---------------------------------------------------------------------------

interface CartItem {
  articulo: Articulo;
  cantidad: number;
  precio_unitario: number;
  descuento_porc: number;
}

interface PagoRow {
  id: string;
  medio: MedioPago;
  monto: string; // string mientras se tipea
  referencia?: string;
}

const TIPOS_COMPROBANTE: { value: TipoComprobante; label: string }[] = [
  { value: "ticket", label: "Ticket" },
  { value: "factura_a", label: "Factura A" },
  { value: "factura_b", label: "Factura B" },
  { value: "factura_c", label: "Factura C" },
];

const MEDIOS_PAGO: { value: MedioPago; label: string }[] = [
  { value: "efectivo", label: "Efectivo" },
  { value: "tarjeta_debito", label: "Tarjeta débito" },
  { value: "tarjeta_credito", label: "Tarjeta crédito" },
  { value: "transferencia", label: "Transferencia" },
  { value: "qr_mercadopago", label: "QR MercadoPago" },
  { value: "qr_modo", label: "QR MODO" },
  { value: "cheque", label: "Cheque" },
  { value: "cuenta_corriente", label: "Cuenta corriente" },
  { value: "vale", label: "Vale" },
];

function formatMoney(v: number): string {
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(v);
}

function itemSubtotal(it: CartItem): number {
  const bruto = it.cantidad * it.precio_unitario;
  const descuento = bruto * (it.descuento_porc / 100);
  return bruto - descuento;
}

function itemTotal(it: CartItem, ivaPorc: number): number {
  const sub = itemSubtotal(it);
  return sub + sub * (ivaPorc / 100);
}

function getIvaPorc(a: Articulo): number {
  return parseDecimal(a.iva_porc) ?? 21;
}

/**
 * El artículo se vende por peso? (unidad_medida = kg | gr).
 * Litros y mililitros NO se pesan — quedan como cantidad manual.
 */
function isWeightArticulo(a: Articulo): boolean {
  const u = (a.unidad_medida ?? "").toLowerCase();
  return u === "kg" || u === "gr";
}

/**
 * Convierte el peso leído (siempre en kg desde el agente) a la unidad del
 * artículo. Si el artículo se vende en gramos, multiplicamos por 1000.
 */
function weightKgToCantidad(kg: number, a: Articulo): number {
  const u = (a.unidad_medida ?? "").toLowerCase();
  if (u === "gr") return Math.round(kg * 1000);
  // 3 decimales para kg.
  return Math.round(kg * 1000) / 1000;
}

function newId(): string {
  return Math.random().toString(36).slice(2, 10);
}

// ---------------------------------------------------------------------------
// Buscador de artículos
// ---------------------------------------------------------------------------

interface PosArticleSearchProps {
  onAdd: (articulo: Articulo) => void;
}

const PosArticleSearch = React.forwardRef<HTMLInputElement, PosArticleSearchProps>(
  function PosArticleSearch({ onAdd }, ref) {
    const [query, setQuery] = React.useState("");
    const [debounced, setDebounced] = React.useState("");

    React.useEffect(() => {
      const id = setTimeout(() => setDebounced(query), 200);
      return () => clearTimeout(id);
    }, [query]);

    const { data } = useQuery({
      queryKey: ["pos-search", debounced],
      queryFn: () =>
        listArticulos({ q: debounced || undefined, per_page: 10 }),
      enabled: debounced.length > 0,
    });

    const items = data?.items ?? [];

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        e.preventDefault();
        const q = query.trim();
        if (!q) return;
        // Si hay match exacto por código o código_barras → agregar.
        const exact = items.find(
          (a) => a.codigo === q || a.codigo_barras === q,
        );
        if (exact) {
          onAdd(exact);
          setQuery("");
          return;
        }
        if (items.length === 1) {
          onAdd(items[0]);
          setQuery("");
        }
      }
      if (e.key === "Escape") {
        setQuery("");
      }
    };

    return (
      <div className="flex flex-col gap-2">
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-[16px] w-[16px] text-muted-foreground"
            strokeWidth={1.5}
          />
          <Input
            ref={ref}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Escaneá o buscá por código, código de barras o descripción"
            className="h-11 pl-9"
            autoFocus
          />
        </div>
        {debounced && items.length > 0 && (
          <Card className="divide-y divide-border overflow-hidden p-0">
            {items.slice(0, 6).map((a) => (
              <button
                key={a.id}
                type="button"
                onClick={() => {
                  onAdd(a);
                  setQuery("");
                }}
                className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left transition-colors hover:bg-muted/50"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13px] font-medium">
                    {a.descripcion}
                  </p>
                  <p className="text-[11px] text-muted-foreground font-mono">
                    {a.codigo}
                    {a.codigo_barras && ` · ${a.codigo_barras}`}
                  </p>
                </div>
                <span className="tabular-nums text-[13px] font-medium">
                  {formatMoney(parseDecimal(a.pvp_base) ?? 0)}
                </span>
              </button>
            ))}
          </Card>
        )}
      </div>
    );
  },
);

// ---------------------------------------------------------------------------
// Selector de cliente
// ---------------------------------------------------------------------------

interface PosCustomerSelectorProps {
  cliente: Cliente | null;
  onChange: (c: Cliente | null) => void;
  openSignal: number;
}

function PosCustomerSelector({
  cliente,
  onChange,
  openSignal,
}: PosCustomerSelectorProps) {
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");

  React.useEffect(() => {
    if (openSignal > 0) setOpen(true);
  }, [openSignal]);

  const { data } = useQuery({
    queryKey: ["pos-clientes", query],
    queryFn: () => listClientes({ q: query || undefined, per_page: 20 }),
    enabled: open,
  });

  const items = data?.items ?? [];

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        onClick={() => setOpen(true)}
        className="h-10 w-full justify-start gap-2 font-normal"
      >
        <User className="h-4 w-4" strokeWidth={1.5} />
        <span className="truncate">
          {cliente ? cliente.razon_social : "Consumidor Final"}
        </span>
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Seleccionar cliente</DialogTitle>
            <DialogDescription>
              Dejá en blanco para Consumidor Final.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-3">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Buscar por razón social, CUIT o código"
              autoFocus
            />
            <div className="max-h-[320px] overflow-y-auto divide-y divide-border rounded-[10px] border border-border">
              <button
                type="button"
                onClick={() => {
                  onChange(null);
                  setOpen(false);
                }}
                className="flex w-full items-center justify-between px-3 py-2.5 text-left transition-colors hover:bg-muted/50"
              >
                <span className="text-[13px] font-medium">
                  Consumidor Final
                </span>
                <span className="text-[11px] text-muted-foreground">
                  por defecto
                </span>
              </button>
              {items.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => {
                    onChange(c);
                    setOpen(false);
                  }}
                  className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left transition-colors hover:bg-muted/50"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-medium">
                      {c.razon_social}
                    </p>
                    <p className="text-[11px] text-muted-foreground font-mono">
                      {c.codigo}
                      {c.cuit && ` · ${c.cuit}`}
                    </p>
                  </div>
                  <span className="text-[11px] text-muted-foreground capitalize">
                    {c.condicion_iva.replace(/_/g, " ")}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ---------------------------------------------------------------------------
// Medios de pago
// ---------------------------------------------------------------------------

interface PosPaymentsProps {
  pagos: PagoRow[];
  total: number;
  onChange: (rows: PagoRow[]) => void;
}

function PosPayments({ pagos, total, onChange }: PosPaymentsProps) {
  const sumaPagada = pagos.reduce(
    (acc, p) => acc + (parseFloat(p.monto) || 0),
    0,
  );
  const faltante = Math.max(0, total - sumaPagada);

  const addRow = (medio: MedioPago) => {
    onChange([
      ...pagos,
      { id: newId(), medio, monto: faltante > 0 ? faltante.toFixed(2) : "" },
    ]);
  };

  const updateRow = (id: string, patch: Partial<PagoRow>) => {
    onChange(pagos.map((p) => (p.id === id ? { ...p, ...patch } : p)));
  };

  const removeRow = (id: string) => {
    onChange(pagos.filter((p) => p.id !== id));
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <Label className="text-[13px] font-medium">Medios de pago</Label>
        <span
          className={cn(
            "text-[12px] tabular-nums",
            Math.abs(sumaPagada - total) < 0.01
              ? "text-emerald-500"
              : "text-muted-foreground",
          )}
        >
          Pagado {formatMoney(sumaPagada)} / {formatMoney(total)}
        </span>
      </div>

      {pagos.length > 0 && (
        <div className="flex flex-col gap-2">
          {pagos.map((p) => (
            <div key={p.id} className="flex items-center gap-2">
              <select
                value={p.medio}
                onChange={(e) =>
                  updateRow(p.id, { medio: e.target.value as MedioPago })
                }
                className="h-10 rounded-[8px] border border-border bg-background px-3 text-[13px] focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {MEDIOS_PAGO.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </select>
              <Input
                type="number"
                step="0.01"
                min="0"
                value={p.monto}
                onChange={(e) => updateRow(p.id, { monto: e.target.value })}
                placeholder="0.00"
                className="h-10 w-32 text-right tabular-nums"
              />
              <Button
                variant="ghost"
                size="icon"
                onClick={() => removeRow(p.id)}
                aria-label="Quitar pago"
              >
                <Trash2 className="h-4 w-4" strokeWidth={1.5} />
              </Button>
            </div>
          ))}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => addRow("efectivo")}
          className="text-[12px]"
        >
          + Efectivo
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => addRow("tarjeta_debito")}
          className="text-[12px]"
        >
          + Débito
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => addRow("tarjeta_credito")}
          className="text-[12px]"
        >
          + Crédito
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => addRow("transferencia")}
          className="text-[12px]"
        >
          + Transferencia
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Carrito
// ---------------------------------------------------------------------------

interface PosCartProps {
  items: CartItem[];
  onUpdateQty: (idx: number, qty: number) => void;
  onRemove: (idx: number) => void;
  onWeigh: (idx: number) => void;
}

function PosCart({ items, onUpdateQty, onRemove, onWeigh }: PosCartProps) {
  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-center">
        <div className="rounded-full bg-muted/60 p-3">
          <ShoppingCart
            className="h-6 w-6 text-muted-foreground"
            strokeWidth={1.5}
          />
        </div>
        <p className="text-[13px] text-muted-foreground">
          Agregá artículos desde el buscador.
        </p>
      </div>
    );
  }

  return (
    <div className="divide-y divide-border">
      {items.map((it, idx) => {
        const iva = getIvaPorc(it.articulo);
        const total = itemTotal(it, iva);
        const weighable = isWeightArticulo(it.articulo);
        const unidad = (it.articulo.unidad_medida ?? "").toLowerCase();
        const step = weighable ? (unidad === "gr" ? "1" : "0.001") : "1";
        const min = weighable ? "0.001" : "1";

        return (
          <div key={`${it.articulo.id}-${idx}`} className="py-3 flex flex-col gap-1">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] font-medium">
                  {it.articulo.descripcion}
                  {weighable && (
                    <span className="ml-2 inline-flex items-center gap-1 rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-normal text-muted-foreground">
                      <Scale className="h-2.5 w-2.5" strokeWidth={1.5} />
                      {unidad}
                    </span>
                  )}
                </p>
                <p className="text-[11px] text-muted-foreground font-mono">
                  {it.articulo.codigo}
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => onRemove(idx)}
                aria-label="Quitar"
                className="h-8 w-8"
              >
                <Trash2 className="h-4 w-4" strokeWidth={1.5} />
              </Button>
            </div>
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-1.5">
                {!weighable && (
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() =>
                      onUpdateQty(idx, Math.max(1, it.cantidad - 1))
                    }
                    aria-label="Menos"
                    className="h-8 w-8"
                  >
                    <Minus className="h-3 w-3" strokeWidth={1.5} />
                  </Button>
                )}
                <Input
                  type="number"
                  min={min}
                  step={step}
                  value={it.cantidad}
                  onChange={(e) => {
                    const n = parseFloat(e.target.value);
                    if (Number.isFinite(n) && n > 0) onUpdateQty(idx, n);
                  }}
                  className={cn(
                    "h-8 text-center tabular-nums",
                    weighable ? "w-24" : "w-16",
                  )}
                />
                {!weighable && (
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => onUpdateQty(idx, it.cantidad + 1)}
                    aria-label="Más"
                    className="h-8 w-8"
                  >
                    <Plus className="h-3 w-3" strokeWidth={1.5} />
                  </Button>
                )}
                {weighable && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onWeigh(idx)}
                    className="h-8 gap-1.5 px-2.5 text-[12px]"
                    title="Pesar con balanza (F4)"
                  >
                    <Scale className="h-3.5 w-3.5" strokeWidth={1.5} />
                    Pesar
                  </Button>
                )}
              </div>
              <div className="flex flex-col items-end">
                <span className="text-[12px] text-muted-foreground tabular-nums">
                  {formatMoney(it.precio_unitario)} c/{unidad || "u"}
                </span>
                <span className="text-[14px] font-semibold tabular-nums">
                  {formatMoney(total)}
                </span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

function PosPage() {
  const { toast } = useToast();
  const authUser = useAuth((s) => s.user);

  const { data: sucursales = [] } = useQuery({
    queryKey: ["sucursales"],
    queryFn: listSucursales,
  });

  const { data: comercio } = useQuery({
    queryKey: ["comercio"],
    queryFn: getComercio,
    staleTime: 5 * 60_000,
  });

  const [sucursalId, setSucursalId] = React.useState<number | null>(null);
  const [cliente, setCliente] = React.useState<Cliente | null>(null);
  const [tipo, setTipo] = React.useState<TipoComprobante>("ticket");
  const [items, setItems] = React.useState<CartItem[]>([]);
  const [pagos, setPagos] = React.useState<PagoRow[]>([]);
  const [observacion, setObservacion] = React.useState("");
  const [clienteOpenSignal, setClienteOpenSignal] = React.useState(0);
  const [lastFactura, setLastFactura] = React.useState<Factura | null>(null);
  const [showSuccessDialog, setShowSuccessDialog] = React.useState(false);
  const [weighIdx, setWeighIdx] = React.useState<number | null>(null);

  const searchRef = React.useRef<HTMLInputElement>(null);

  // Default sucursal: la del user, si tiene; si no, la primera activa.
  React.useEffect(() => {
    if (sucursalId !== null) return;
    if (authUser?.sucursal_id) {
      setSucursalId(authUser.sucursal_id);
      return;
    }
    const activa = sucursales.find((s) => s.activa);
    if (activa) setSucursalId(activa.id);
  }, [sucursalId, sucursales, authUser]);

  // ----- Totales calculados
  const totales = React.useMemo(() => {
    let subtotal = 0;
    let iva = 0;
    let descuento = 0;
    let iva21 = 0;
    let iva105 = 0;
    let ivaOtros = 0;
    for (const it of items) {
      const ivaPorc = getIvaPorc(it.articulo);
      const bruto = it.cantidad * it.precio_unitario;
      const desc = bruto * (it.descuento_porc / 100);
      const sub = bruto - desc;
      const ivaMonto = sub * (ivaPorc / 100);
      subtotal += sub;
      iva += ivaMonto;
      descuento += desc;
      if (ivaPorc === 21) iva21 += ivaMonto;
      else if (ivaPorc === 10.5) iva105 += ivaMonto;
      else ivaOtros += ivaMonto;
    }
    return {
      subtotal: Number(subtotal.toFixed(2)),
      iva: Number(iva.toFixed(2)),
      descuento: Number(descuento.toFixed(2)),
      total: Number((subtotal + iva).toFixed(2)),
      iva21: Number(iva21.toFixed(2)),
      iva105: Number(iva105.toFixed(2)),
      ivaOtros: Number(ivaOtros.toFixed(2)),
    };
  }, [items]);

  const sumaPagos = React.useMemo(
    () => pagos.reduce((acc, p) => acc + (parseFloat(p.monto) || 0), 0),
    [pagos],
  );

  const puedeFinalizar =
    sucursalId !== null &&
    items.length > 0 &&
    pagos.length > 0 &&
    pagos.every((p) => parseFloat(p.monto) > 0) &&
    Math.abs(sumaPagos - totales.total) < 0.01;

  // ----- Acciones
  const addArticulo = (articulo: Articulo) => {
    setItems((prev) => {
      const existingIdx = prev.findIndex(
        (it) => it.articulo.id === articulo.id,
      );
      if (existingIdx >= 0) {
        return prev.map((it, i) =>
          i === existingIdx ? { ...it, cantidad: it.cantidad + 1 } : it,
        );
      }
      return [
        ...prev,
        {
          articulo,
          cantidad: 1,
          precio_unitario: parseDecimal(articulo.pvp_base) ?? 0,
          descuento_porc: 0,
        },
      ];
    });
  };

  const updateQty = (idx: number, qty: number) => {
    setItems((prev) =>
      prev.map((it, i) => (i === idx ? { ...it, cantidad: qty } : it)),
    );
  };

  const removeItem = (idx: number) => {
    setItems((prev) => prev.filter((_, i) => i !== idx));
  };

  const resetVenta = () => {
    setItems([]);
    setPagos([]);
    setObservacion("");
    setCliente(null);
    setTipo("ticket");
    setTimeout(() => searchRef.current?.focus(), 50);
  };

  // ----- Mutación de venta
  // Recordamos el cliente usado para imprimir post-venta sin perderlo en resetVenta()
  const lastClienteRef = React.useRef<Cliente | null>(null);

  const mutation = useMutation({
    mutationFn: async (): Promise<Factura> => {
      if (sucursalId === null) throw new Error("sucursal requerida");
      const payload: FacturaCreatePayload = {
        sucursal_id: sucursalId,
        punto_venta: 1,
        tipo,
        cliente_id: cliente?.id ?? null,
        observacion: observacion.trim() || null,
        items: items.map((it) => ({
          articulo_id: it.articulo.id,
          cantidad: it.cantidad.toString(),
          precio_unitario: it.precio_unitario.toString(),
          descuento_porc: it.descuento_porc.toString(),
        })),
        pagos: pagos.map((p) => ({
          medio: p.medio,
          monto: parseFloat(p.monto).toFixed(2),
          referencia: p.referencia ?? null,
        })),
      };
      return await createFactura(payload);
    },
    onSuccess: (factura) => {
      setLastFactura(factura);
      lastClienteRef.current = cliente;
      setShowSuccessDialog(true);
      toast({
        title: `Venta #${factura.numero} emitida`,
        description: `${formatMoney(parseFloat(factura.total))} · ${factura.tipo.replace("_", " ")}`,
      });
    },
    onError: (err: AxiosError<{ error?: string }>) => {
      const msg =
        err.response?.data?.error ?? err.message ?? "Error desconocido";
      toast({
        title: "No se pudo emitir",
        description: msg,
        variant: "destructive",
      });
    },
  });

  // ----- Mutación de impresión (agente local)
  const printMutation = useMutation({
    mutationFn: async (factura: Factura) => {
      const sucursalActual =
        sucursales.find((s) => s.id === factura.sucursal_id) ?? null;
      const payload = buildTicketPayload({
        factura,
        sucursal: sucursalActual,
        cliente: lastClienteRef.current,
        cajero: authUser
          ? { nombre: authUser.nombre, email: authUser.email }
          : null,
        comercio: comercioToAgentPayload(comercio),
      });
      return await printTicket(payload);
    },
    onSuccess: (resp) => {
      if (resp.preview_url && resp.preview_id) {
        // Modo mock: abrimos el PDF en otra pestaña.
        window.open(previewUrl(resp.preview_id), "_blank", "noopener");
      }
      toast({
        title: "Ticket enviado a impresora",
        description: resp.driver === "mock"
          ? `Preview PDF generado · ${resp.duration_ms}ms`
          : `Driver ${resp.driver} · ${resp.duration_ms}ms`,
      });
    },
    onError: (err: AxiosError<{ error?: string }>) => {
      const msg =
        err.response?.data?.error ??
        err.message ??
        "No se pudo contactar al agente local";
      toast({
        title: "No se pudo imprimir",
        description: `${msg}. Verificá que el agente corra en :9123.`,
        variant: "destructive",
      });
    },
  });

  const handleFinalizar = () => {
    if (!puedeFinalizar || mutation.isPending) return;
    mutation.mutate();
  };

  // ----- Balanza
  // Intento de lectura rápida (autocomplete inline). Si la balanza responde
  // y el peso es estable, lo aplicamos directo. Si no, abrimos el modal para
  // que el cajero confirme visualmente.
  const handleWeigh = async (idx: number) => {
    const item = items[idx];
    if (!item) return;
    try {
      const reading = await readWeight();
      const kg = parseFloat(reading.weight_kg);
      if (!Number.isFinite(kg) || kg <= 0) {
        setWeighIdx(idx);
        return;
      }
      if (!reading.stable) {
        toast({
          title: "Peso no estable",
          description:
            "Esperá un momento a que la balanza se asiente antes de confirmar.",
        });
        setWeighIdx(idx);
        return;
      }
      const cantidad = weightKgToCantidad(kg, item.articulo);
      updateQty(idx, cantidad);
      toast({
        title: "Peso cargado",
        description: `${reading.weight_kg} kg → ${cantidad} ${item.articulo.unidad_medida ?? ""}`,
      });
    } catch {
      toast({
        title: "Balanza no responde",
        description:
          "No se pudo leer el peso — modo manual o revisá el agente.",
        variant: "destructive",
      });
    }
  };

  const handleConfirmWeight = (kg: number) => {
    if (weighIdx === null) return;
    const item = items[weighIdx];
    if (!item) return;
    const cantidad = weightKgToCantidad(kg, item.articulo);
    updateQty(weighIdx, cantidad);
    toast({
      title: "Peso cargado",
      description: `${kg.toFixed(3)} kg → ${cantidad} ${item.articulo.unidad_medida ?? ""}`,
    });
  };

  const tareMutation = useMutation({
    mutationFn: tareScale,
    onSuccess: () => {
      toast({
        title: "Balanza en cero",
        description: "Tara aplicada correctamente.",
      });
    },
    onError: () => {
      toast({
        title: "No se pudo tarar",
        description: "Verificá la balanza o el agente local.",
        variant: "destructive",
      });
    },
  });

  // ----- Atajos de teclado
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Evitar interceptar cuando el user está tipeando en un input
      const target = e.target as HTMLElement | null;
      const typing =
        target?.tagName === "INPUT" ||
        target?.tagName === "TEXTAREA" ||
        target?.tagName === "SELECT";

      if (e.key === "F2") {
        e.preventDefault();
        searchRef.current?.focus();
      } else if (e.key === "F4") {
        e.preventDefault();
        // Pesar la última fila kg/gr del carrito (la más reciente).
        for (let i = items.length - 1; i >= 0; i--) {
          if (isWeightArticulo(items[i].articulo)) {
            void handleWeigh(i);
            break;
          }
        }
      } else if (e.key === "F8") {
        e.preventDefault();
        // Pagar todo en efectivo con el faltante.
        const faltante = totales.total - sumaPagos;
        if (faltante > 0) {
          setPagos((prev) => [
            ...prev,
            {
              id: newId(),
              medio: "efectivo",
              monto: faltante.toFixed(2),
            },
          ]);
        }
      } else if (e.key === "F9") {
        e.preventDefault();
        setClienteOpenSignal((n) => n + 1);
      } else if (e.key === "F12") {
        e.preventDefault();
        handleFinalizar();
      } else if (e.key === "Escape" && !typing) {
        // nada
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [puedeFinalizar, totales.total, sumaPagos, mutation.isPending, items]);

  const sucursalActual = sucursales.find((s) => s.id === sucursalId);

  return (
    <div className="flex flex-col gap-6 max-w-[1440px]">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-[28px] font-semibold tracking-tight leading-tight">
            Punto de venta
          </h2>
          <p className="mt-1.5 text-[14px] text-muted-foreground">
            Armá la venta, cargá el pago y emití el comprobante.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex flex-col gap-1">
            <Label className="text-[11px] uppercase tracking-wider text-muted-foreground">
              Sucursal
            </Label>
            <select
              value={sucursalId ?? ""}
              onChange={(e) => setSucursalId(Number(e.target.value))}
              className="h-10 rounded-[8px] border border-border bg-background px-3 text-[13px] min-w-[200px] focus:outline-none focus:ring-2 focus:ring-ring"
            >
              {sucursales
                .filter((s) => s.activa)
                .map((s: Sucursal) => (
                  <option key={s.id} value={s.id}>
                    {s.nombre}
                  </option>
                ))}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <Label className="text-[11px] uppercase tracking-wider text-muted-foreground">
              Comprobante
            </Label>
            <select
              value={tipo}
              onChange={(e) => setTipo(e.target.value as TipoComprobante)}
              className="h-10 rounded-[8px] border border-border bg-background px-3 text-[13px] min-w-[160px] focus:outline-none focus:ring-2 focus:ring-ring"
            >
              {TIPOS_COMPROBANTE.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Grid principal */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Columna izquierda: buscador + carrito + cliente + pagos */}
        <div className="lg:col-span-3 flex flex-col gap-5">
          <PosArticleSearch ref={searchRef} onAdd={addArticulo} />

          <Card className="p-5">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-[14px] font-semibold tracking-tight">
                Carrito
              </h3>
              <span className="text-[11px] text-muted-foreground tabular-nums">
                {items.length} {items.length === 1 ? "ítem" : "ítems"}
              </span>
            </div>
            <PosCart
              items={items}
              onUpdateQty={updateQty}
              onRemove={removeItem}
              onWeigh={(idx) => void handleWeigh(idx)}
            />
          </Card>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card className="p-5">
              <Label className="text-[11px] uppercase tracking-wider text-muted-foreground mb-2 block">
                Cliente
              </Label>
              <PosCustomerSelector
                cliente={cliente}
                onChange={setCliente}
                openSignal={clienteOpenSignal}
              />
            </Card>
            <Card className="p-5">
              <Label className="text-[11px] uppercase tracking-wider text-muted-foreground mb-2 block">
                Observación
              </Label>
              <Input
                value={observacion}
                onChange={(e) => setObservacion(e.target.value)}
                placeholder="Opcional"
                className="h-10"
              />
            </Card>
          </div>

          <Card className="p-5">
            <PosPayments
              pagos={pagos}
              total={totales.total}
              onChange={setPagos}
            />
          </Card>

          {items.some((it) => isWeightArticulo(it.articulo)) && (
            <div className="flex items-center justify-end">
              <Button
                variant="outline"
                size="sm"
                onClick={() => tareMutation.mutate()}
                disabled={tareMutation.isPending}
                className="h-8 gap-1.5 text-[12px]"
                title="Tarar balanza (poner en cero)"
              >
                {tareMutation.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={1.5} />
                ) : (
                  <Scale className="h-3.5 w-3.5" strokeWidth={1.5} />
                )}
                Tarar balanza
              </Button>
            </div>
          )}
        </div>

        {/* Columna derecha: totales + finalizar */}
        <div className="lg:col-span-2 flex flex-col gap-4">
          <Card className="p-6 sticky top-6">
            <div className="flex flex-col gap-4">
              <div>
                <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
                  {sucursalActual?.nombre ?? "—"}
                </span>
                <h3 className="text-[15px] font-semibold tracking-tight mt-0.5">
                  Resumen
                </h3>
              </div>

              <div className="flex flex-col gap-2 text-[13px]">
                <div className="flex justify-between text-muted-foreground">
                  <span>Subtotal</span>
                  <span className="tabular-nums">
                    {formatMoney(totales.subtotal)}
                  </span>
                </div>
                {totales.descuento > 0 && (
                  <div className="flex justify-between text-muted-foreground">
                    <span>Descuento</span>
                    <span className="tabular-nums">
                      −{formatMoney(totales.descuento)}
                    </span>
                  </div>
                )}
                {totales.iva21 > 0 && (
                  <div className="flex justify-between text-muted-foreground">
                    <span>IVA 21%</span>
                    <span className="tabular-nums">
                      {formatMoney(totales.iva21)}
                    </span>
                  </div>
                )}
                {totales.iva105 > 0 && (
                  <div className="flex justify-between text-muted-foreground">
                    <span>IVA 10.5%</span>
                    <span className="tabular-nums">
                      {formatMoney(totales.iva105)}
                    </span>
                  </div>
                )}
                {totales.ivaOtros > 0 && (
                  <div className="flex justify-between text-muted-foreground">
                    <span>Otros IVA</span>
                    <span className="tabular-nums">
                      {formatMoney(totales.ivaOtros)}
                    </span>
                  </div>
                )}
              </div>

              <div className="pt-3 border-t border-border">
                <div className="flex items-baseline justify-between">
                  <span className="text-[13px] font-medium">Total</span>
                  <span className="text-[32px] font-semibold tabular-nums tracking-tight">
                    {formatMoney(totales.total)}
                  </span>
                </div>
              </div>

              <Button
                size="lg"
                onClick={handleFinalizar}
                disabled={!puedeFinalizar || mutation.isPending}
                className="h-12"
              >
                {mutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.5} />
                    Emitiendo…
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="h-4 w-4" strokeWidth={1.5} />
                    Finalizar venta
                  </>
                )}
              </Button>

              <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                <Keyboard className="h-3 w-3" strokeWidth={1.5} />
                <span>
                  F2 buscar · F4 pesar · F8 efectivo · F9 cliente · F12 finalizar
                </span>
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* Dialog de pesaje */}
      {weighIdx !== null && items[weighIdx] && (
        <WeighDialog
          open={weighIdx !== null}
          onOpenChange={(open) => {
            if (!open) setWeighIdx(null);
          }}
          articuloDescripcion={items[weighIdx].articulo.descripcion}
          onConfirm={handleConfirmWeight}
        />
      )}

      {/* Dialog de éxito */}
      <Dialog open={showSuccessDialog} onOpenChange={setShowSuccessDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <CheckCircle2
                className="h-5 w-5 text-emerald-500"
                strokeWidth={1.5}
              />
              Venta emitida
            </DialogTitle>
            <DialogDescription>
              {lastFactura &&
                `${lastFactura.tipo.replace(/_/g, " ")} ${String(lastFactura.punto_venta).padStart(4, "0")}-${String(lastFactura.numero).padStart(8, "0")}`}
            </DialogDescription>
          </DialogHeader>
          {lastFactura && (
            <div className="flex flex-col gap-3">
              <div className="rounded-[10px] border border-border bg-muted/30 p-4">
                <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
                  Total cobrado
                </div>
                <div className="text-[28px] font-semibold tabular-nums tracking-tight">
                  {formatMoney(parseFloat(lastFactura.total))}
                </div>
              </div>
              {lastFactura.cae && (
                <div className="text-[12px] text-muted-foreground">
                  CAE {lastFactura.cae} · vence{" "}
                  {lastFactura.cae_vencimiento}
                </div>
              )}
            </div>
          )}
          <DialogFooter className="sm:justify-between gap-2">
            <Button
              variant="outline"
              onClick={() => {
                if (!lastFactura) return;
                printMutation.mutate(lastFactura);
              }}
              disabled={!lastFactura || printMutation.isPending}
            >
              {printMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.5} />
                  Imprimiendo…
                </>
              ) : (
                <>
                  <Printer className="h-4 w-4" strokeWidth={1.5} />
                  Imprimir ticket
                </>
              )}
            </Button>
            <Button
              onClick={() => {
                setShowSuccessDialog(false);
                resetVenta();
              }}
            >
              Nueva venta
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
