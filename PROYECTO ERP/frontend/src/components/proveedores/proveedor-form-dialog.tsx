import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import {
  createProveedor,
  updateProveedor,
  type ProveedorPayload,
} from "@/api/proveedores";
import type { ProveedorFull } from "@/lib/types";
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
  proveedor?: ProveedorFull | null;
}

interface FormState {
  codigo: string;
  razon_social: string;
  cuit: string;
  email: string;
  telefono: string;
  direccion: string;
  activo: boolean;
}

const INITIAL: FormState = {
  codigo: "",
  razon_social: "",
  cuit: "",
  email: "",
  telefono: "",
  direccion: "",
  activo: true,
};

function genCodigo(): string {
  return `PRV${Date.now().toString().slice(-8)}`;
}

function isValidCuit(cuit: string): boolean {
  if (!cuit) return true;
  return /^\d{2}-?\d{8}-?\d{1}$/.test(cuit.trim());
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

export function ProveedorFormDialog({
  open,
  onOpenChange,
  proveedor,
}: Props) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const editing = Boolean(proveedor);

  const [form, setForm] = React.useState<FormState>(INITIAL);
  const [errors, setErrors] = React.useState<
    Partial<Record<keyof FormState, string>>
  >({});

  React.useEffect(() => {
    if (!open) {
      setForm(INITIAL);
      setErrors({});
      return;
    }
    if (proveedor) {
      setForm({
        codigo: proveedor.codigo,
        razon_social: proveedor.razon_social,
        cuit: proveedor.cuit ?? "",
        email: proveedor.email ?? "",
        telefono: proveedor.telefono ?? "",
        direccion: proveedor.direccion ?? "",
        activo: Boolean(proveedor.activo),
      });
    } else {
      setForm(INITIAL);
    }
    setErrors({});
  }, [open, proveedor]);

  const mutation = useMutation({
    mutationFn: async (payload: ProveedorPayload) => {
      if (editing && proveedor) return updateProveedor(proveedor.id, payload);
      return createProveedor(payload);
    },
    onSuccess: (saved) => {
      toast({
        title: editing ? "Proveedor actualizado" : "Proveedor creado",
        description: `${saved.codigo} · ${saved.razon_social}`,
      });
      qc.invalidateQueries({ queryKey: ["proveedores-full"] });
      qc.invalidateQueries({ queryKey: ["proveedores"] });
      onOpenChange(false);
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: { error?: string } } };
      toast({
        title: editing
          ? "No pudimos actualizar el proveedor"
          : "No pudimos crear el proveedor",
        description:
          e?.response?.data?.error ?? "Revisá los campos e intentá de nuevo.",
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
    if (!form.razon_social.trim()) errs.razon_social = "Requerido";
    else if (form.razon_social.length > 255)
      errs.razon_social = "Máximo 255 caracteres";
    if (form.codigo.length > 30) errs.codigo = "Máximo 30 caracteres";
    if (form.cuit.trim() && !isValidCuit(form.cuit))
      errs.cuit = "Formato esperado XX-XXXXXXXX-X";
    if (
      form.email.trim() &&
      !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())
    )
      errs.email = "Email inválido";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    const codigo = form.codigo.trim() || genCodigo();
    const payload: ProveedorPayload = {
      codigo,
      razon_social: form.razon_social.trim(),
      cuit: form.cuit.trim() || null,
      email: form.email.trim() || null,
      telefono: form.telefono.trim() || null,
      direccion: form.direccion.trim() || null,
      activo: form.activo,
    };

    mutation.mutate(payload);
  };

  const loading = mutation.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[560px] p-0 overflow-hidden">
        <DialogHeader className="px-8 pt-8 pb-2">
          <DialogTitle className="text-[22px] font-semibold tracking-tight">
            {editing ? "Editar proveedor" : "Nuevo proveedor"}
          </DialogTitle>
          <DialogDescription className="text-[13px] text-muted-foreground">
            {editing
              ? "Actualizá los datos del proveedor."
              : "Si dejás el código vacío, lo generamos automáticamente."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={onSubmit}>
          <div className="px-8 pt-4 pb-6 max-h-[60vh] overflow-y-auto flex flex-col gap-5">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="md:col-span-1 flex flex-col gap-2">
                <Label htmlFor="prv-codigo">Código</Label>
                <Input
                  id="prv-codigo"
                  value={form.codigo}
                  onChange={(e) => set("codigo", e.target.value)}
                  disabled={loading || editing}
                  maxLength={30}
                  placeholder={editing ? "" : "Auto"}
                  className="font-mono text-[12px]"
                />
                {errors.codigo && (
                  <p className="text-[12px] text-destructive">
                    {errors.codigo}
                  </p>
                )}
              </div>
              <div className="md:col-span-2 flex flex-col gap-2">
                <Label htmlFor="prv-razon">Razón social *</Label>
                <Input
                  id="prv-razon"
                  value={form.razon_social}
                  onChange={(e) => set("razon_social", e.target.value)}
                  disabled={loading}
                  autoFocus
                  maxLength={255}
                />
                {errors.razon_social && (
                  <p className="text-[12px] text-destructive">
                    {errors.razon_social}
                  </p>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor="prv-cuit">CUIT</Label>
                <Input
                  id="prv-cuit"
                  value={form.cuit}
                  onChange={(e) => set("cuit", e.target.value)}
                  disabled={loading}
                  placeholder="XX-XXXXXXXX-X"
                  maxLength={15}
                  className="font-mono"
                />
                {errors.cuit && (
                  <p className="text-[12px] text-destructive">{errors.cuit}</p>
                )}
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="prv-email">Email</Label>
                <Input
                  id="prv-email"
                  type="email"
                  value={form.email}
                  onChange={(e) => set("email", e.target.value)}
                  disabled={loading}
                  maxLength={200}
                />
                {errors.email && (
                  <p className="text-[12px] text-destructive">{errors.email}</p>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor="prv-tel">Teléfono</Label>
                <Input
                  id="prv-tel"
                  value={form.telefono}
                  onChange={(e) => set("telefono", e.target.value)}
                  disabled={loading}
                  maxLength={50}
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="prv-dir">Dirección</Label>
                <Input
                  id="prv-dir"
                  value={form.direccion}
                  onChange={(e) => set("direccion", e.target.value)}
                  disabled={loading}
                  maxLength={255}
                />
              </div>
            </div>

            <div className="pt-2 border-t border-border">
              <Check
                id="prv-activo"
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
              {loading && (
                <Loader2 className="animate-spin" strokeWidth={1.5} />
              )}
              {loading
                ? editing
                  ? "Guardando…"
                  : "Creando…"
                : editing
                  ? "Guardar cambios"
                  : "Crear proveedor"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
