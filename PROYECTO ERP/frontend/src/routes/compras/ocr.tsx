import * as React from "react";
import { createRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Loader2,
  Sparkles,
  Trash2,
  XCircle,
} from "lucide-react";
import {
  type ComprobanteOcr,
  type OcrItemOverridePayload,
  confirmarComprobante,
  descartarComprobante,
  getImagenUrl,
  listComprobantes,
  uploadComprobante,
} from "@/api/ocr";
import { listSucursales } from "@/api/sucursales";
import { listProveedoresFull } from "@/api/proveedores";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ConfidenceBar } from "@/components/ocr/confidence-bar";
import { Dropzone } from "@/components/ocr/dropzone";
import { ItemsEditor, type ItemDraft } from "@/components/ocr/items-editor";
import { useToast } from "@/hooks/use-toast";
import { comprasRoute } from "../compras";

export const comprasOcrRoute = createRoute({
  getParentRoute: () => comprasRoute,
  path: "/ocr",
  component: ComprasOcrPage,
});

const ESTADO_LABEL: Record<string, string> = {
  pendiente: "Pendiente",
  procesando: "Procesando",
  extraido: "Para revisar",
  confirmado: "Confirmado",
  descartado: "Descartado",
  error: "Error",
};

const ESTADO_VARIANT: Record<
  string,
  "default" | "secondary" | "destructive" | "success" | "outline"
> = {
  pendiente: "secondary",
  procesando: "secondary",
  extraido: "default",
  confirmado: "success",
  descartado: "outline",
  error: "destructive",
};

function ComprasOcrPage() {
  const { toast } = useToast();
  const qc = useQueryClient();

  const [file, setFile] = React.useState<File | null>(null);
  const [activeOcr, setActiveOcr] = React.useState<ComprobanteOcr | null>(null);

  const sucursalesQ = useQuery({
    queryKey: ["sucursales"],
    queryFn: listSucursales,
  });
  const proveedoresQ = useQuery({
    queryKey: ["proveedores"],
    queryFn: listProveedoresFull,
  });

  const listadoQ = useQuery({
    queryKey: ["ocr", "list"],
    queryFn: () => listComprobantes({ per_page: 20 }),
  });

  const uploadMut = useMutation({
    mutationFn: async (vars: { f: File; sid?: number }) =>
      uploadComprobante(vars.f, vars.sid),
    onSuccess: (data) => {
      setActiveOcr(data);
      setFile(null);
      qc.invalidateQueries({ queryKey: ["ocr"] });
      if (data.estado === "error") {
        toast({
          title: "No se pudo leer el comprobante",
          description: data.error_message ?? "Probá con otra foto.",
          variant: "destructive",
        });
      } else {
        toast({
          title: "Comprobante leído",
          description: `${data.items_extraidos.length} ítems detectados.`,
        });
      }
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { error?: string } } })?.response?.data
          ?.error ?? "Error subiendo el archivo.";
      toast({
        title: "Error",
        description: msg,
        variant: "destructive",
      });
    },
  });

  const sucursalesActivas = (sucursalesQ.data ?? []).filter((s) => s.activa);
  const defaultSucursalId = sucursalesActivas[0]?.id ?? null;
  const [sucursalUpload, setSucursalUpload] = React.useState<number | null>(
    null,
  );
  React.useEffect(() => {
    if (sucursalUpload === null && defaultSucursalId !== null) {
      setSucursalUpload(defaultSucursalId);
    }
  }, [defaultSucursalId, sucursalUpload]);

  const handleProcesar = () => {
    if (!file) return;
    uploadMut.mutate({ f: file, sid: sucursalUpload ?? undefined });
  };

  return (
    <div className="space-y-8 max-w-7xl">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">
          Carga de compras con IA
        </h1>
        <p className="text-sm text-muted-foreground">
          Subí una foto del comprobante del proveedor. Claude lee los ítems y
          los carga como borrador para que revises antes de imputar a stock.
        </p>
      </header>

      {!activeOcr ? (
        <UploadView
          file={file}
          setFile={setFile}
          sucursales={sucursalesActivas}
          sucursalId={sucursalUpload}
          onSucursalChange={setSucursalUpload}
          onProcesar={handleProcesar}
          loading={uploadMut.isPending}
        />
      ) : (
        <ResultadoView
          comprobante={activeOcr}
          onClose={() => setActiveOcr(null)}
          sucursales={sucursalesActivas}
          proveedores={proveedoresQ.data ?? []}
        />
      )}

      <section className="space-y-3">
        <div className="flex items-baseline justify-between">
          <h2 className="text-base font-semibold tracking-tight">
            Comprobantes recientes
          </h2>
          <span className="text-xs text-muted-foreground">
            {listadoQ.data?.total ?? 0} totales
          </span>
        </div>
        {listadoQ.isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-14 w-full" />
            ))}
          </div>
        ) : (
          <Card>
            <ul className="divide-y divide-border">
              {(listadoQ.data?.items ?? []).map((it) => (
                <li
                  key={it.id}
                  className="flex items-center gap-4 p-4 hover:bg-muted/30 transition-colors duration-200 ease-apple cursor-pointer"
                  onClick={() => {
                    if (it.estado === "extraido" || it.estado === "error") {
                      setActiveOcr(it);
                    }
                  }}
                >
                  <img
                    src={getImagenUrl(it.id)}
                    alt=""
                    className="h-12 w-12 rounded-[8px] object-cover bg-muted shadow-apple"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.visibility =
                        "hidden";
                    }}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium truncate">
                      {it.proveedor_nombre_raw ?? "Proveedor sin identificar"}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {it.tipo_detectado}
                      {it.numero_comprobante ? ` · ${it.numero_comprobante}` : ""}
                      {it.total ? ` · $${it.total}` : ""}
                    </div>
                  </div>
                  <Badge variant={ESTADO_VARIANT[it.estado] ?? "outline"}>
                    {ESTADO_LABEL[it.estado] ?? it.estado}
                  </Badge>
                </li>
              ))}
              {(listadoQ.data?.items ?? []).length === 0 && (
                <li className="p-8 text-center text-sm text-muted-foreground">
                  Todavía no subiste ningún comprobante.
                </li>
              )}
            </ul>
          </Card>
        )}
      </section>
    </div>
  );
}

// ----------------------------------------------------------------------------
// UploadView
// ----------------------------------------------------------------------------

interface Sucursal {
  id: number;
  nombre: string;
  codigo: string;
  activa: boolean;
}

interface UploadViewProps {
  file: File | null;
  setFile: (f: File | null) => void;
  sucursales: Sucursal[];
  sucursalId: number | null;
  onSucursalChange: (id: number) => void;
  onProcesar: () => void;
  loading: boolean;
}

function UploadView({
  file,
  setFile,
  sucursales,
  sucursalId,
  onSucursalChange,
  onProcesar,
  loading,
}: UploadViewProps) {
  return (
    <div className="space-y-5">
      <Dropzone
        onFile={setFile}
        selectedFile={file}
        onClear={() => setFile(null)}
        disabled={loading}
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <label className="text-xs font-medium text-muted-foreground">
            Sucursal donde imputar la compra
          </label>
          <select
            value={sucursalId ?? ""}
            onChange={(e) => onSucursalChange(Number(e.target.value))}
            className="h-10 w-full rounded-[8px] border border-input bg-background px-3 text-sm"
          >
            <option value="" disabled>
              Elegir sucursal…
            </option>
            {sucursales.map((s) => (
              <option key={s.id} value={s.id}>
                {s.codigo} · {s.nombre}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-end">
          <Button
            type="button"
            size="lg"
            disabled={!file || loading || !sucursalId}
            onClick={onProcesar}
            className="w-full"
          >
            {loading ? (
              <>
                <Loader2
                  className="h-4 w-4 animate-spin"
                  strokeWidth={1.5}
                />
                Leyendo comprobante con IA…
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" strokeWidth={1.5} />
                Procesar con IA
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ----------------------------------------------------------------------------
// ResultadoView
// ----------------------------------------------------------------------------

interface ResultadoViewProps {
  comprobante: ComprobanteOcr;
  onClose: () => void;
  sucursales: Sucursal[];
  proveedores: { id: number; razon_social: string; codigo: string }[];
}

function itemsExtraidosToDrafts(c: ComprobanteOcr): ItemDraft[] {
  return c.items_extraidos.map((it) => ({
    descripcion: String(it.descripcion ?? ""),
    cantidad: String(it.cantidad ?? "1"),
    unidad: String(it.unidad ?? "unidad"),
    precio_unitario: String(it.precio_unitario ?? "0"),
    iva_porc: "21",
    articulo_id: it.articulo_id_match ?? null,
    crear_articulo_si_falta: !it.articulo_id_match,
  }));
}

function ResultadoView({
  comprobante,
  onClose,
  sucursales,
  proveedores,
}: ResultadoViewProps) {
  const { toast } = useToast();
  const qc = useQueryClient();

  const [items, setItems] = React.useState<ItemDraft[]>(() =>
    itemsExtraidosToDrafts(comprobante),
  );
  const [sucursalId, setSucursalId] = React.useState<number>(
    comprobante.sucursal_id ?? sucursales[0]?.id ?? 0,
  );
  const [proveedorId, setProveedorId] = React.useState<number | null>(
    comprobante.proveedor_id_match ?? null,
  );
  const [numero, setNumero] = React.useState<string>(
    comprobante.numero_comprobante ?? "",
  );

  const confirmMut = useMutation({
    mutationFn: async () => {
      const payload: OcrItemOverridePayload[] = items.map((it) => ({
        descripcion: it.descripcion,
        cantidad: it.cantidad,
        unidad: it.unidad,
        precio_unitario: it.precio_unitario,
        iva_porc: it.iva_porc,
        articulo_id: it.articulo_id,
        crear_articulo_si_falta: it.crear_articulo_si_falta,
      }));
      return confirmarComprobante(comprobante.id, {
        sucursal_id: sucursalId,
        proveedor_id: proveedorId,
        numero_override: numero || null,
        items: payload,
      });
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["ocr"] });
      qc.invalidateQueries({ queryKey: ["facturas"] });
      qc.invalidateQueries({ queryKey: ["stock"] });
      qc.invalidateQueries({ queryKey: ["articulos"] });
      toast({
        title: "Compra creada",
        description: data.factura_creada
          ? `Factura compra ${data.factura_creada.punto_venta
              .toString()
              .padStart(4, "0")}-${data.factura_creada.numero
              .toString()
              .padStart(8, "0")} imputada al stock.`
          : "Compra confirmada.",
      });
      onClose();
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { error?: string } } })?.response?.data
          ?.error ?? "No se pudo confirmar.";
      toast({
        title: "Error",
        description: msg,
        variant: "destructive",
      });
    },
  });

  const descartarMut = useMutation({
    mutationFn: async () => descartarComprobante(comprobante.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ocr"] });
      toast({ title: "Comprobante descartado" });
      onClose();
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { error?: string } } })?.response?.data
          ?.error ?? "No se pudo descartar.";
      toast({
        title: "Error",
        description: msg,
        variant: "destructive",
      });
    },
  });

  const totalCalc = items.reduce((acc, it) => {
    const c = parseFloat(it.cantidad || "0");
    const p = parseFloat(it.precio_unitario || "0");
    const iva = parseFloat(it.iva_porc || "0");
    if (!Number.isFinite(c) || !Number.isFinite(p)) return acc;
    return acc + c * p * (1 + iva / 100);
  }, 0);

  const onChangeItem = (idx: number, patch: Partial<ItemDraft>) =>
    setItems((prev) => prev.map((it, i) => (i === idx ? { ...it, ...patch } : it)));

  const onRemoveItem = (idx: number) =>
    setItems((prev) => prev.filter((_, i) => i !== idx));

  const confianza = comprobante.confianza
    ? parseFloat(comprobante.confianza)
    : null;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
      <div className="space-y-5 min-w-0">
        <Card className="p-5 space-y-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
                Resultado IA
              </div>
              <h2 className="text-lg font-semibold tracking-tight mt-0.5">
                {comprobante.tipo_detectado}
                {comprobante.letra ? ` ${comprobante.letra}` : ""}
                {comprobante.numero_comprobante
                  ? ` · ${comprobante.numero_comprobante}`
                  : ""}
              </h2>
              <div className="text-xs text-muted-foreground mt-1">
                Modelo: {comprobante.modelo_ia_usado ?? "?"} ·{" "}
                {comprobante.duracion_extraccion_ms ?? 0}ms
              </div>
            </div>
            <ConfidenceBar value={confianza} className="w-44" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                Proveedor
              </label>
              {comprobante.proveedor_match ? (
                <div className="text-sm">
                  <span className="font-medium text-emerald-600 dark:text-emerald-400">
                    Matcheado:
                  </span>{" "}
                  {comprobante.proveedor_match.razon_social}
                </div>
              ) : comprobante.proveedor_nombre_raw ? (
                <div className="text-xs text-amber-600 dark:text-amber-400">
                  Sin match: {comprobante.proveedor_nombre_raw}
                </div>
              ) : null}
              <select
                value={proveedorId ?? ""}
                onChange={(e) =>
                  setProveedorId(e.target.value ? Number(e.target.value) : null)
                }
                className="h-10 w-full rounded-[8px] border border-input bg-background px-3 text-sm"
              >
                <option value="">— Sin proveedor —</option>
                {proveedores.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.codigo} · {p.razon_social}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                Sucursal de imputación
              </label>
              <select
                value={sucursalId}
                onChange={(e) => setSucursalId(Number(e.target.value))}
                className="h-10 w-full rounded-[8px] border border-input bg-background px-3 text-sm"
              >
                {sucursales.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.codigo} · {s.nombre}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                N° de comprobante (proveedor)
              </label>
              <Input
                value={numero}
                onChange={(e) => setNumero(e.target.value)}
                placeholder="0001-00012345"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                Total IA
              </label>
              <div className="h-10 flex items-center text-sm tabular-nums">
                {comprobante.total
                  ? `$ ${parseFloat(comprobante.total).toLocaleString("es-AR", {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}`
                  : "—"}
              </div>
            </div>
          </div>
        </Card>

        <ItemsEditor
          items={items}
          onChange={onChangeItem}
          onRemove={onRemoveItem}
        />

        <div className="flex items-center justify-between gap-4 rounded-xl border border-border bg-card p-4 shadow-apple">
          <div className="text-sm">
            <span className="text-muted-foreground">Total recalculado:</span>{" "}
            <span className="font-semibold tabular-nums">
              {totalCalc.toLocaleString("es-AR", {
                style: "currency",
                currency: "ARS",
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </span>
          </div>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => descartarMut.mutate()}
              disabled={descartarMut.isPending || confirmMut.isPending}
            >
              <Trash2 className="h-4 w-4" strokeWidth={1.5} />
              Descartar
            </Button>
            <Button
              type="button"
              onClick={() => confirmMut.mutate()}
              disabled={
                confirmMut.isPending ||
                descartarMut.isPending ||
                !sucursalId ||
                items.length === 0
              }
            >
              {confirmMut.isPending ? (
                <>
                  <Loader2
                    className="h-4 w-4 animate-spin"
                    strokeWidth={1.5}
                  />
                  Creando compra…
                </>
              ) : (
                <>
                  <CheckCircle2 className="h-4 w-4" strokeWidth={1.5} />
                  Confirmar y crear compra
                </>
              )}
            </Button>
          </div>
        </div>

        {comprobante.estado === "error" && (
          <div className="rounded-xl border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive flex gap-3 items-start">
            <XCircle className="h-5 w-5 mt-0.5" strokeWidth={1.5} />
            <div>
              <div className="font-medium">No se pudo extraer la información</div>
              <div className="text-xs mt-1">{comprobante.error_message}</div>
            </div>
          </div>
        )}
      </div>

      <aside className="lg:sticky lg:top-6 self-start">
        <Card className="overflow-hidden shadow-apple-md">
          <div className="px-4 py-3 border-b border-border bg-muted/40 text-xs uppercase tracking-wider text-muted-foreground">
            Imagen original
          </div>
          <img
            src={getImagenUrl(comprobante.id)}
            alt="comprobante"
            className="w-full"
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = "none";
            }}
          />
        </Card>
      </aside>
    </div>
  );
}
