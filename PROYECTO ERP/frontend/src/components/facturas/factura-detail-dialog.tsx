import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AxiosError } from "axios";
import {
  CheckCircle2,
  ExternalLink,
  Loader2,
  Printer,
  ShieldOff,
  Sparkles,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { AlertDialog } from "@/components/ui/alert-dialog";
import {
  anularFactura,
  emitirCae,
  getFactura,
} from "@/api/facturas";
import { listSucursales } from "@/api/sucursales";
import { listClientes } from "@/api/clientes";
import { previewUrl, printTicket } from "@/api/agent";
import { getComercio } from "@/api/comercio";
import { comercioToAgentPayload } from "@/api/comercio-context";
import { buildTicketPayload } from "@/lib/ticket-payload";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/store/auth";
import type { Factura } from "@/lib/types";
import { parseDecimal } from "@/lib/types";
import {
  comprobanteLabel,
  formatComprobanteNumero,
  formatDateLong,
  formatMoney,
  medioPagoLabel,
  tipoComprobanteBadgeVariant,
} from "./format";

interface FacturaDetailDialogProps {
  facturaId: number | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function FacturaDetailDialog({
  facturaId,
  open,
  onOpenChange,
}: FacturaDetailDialogProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const authUser = useAuth((s) => s.user);
  const isAdminLike =
    authUser?.rol === "admin" || authUser?.rol === "supervisor";

  const [confirmAnular, setConfirmAnular] = React.useState(false);
  const [confirmCae, setConfirmCae] = React.useState(false);

  const { data: factura, isLoading } = useQuery({
    queryKey: ["factura", facturaId],
    queryFn: () => getFactura(facturaId as number),
    enabled: open && facturaId !== null,
  });

  const { data: sucursales = [] } = useQuery({
    queryKey: ["sucursales"],
    queryFn: listSucursales,
    enabled: open,
  });

  const { data: clientesData } = useQuery({
    queryKey: ["clientes-detail", factura?.cliente_id],
    queryFn: async () => {
      if (!factura?.cliente_id) return null;
      const all = await listClientes({ per_page: 200 });
      return all.items.find((c) => c.id === factura.cliente_id) ?? null;
    },
    enabled: open && Boolean(factura?.cliente_id),
  });

  const cliente = clientesData ?? null;
  const sucursal = factura
    ? sucursales.find((s) => s.id === factura.sucursal_id) ?? null
    : null;

  const { data: comercio } = useQuery({
    queryKey: ["comercio"],
    queryFn: getComercio,
    enabled: open,
    staleTime: 5 * 60_000,
  });

  // ---- print
  const printMutation = useMutation({
    mutationFn: async (f: Factura) => {
      const payload = buildTicketPayload({
        factura: f,
        sucursal,
        cliente,
        cajero: authUser
          ? { nombre: authUser.nombre, email: authUser.email }
          : null,
        comercio: comercioToAgentPayload(comercio),
      });
      return await printTicket(payload);
    },
    onSuccess: (resp) => {
      if (resp.preview_url && resp.preview_id) {
        window.open(previewUrl(resp.preview_id), "_blank", "noopener");
      }
      toast({
        title: "Ticket enviado a impresión",
        description:
          resp.driver === "mock"
            ? `Preview PDF generado · ${resp.duration_ms}ms`
            : `Driver ${resp.driver} · ${resp.duration_ms}ms`,
      });
    },
    onError: (err: AxiosError<{ error?: string }>) => {
      toast({
        title: "No se pudo imprimir",
        description: `${err.response?.data?.error ?? err.message}. Verificá que el agente local corra en :9123.`,
        variant: "destructive",
      });
    },
  });

  // ---- anular
  const anularMutation = useMutation({
    mutationFn: () => anularFactura(facturaId as number),
    onSuccess: () => {
      toast({
        title: "Factura anulada",
        description: "El comprobante fue anulado.",
      });
      queryClient.invalidateQueries({ queryKey: ["facturas"] });
      queryClient.invalidateQueries({ queryKey: ["factura", facturaId] });
      setConfirmAnular(false);
    },
    onError: (err: AxiosError<{ error?: string }>) => {
      toast({
        title: "No se pudo anular",
        description: err.response?.data?.error ?? err.message,
        variant: "destructive",
      });
    },
  });

  // ---- emitir CAE
  const emitirCaeMutation = useMutation({
    mutationFn: () => emitirCae(facturaId as number),
    onSuccess: (resp) => {
      toast({
        title: "CAE emitido",
        description: `CAE ${resp.cae} · vence ${resp.fecha_vencimiento}`,
      });
      queryClient.invalidateQueries({ queryKey: ["facturas"] });
      queryClient.invalidateQueries({ queryKey: ["factura", facturaId] });
      setConfirmCae(false);
    },
    onError: (err: AxiosError<{ error?: string }>) => {
      toast({
        title: "No se pudo emitir CAE",
        description: err.response?.data?.error ?? err.message,
        variant: "destructive",
      });
    },
  });

  const tipoRequiereCae = (t: string) =>
    t === "factura_a" || t === "factura_b" || t === "factura_c";

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-[820px] max-h-[88vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="sr-only">Detalle de comprobante</DialogTitle>
          </DialogHeader>

          {isLoading || !factura ? (
            <div className="flex flex-col gap-3">
              <Skeleton className="h-8 w-3/4" />
              <Skeleton className="h-5 w-1/2" />
              <Skeleton className="h-40 w-full" />
            </div>
          ) : (
            <FacturaDetailContent
              factura={factura}
              sucursalNombre={sucursal?.nombre ?? null}
              sucursalCodigo={sucursal?.codigo ?? null}
              clienteRazonSocial={cliente?.razon_social ?? null}
              clienteCuit={cliente?.cuit ?? null}
              clienteCondicionIva={cliente?.condicion_iva ?? null}
              actions={
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => printMutation.mutate(factura)}
                    disabled={printMutation.isPending}
                  >
                    {printMutation.isPending ? (
                      <Loader2
                        className="h-4 w-4 animate-spin"
                        strokeWidth={1.5}
                      />
                    ) : (
                      <Printer className="h-4 w-4" strokeWidth={1.5} />
                    )}
                    Reimprimir ticket
                  </Button>

                  {!factura.cae &&
                    tipoRequiereCae(factura.tipo) &&
                    factura.estado !== "anulada" &&
                    isAdminLike && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setConfirmCae(true)}
                        disabled={emitirCaeMutation.isPending}
                      >
                        <Sparkles className="h-4 w-4" strokeWidth={1.5} />
                        Emitir CAE
                      </Button>
                    )}

                  {factura.estado !== "anulada" && isAdminLike && (
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => setConfirmAnular(true)}
                      disabled={anularMutation.isPending}
                    >
                      <ShieldOff className="h-4 w-4" strokeWidth={1.5} />
                      Anular
                    </Button>
                  )}
                </div>
              }
            />
          )}
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={confirmAnular}
        onOpenChange={setConfirmAnular}
        destructive
        title="¿Anular este comprobante?"
        description="Esta acción es irreversible. Se generará un movimiento de devolución y el stock volverá al inventario."
        confirmLabel={anularMutation.isPending ? "Anulando…" : "Anular"}
        cancelLabel="Cancelar"
        onConfirm={() => anularMutation.mutate()}
        loading={anularMutation.isPending}
      />

      <AlertDialog
        open={confirmCae}
        onOpenChange={setConfirmCae}
        title="¿Emitir CAE para esta factura?"
        description="Se solicitará un Código de Autorización Electrónico a AFIP. Esta operación es regulatoria y queda registrada en el log fiscal."
        confirmLabel={
          emitirCaeMutation.isPending ? "Solicitando…" : "Emitir CAE"
        }
        onConfirm={() => emitirCaeMutation.mutate()}
        loading={emitirCaeMutation.isPending}
      />
    </>
  );
}

// ---------------------------------------------------------------------------
// Detail content (puro, sin estado)
// ---------------------------------------------------------------------------

interface FacturaDetailContentProps {
  factura: Factura;
  sucursalNombre: string | null;
  sucursalCodigo: string | null;
  clienteRazonSocial: string | null;
  clienteCuit: string | null;
  clienteCondicionIva: string | null;
  actions: React.ReactNode;
}

function FacturaDetailContent({
  factura,
  sucursalNombre,
  sucursalCodigo,
  clienteRazonSocial,
  clienteCuit,
  clienteCondicionIva,
  actions,
}: FacturaDetailContentProps) {
  const numeroCompleto = formatComprobanteNumero(
    factura.punto_venta,
    factura.numero,
  );

  const ivaDesglose = React.useMemo(() => {
    const map = new Map<string, { base: number; iva: number }>();
    for (const it of factura.items) {
      const alic = parseDecimal(it.iva_porc) ?? 0;
      const base = parseDecimal(it.subtotal) ?? 0;
      const iva = parseDecimal(it.iva_monto) ?? 0;
      const key = alic.toFixed(2);
      const prev = map.get(key) ?? { base: 0, iva: 0 };
      map.set(key, { base: prev.base + base, iva: prev.iva + iva });
    }
    return Array.from(map.entries())
      .filter(([, v]) => v.iva > 0)
      .map(([alic, v]) => ({
        alic: Number(alic),
        base: v.base,
        iva: v.iva,
      }))
      .sort((a, b) => b.alic - a.alic);
  }, [factura.items]);

  return (
    <div className="flex flex-col gap-6 pt-1">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1.5 min-w-0">
          <div className="flex items-center gap-2">
            <Badge variant={tipoComprobanteBadgeVariant(factura.tipo)}>
              {comprobanteLabel(factura.tipo)}
            </Badge>
            {factura.estado === "anulada" ? (
              <Badge variant="destructive">Anulada</Badge>
            ) : factura.estado === "emitida" ? (
              <Badge variant="success">Emitida</Badge>
            ) : (
              <Badge variant="secondary">{factura.estado}</Badge>
            )}
          </div>
          <h2 className="text-[22px] font-semibold tracking-tight font-mono leading-tight">
            {numeroCompleto}
          </h2>
          <p className="text-[13px] text-muted-foreground">
            {formatDateLong(factura.fecha)}
          </p>
        </div>
        {actions}
      </div>

      <Separator />

      {/* Datos del comprobante + receptor */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="flex flex-col gap-3">
          <h3 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Datos del comprobante
          </h3>
          <dl className="flex flex-col gap-1.5 text-[13px]">
            <DataRow
              label="Sucursal"
              value={
                sucursalNombre
                  ? `${sucursalCodigo ?? ""} · ${sucursalNombre}`
                  : `Sucursal ${factura.sucursal_id}`
              }
            />
            <DataRow
              label="Punto de venta"
              value={
                <span className="font-mono">
                  {String(factura.punto_venta).padStart(4, "0")}
                </span>
              }
            />
            <DataRow
              label="Cajero"
              value={`#${factura.cajero_id}`}
            />
            <DataRow
              label="Moneda"
              value={factura.moneda}
            />
          </dl>
        </div>

        <div className="flex flex-col gap-3">
          <h3 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Receptor
          </h3>
          <dl className="flex flex-col gap-1.5 text-[13px]">
            <DataRow
              label="Razón social"
              value={clienteRazonSocial ?? "Consumidor Final"}
            />
            <DataRow
              label="CUIT/DNI"
              value={
                <span className="font-mono">{clienteCuit ?? "—"}</span>
              }
            />
            <DataRow
              label="Condición IVA"
              value={
                clienteCondicionIva
                  ? clienteCondicionIva
                      .replace(/_/g, " ")
                      .replace(/\b\w/g, (c) => c.toUpperCase())
                  : "Consumidor Final"
              }
            />
          </dl>
        </div>
      </div>

      <Separator />

      {/* Items */}
      <div className="flex flex-col gap-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Ítems
        </h3>
        <div className="overflow-hidden rounded-[10px] border border-border">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-[110px]">Código</TableHead>
                <TableHead>Descripción</TableHead>
                <TableHead className="w-[60px] text-right">Cant.</TableHead>
                <TableHead className="w-[110px] text-right">Precio</TableHead>
                <TableHead className="w-[60px] text-right">Desc.</TableHead>
                <TableHead className="w-[60px] text-right">IVA</TableHead>
                <TableHead className="w-[110px] text-right">Subtotal</TableHead>
                <TableHead className="w-[110px] text-right">Total</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {factura.items.map((it) => (
                <TableRow key={it.id} className="hover:bg-transparent">
                  <TableCell className="font-mono text-[12px] text-muted-foreground">
                    {it.codigo}
                  </TableCell>
                  <TableCell className="text-[13px]">
                    {it.descripcion}
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-[13px]">
                    {parseDecimal(it.cantidad)?.toLocaleString("es-AR") ?? "—"}
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-[13px]">
                    {formatMoney(it.precio_unitario)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-[12px] text-muted-foreground">
                    {parseDecimal(it.descuento_porc)
                      ? `${parseDecimal(it.descuento_porc)}%`
                      : "—"}
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-[12px] text-muted-foreground">
                    {parseDecimal(it.iva_porc)
                      ? `${parseDecimal(it.iva_porc)}%`
                      : "—"}
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-[13px]">
                    {formatMoney(it.subtotal)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-[13px] font-medium">
                    {formatMoney(it.total)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>

      {/* Totales */}
      <div className="flex flex-col gap-2 self-end w-full max-w-[360px]">
        <div className="flex justify-between text-[13px] text-muted-foreground">
          <span>Subtotal</span>
          <span className="tabular-nums">{formatMoney(factura.subtotal)}</span>
        </div>
        {parseDecimal(factura.total_descuento) ? (
          <div className="flex justify-between text-[13px] text-muted-foreground">
            <span>Descuento</span>
            <span className="tabular-nums">
              −{formatMoney(factura.total_descuento)}
            </span>
          </div>
        ) : null}
        {ivaDesglose.map((d) => (
          <div
            key={d.alic}
            className="flex justify-between text-[13px] text-muted-foreground"
          >
            <span>IVA {d.alic}%</span>
            <span className="tabular-nums">
              {formatMoney(d.iva.toFixed(2))}
            </span>
          </div>
        ))}
        <Separator />
        <div className="flex items-baseline justify-between">
          <span className="text-[13px] font-medium">Total</span>
          <span className="text-[28px] font-semibold tabular-nums tracking-tight">
            {formatMoney(factura.total)}
          </span>
        </div>
      </div>

      <Separator />

      {/* Pagos */}
      <div className="flex flex-col gap-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Medios de pago
        </h3>
        {factura.pagos.length === 0 ? (
          <p className="text-[13px] text-muted-foreground">Sin pagos cargados.</p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {factura.pagos.map((p) => (
              <li
                key={p.id}
                className="flex items-center justify-between gap-3 rounded-[8px] border border-border px-3 py-2 text-[13px]"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <Badge variant="outline" className="font-mono lowercase">
                    {medioPagoLabel(p.medio)}
                  </Badge>
                  {p.referencia ? (
                    <span className="text-[12px] text-muted-foreground truncate font-mono">
                      {p.referencia}
                    </span>
                  ) : null}
                </div>
                <span className="tabular-nums font-medium">
                  {formatMoney(p.monto)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* CAE info */}
      {factura.cae ? (
        <>
          <Separator />
          <div className="flex flex-col gap-2">
            <h3 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Autorización AFIP
            </h3>
            <div className="rounded-[10px] border border-border bg-muted/30 p-4 flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-2">
                  <CheckCircle2
                    className="h-[14px] w-[14px] text-emerald-500"
                    strokeWidth={1.5}
                  />
                  <span className="font-mono text-[13px]">{factura.cae}</span>
                </div>
                <span className="text-[12px] text-muted-foreground">
                  Vence {factura.cae_vencimiento ?? "—"}
                </span>
              </div>
              <Button asChild variant="outline" size="sm">
                <a
                  href={`https://www.afip.gob.ar/fe/qr/?p=${factura.cae}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <ExternalLink className="h-4 w-4" strokeWidth={1.5} />
                  Ver QR AFIP
                </a>
              </Button>
            </div>
          </div>
        </>
      ) : null}

      {factura.observacion ? (
        <>
          <Separator />
          <div className="flex flex-col gap-1">
            <h3 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Observación
            </h3>
            <p className="text-[13px] text-foreground">{factura.observacion}</p>
          </div>
        </>
      ) : null}
    </div>
  );
}

function DataRow({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-foreground text-right">{value}</dd>
    </div>
  );
}
