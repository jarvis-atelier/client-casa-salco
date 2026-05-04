import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import {
  createCliente,
  updateCliente,
  type ClientePayload,
} from "@/api/clientes";
import type { Cliente, CondicionIva } from "@/lib/types";
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
  cliente?: Cliente | null;
}

const CONDICIONES: { value: CondicionIva; label: string }[] = [
  { value: "responsable_inscripto", label: "Responsable Inscripto" },
  { value: "monotributo", label: "Monotributo" },
  { value: "consumidor_final", label: "Consumidor Final" },
  { value: "exento", label: "Exento" },
  { value: "no_categorizado", label: "No categorizado" },
];

interface FormState {
  codigo: string;
  razon_social: string;
  cuit: string;
  condicion_iva: CondicionIva;
  condicion_iva_receptor_id: string;
  email: string;
  telefono: string;
  direccion: string;
  cuenta_corriente: boolean;
  limite_cuenta_corriente: string;
  activo: boolean;
}

const INITIAL: FormState = {
  codigo: "",
  razon_social: "",
  cuit: "",
  condicion_iva: "consumidor_final",
  condicion_iva_receptor_id: "",
  email: "",
  telefono: "",
  direccion: "",
  cuenta_corriente: false,
  limite_cuenta_corriente: "0",
  activo: true,
};

function genCodigo(): string {
  return `CLI${Date.now().toString().slice(-8)}`;
}

function isValidCuit(cuit: string): boolean {
  if (!cuit) return true;
  return /^\d{2}-?\d{8}-?\d{1}$/.test(cuit.trim());
}

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

export function ClienteFormDialog({ open, onOpenChange, cliente }: Props) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const editing = Boolean(cliente);

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
    if (cliente) {
      setForm({
        codigo: cliente.codigo ?? "",
        razon_social: cliente.razon_social ?? "",
        cuit: cliente.cuit ?? "",
        condicion_iva: cliente.condicion_iva,
        condicion_iva_receptor_id:
          cliente.condicion_iva_receptor_id != null
            ? String(cliente.condicion_iva_receptor_id)
            : "",
        email: cliente.email ?? "",
        telefono: cliente.telefono ?? "",
        direccion: cliente.direccion ?? "",
        cuenta_corriente: Boolean(cliente.cuenta_corriente),
        limite_cuenta_corriente: String(cliente.limite_cuenta_corriente ?? "0"),
        activo: Boolean(cliente.activo),
      });
    } else {
      setForm(INITIAL);
    }
    setErrors({});
  }, [open, cliente]);

  const mutation = useMutation({
    mutationFn: async (payload: ClientePayload) => {
      if (editing && cliente) {
        return updateCliente(cliente.id, payload);
      }
      return createCliente(payload);
    },
    onSuccess: (saved) => {
      toast({
        title: editing ? "Cliente actualizado" : "Cliente creado",
        description: `${saved.codigo} · ${saved.razon_social}`,
      });
      qc.invalidateQueries({ queryKey: ["clientes"] });
      qc.invalidateQueries({ queryKey: ["cliente", saved.id] });
      onOpenChange(false);
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: { error?: string } } };
      toast({
        title: editing
          ? "No pudimos actualizar el cliente"
          : "No pudimos crear el cliente",
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
    if (Number(form.limite_cuenta_corriente) < 0)
      errs.limite_cuenta_corriente = "No puede ser negativo";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    const codigo = form.codigo.trim() || genCodigo();
    const payload: ClientePayload = {
      codigo,
      razon_social: form.razon_social.trim(),
      cuit: form.cuit.trim() || null,
      condicion_iva: form.condicion_iva,
      condicion_iva_receptor_id: form.condicion_iva_receptor_id
        ? Number(form.condicion_iva_receptor_id)
        : null,
      email: form.email.trim() || null,
      telefono: form.telefono.trim() || null,
      direccion: form.direccion.trim() || null,
      cuenta_corriente: form.cuenta_corriente,
      limite_cuenta_corriente: form.cuenta_corriente
        ? form.limite_cuenta_corriente || "0"
        : "0",
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
            {editing ? "Editar cliente" : "Nuevo cliente"}
          </DialogTitle>
          <DialogDescription className="text-[13px] text-muted-foreground">
            {editing
              ? "Actualizá los datos. Los cambios se guardan al confirmar."
              : "Si dejás el código vacío, lo generamos automáticamente."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={onSubmit}>
          <div className="px-8 pt-4 pb-6 max-h-[60vh] overflow-y-auto flex flex-col gap-5">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="md:col-span-1 flex flex-col gap-2">
                <Label htmlFor="cli-codigo">Código</Label>
                <Input
                  id="cli-codigo"
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
                <Label htmlFor="cli-razon">Razón social *</Label>
                <Input
                  id="cli-razon"
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
                <Label htmlFor="cli-cuit">CUIT</Label>
                <Input
                  id="cli-cuit"
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
                <Label htmlFor="cli-condicion">Condición IVA</Label>
                <AppleSelect
                  id="cli-condicion"
                  value={form.condicion_iva}
                  onChange={(v) => set("condicion_iva", v as CondicionIva)}
                  disabled={loading}
                >
                  {CONDICIONES.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </AppleSelect>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor="cli-receptor">Cond. receptor (RG 5616)</Label>
                <Input
                  id="cli-receptor"
                  type="number"
                  min="0"
                  value={form.condicion_iva_receptor_id}
                  onChange={(e) =>
                    set("condicion_iva_receptor_id", e.target.value)
                  }
                  disabled={loading}
                  placeholder="Opcional"
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="cli-email">Email</Label>
                <Input
                  id="cli-email"
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
                <Label htmlFor="cli-tel">Teléfono</Label>
                <Input
                  id="cli-tel"
                  value={form.telefono}
                  onChange={(e) => set("telefono", e.target.value)}
                  disabled={loading}
                  maxLength={50}
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="cli-dir">Dirección</Label>
                <Input
                  id="cli-dir"
                  value={form.direccion}
                  onChange={(e) => set("direccion", e.target.value)}
                  disabled={loading}
                  maxLength={255}
                />
              </div>
            </div>

            <div className="flex flex-col gap-3 pt-2 border-t border-border">
              <Check
                id="cli-cta"
                label="Habilitar cuenta corriente"
                checked={form.cuenta_corriente}
                onChange={(v) => set("cuenta_corriente", v)}
                disabled={loading}
              />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="flex flex-col gap-2">
                  <Label htmlFor="cli-limite">Límite cta cte</Label>
                  <Input
                    id="cli-limite"
                    type="number"
                    step="0.01"
                    min="0"
                    value={form.limite_cuenta_corriente}
                    onChange={(e) =>
                      set("limite_cuenta_corriente", e.target.value)
                    }
                    disabled={loading || !form.cuenta_corriente}
                    className="tabular-nums"
                  />
                  {errors.limite_cuenta_corriente && (
                    <p className="text-[12px] text-destructive">
                      {errors.limite_cuenta_corriente}
                    </p>
                  )}
                </div>
                <div className="flex items-end pb-1">
                  <Check
                    id="cli-activo"
                    label="Activo"
                    checked={form.activo}
                    onChange={(v) => set("activo", v)}
                    disabled={loading}
                  />
                </div>
              </div>
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
                  : "Crear cliente"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
