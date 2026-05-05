import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { createArticulo } from "@/api/articulos";
import type { ArticuloCreatePayload } from "@/api/articulos";
import {
  listFamilias,
  listMarcas,
  listProveedores,
  listRubros,
} from "@/api/catalogos";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type UnidadMedida = "unidad" | "kg" | "gr" | "lt" | "ml";

const UNIDADES: { value: UnidadMedida; label: string }[] = [
  { value: "unidad", label: "Unidad" },
  { value: "kg", label: "Kilogramo (kg)" },
  { value: "gr", label: "Gramo (gr)" },
  { value: "lt", label: "Litro (lt)" },
  { value: "ml", label: "Mililitro (ml)" },
];

const IVA_OPCIONES = ["0", "10.50", "21", "27"];

interface FormState {
  codigo: string;
  descripcion: string;
  // Renombrado en `articulo-multi-codigo-migration` — el label UI mantiene
  // "Código de barras" por convención; el payload va como `codigo_principal`.
  codigo_principal: string;
  descripcion_corta: string;
  unidad_medida: UnidadMedida;
  familia_id: string;
  rubro_id: string;
  marca_id: string;
  proveedor_principal_id: string;
  costo: string;
  pvp_base: string;
  iva_porc: string;
  controla_stock: boolean;
  controla_vencimiento: boolean;
  activo: boolean;
}

const INITIAL: FormState = {
  codigo: "",
  descripcion: "",
  codigo_principal: "",
  descripcion_corta: "",
  unidad_medida: "unidad",
  familia_id: "",
  rubro_id: "",
  marca_id: "",
  proveedor_principal_id: "",
  costo: "0",
  pvp_base: "0",
  iva_porc: "21",
  controla_stock: true,
  controla_vencimiento: false,
  activo: true,
};

function AppleSelect({
  id,
  value,
  onChange,
  children,
  disabled,
}: {
  id: string;
  value: string;
  onChange: (v: string) => void;
  children: React.ReactNode;
  disabled?: boolean;
}) {
  return (
    <select
      id={id}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      className={cn(
        "flex h-10 w-full items-center rounded-lg border border-input bg-background px-3 py-2 text-[14px]",
        "ring-offset-background transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        "disabled:cursor-not-allowed disabled:opacity-50",
      )}
    >
      {children}
    </select>
  );
}

function Check({
  id,
  label,
  checked,
  onChange,
  disabled,
}: {
  id: string;
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <label
      htmlFor={id}
      className={cn(
        "flex items-center gap-2.5 cursor-pointer select-none",
        disabled && "cursor-not-allowed opacity-50",
      )}
    >
      <input
        id={id}
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 rounded-[4px] border border-input accent-primary"
      />
      <span className="text-[13px] text-foreground">{label}</span>
    </label>
  );
}

export function CreateArticleDialog({ open, onOpenChange }: Props) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [form, setForm] = React.useState<FormState>(INITIAL);
  const [errors, setErrors] = React.useState<Partial<Record<keyof FormState, string>>>({});

  const familiasQ = useQuery({ queryKey: ["familias"], queryFn: listFamilias, enabled: open });
  const rubrosQ = useQuery({ queryKey: ["rubros"], queryFn: listRubros, enabled: open });
  const marcasQ = useQuery({ queryKey: ["marcas"], queryFn: listMarcas, enabled: open });
  const proveedoresQ = useQuery({
    queryKey: ["proveedores"],
    queryFn: listProveedores,
    enabled: open,
  });

  const rubrosFiltrados = React.useMemo(() => {
    const rubros = rubrosQ.data ?? [];
    if (!form.familia_id) return rubros;
    const fid = Number(form.familia_id);
    return rubros.filter((r) => r.familia_id === fid || r.familia_id == null);
  }, [rubrosQ.data, form.familia_id]);

  React.useEffect(() => {
    if (!open) {
      setForm(INITIAL);
      setErrors({});
    }
  }, [open]);

  const mutation = useMutation({
    mutationFn: createArticulo,
    onSuccess: (articulo) => {
      toast({
        title: "Artículo creado",
        description: `${articulo.codigo} · ${articulo.descripcion}`,
      });
      qc.invalidateQueries({ queryKey: ["articulos"] });
      onOpenChange(false);
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: { error?: string; details?: unknown } } };
      toast({
        title: "No pudimos crear el artículo",
        description: e?.response?.data?.error ?? "Revisá los campos e intentá de nuevo.",
        variant: "destructive",
      });
    },
  });

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((f) => ({ ...f, [key]: value }));
    if (errors[key]) setErrors((prev) => ({ ...prev, [key]: undefined }));
  };

  const validate = (): boolean => {
    const errs: Partial<Record<keyof FormState, string>> = {};
    if (!form.codigo.trim()) errs.codigo = "Requerido";
    else if (form.codigo.length > 30) errs.codigo = "Máximo 30 caracteres";
    if (!form.descripcion.trim()) errs.descripcion = "Requerido";
    else if (form.descripcion.length > 255) errs.descripcion = "Máximo 255 caracteres";
    if (Number(form.costo) < 0) errs.costo = "No puede ser negativo";
    if (Number(form.pvp_base) < 0) errs.pvp_base = "No puede ser negativo";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    const payload: ArticuloCreatePayload = {
      codigo: form.codigo.trim(),
      descripcion: form.descripcion.trim(),
      codigo_principal: form.codigo_principal.trim() || null,
      descripcion_corta: form.descripcion_corta.trim() || null,
      unidad_medida: form.unidad_medida,
      familia_id: form.familia_id ? Number(form.familia_id) : null,
      rubro_id: form.rubro_id ? Number(form.rubro_id) : null,
      marca_id: form.marca_id ? Number(form.marca_id) : null,
      proveedor_principal_id: form.proveedor_principal_id
        ? Number(form.proveedor_principal_id)
        : null,
      costo: form.costo || "0",
      pvp_base: form.pvp_base || "0",
      iva_porc: form.iva_porc || "21",
      controla_stock: form.controla_stock,
      controla_vencimiento: form.controla_vencimiento,
      activo: form.activo,
    };

    mutation.mutate(payload);
  };

  const loading = mutation.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[640px] p-0 overflow-hidden">
        <DialogHeader className="px-8 pt-8 pb-2">
          <DialogTitle className="text-[22px] font-semibold tracking-tight">
            Nuevo artículo
          </DialogTitle>
          <DialogDescription className="text-[13px] text-muted-foreground">
            Se agrega al catálogo unificado. Podés cargar precios por sucursal
            después desde la tabla.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={onSubmit}>
          <div className="px-8 pt-4 pb-6 max-h-[60vh] overflow-y-auto flex flex-col gap-5">
            {/* Básicos */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="md:col-span-1 flex flex-col gap-2">
                <Label htmlFor="codigo">Código *</Label>
                <Input
                  id="codigo"
                  value={form.codigo}
                  onChange={(e) => set("codigo", e.target.value)}
                  disabled={loading}
                  autoFocus
                  maxLength={30}
                />
                {errors.codigo && (
                  <p className="text-[12px] text-destructive">{errors.codigo}</p>
                )}
              </div>
              <div className="md:col-span-2 flex flex-col gap-2">
                <Label htmlFor="descripcion">Descripción *</Label>
                <Input
                  id="descripcion"
                  value={form.descripcion}
                  onChange={(e) => set("descripcion", e.target.value)}
                  disabled={loading}
                  maxLength={255}
                />
                {errors.descripcion && (
                  <p className="text-[12px] text-destructive">{errors.descripcion}</p>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="flex flex-col gap-2">
                {/* Label legacy preservado — el campo backend es `codigo_principal`
                    pero la UI sigue diciendo "Código de barras" por convención. */}
                <Label htmlFor="codigo_principal">Código de barras</Label>
                <Input
                  id="codigo_principal"
                  value={form.codigo_principal}
                  onChange={(e) => set("codigo_principal", e.target.value)}
                  disabled={loading}
                  placeholder="EAN-13 / UPC"
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="descripcion_corta">Descripción corta</Label>
                <Input
                  id="descripcion_corta"
                  value={form.descripcion_corta}
                  onChange={(e) => set("descripcion_corta", e.target.value)}
                  disabled={loading}
                  maxLength={100}
                  placeholder="Para ticket (opcional)"
                />
              </div>
            </div>

            {/* Clasificación */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor="familia">Familia</Label>
                <AppleSelect
                  id="familia"
                  value={form.familia_id}
                  onChange={(v) => {
                    set("familia_id", v);
                    set("rubro_id", "");
                  }}
                  disabled={loading}
                >
                  <option value="">Sin familia</option>
                  {(familiasQ.data ?? []).map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.nombre}
                    </option>
                  ))}
                </AppleSelect>
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="rubro">Rubro</Label>
                <AppleSelect
                  id="rubro"
                  value={form.rubro_id}
                  onChange={(v) => set("rubro_id", v)}
                  disabled={loading}
                >
                  <option value="">Sin rubro</option>
                  {rubrosFiltrados.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.nombre}
                    </option>
                  ))}
                </AppleSelect>
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="marca">Marca</Label>
                <AppleSelect
                  id="marca"
                  value={form.marca_id}
                  onChange={(v) => set("marca_id", v)}
                  disabled={loading}
                >
                  <option value="">Sin marca</option>
                  {(marcasQ.data ?? []).map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.nombre}
                    </option>
                  ))}
                </AppleSelect>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor="proveedor">Proveedor principal</Label>
                <AppleSelect
                  id="proveedor"
                  value={form.proveedor_principal_id}
                  onChange={(v) => set("proveedor_principal_id", v)}
                  disabled={loading}
                >
                  <option value="">Sin proveedor</option>
                  {(proveedoresQ.data ?? []).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.nombre}
                    </option>
                  ))}
                </AppleSelect>
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="unidad">Unidad de medida</Label>
                <AppleSelect
                  id="unidad"
                  value={form.unidad_medida}
                  onChange={(v) => set("unidad_medida", v as UnidadMedida)}
                  disabled={loading}
                >
                  {UNIDADES.map((u) => (
                    <option key={u.value} value={u.value}>
                      {u.label}
                    </option>
                  ))}
                </AppleSelect>
              </div>
            </div>

            {/* Precios */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor="costo">Costo</Label>
                <Input
                  id="costo"
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.costo}
                  onChange={(e) => set("costo", e.target.value)}
                  disabled={loading}
                  className="tabular-nums"
                />
                {errors.costo && (
                  <p className="text-[12px] text-destructive">{errors.costo}</p>
                )}
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="pvp">PVP base</Label>
                <Input
                  id="pvp"
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.pvp_base}
                  onChange={(e) => set("pvp_base", e.target.value)}
                  disabled={loading}
                  className="tabular-nums"
                />
                {errors.pvp_base && (
                  <p className="text-[12px] text-destructive">{errors.pvp_base}</p>
                )}
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="iva">IVA %</Label>
                <AppleSelect
                  id="iva"
                  value={form.iva_porc}
                  onChange={(v) => set("iva_porc", v)}
                  disabled={loading}
                >
                  {IVA_OPCIONES.map((v) => (
                    <option key={v} value={v}>
                      {v}%
                    </option>
                  ))}
                </AppleSelect>
              </div>
            </div>

            {/* Flags */}
            <div className="flex flex-wrap gap-x-6 gap-y-3 pt-2 border-t border-border">
              <Check
                id="controla_stock"
                label="Controla stock"
                checked={form.controla_stock}
                onChange={(v) => set("controla_stock", v)}
                disabled={loading}
              />
              <Check
                id="controla_vencimiento"
                label="Controla vencimiento"
                checked={form.controla_vencimiento}
                onChange={(v) => set("controla_vencimiento", v)}
                disabled={loading}
              />
              <Check
                id="activo"
                label="Activo"
                checked={form.activo}
                onChange={(v) => set("activo", v)}
                disabled={loading}
              />
            </div>
          </div>

          <DialogFooter className="px-8 py-5 border-t border-border bg-muted/30">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={loading}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={loading}>
              {loading && <Loader2 className="animate-spin" strokeWidth={1.5} />}
              {loading ? "Creando…" : "Crear artículo"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
