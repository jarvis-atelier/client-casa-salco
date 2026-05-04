import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Save } from "lucide-react";
import {
  getComercio,
  updateComercio,
  type ComercioConfig,
  type ComercioUpdatePayload,
} from "@/api/comercio";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

const CONDICIONES_IVA = [
  "Responsable Inscripto",
  "Monotributo",
  "Exento",
  "Consumidor Final",
  "No Responsable",
];

interface FormState {
  razon_social: string;
  nombre_fantasia: string;
  cuit: string;
  condicion_iva: string;
  domicilio: string;
  localidad: string;
  provincia: string;
  cp: string;
  telefono: string;
  email: string;
  iibb: string;
  inicio_actividades: string;
  pie_ticket: string;
}

const EMPTY: FormState = {
  razon_social: "",
  nombre_fantasia: "",
  cuit: "",
  condicion_iva: "Responsable Inscripto",
  domicilio: "",
  localidad: "",
  provincia: "",
  cp: "",
  telefono: "",
  email: "",
  iibb: "",
  inicio_actividades: "",
  pie_ticket: "",
};

function fromConfig(c: ComercioConfig | undefined): FormState {
  if (!c) return EMPTY;
  return {
    razon_social: c.razon_social ?? "",
    nombre_fantasia: c.nombre_fantasia ?? "",
    cuit: c.cuit ?? "",
    condicion_iva: c.condicion_iva || "Responsable Inscripto",
    domicilio: c.domicilio ?? "",
    localidad: c.localidad ?? "",
    provincia: c.provincia ?? "",
    cp: c.cp ?? "",
    telefono: c.telefono ?? "",
    email: c.email ?? "",
    iibb: c.iibb ?? "",
    inicio_actividades: c.inicio_actividades ?? "",
    pie_ticket: c.pie_ticket ?? "",
  };
}

const CUIT_REGEX = /^\d{2}-?\d{8}-?\d{1}$/;

export function ComercioForm() {
  const { toast } = useToast();
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["comercio"],
    queryFn: getComercio,
  });

  const [form, setForm] = React.useState<FormState>(EMPTY);
  const [errors, setErrors] = React.useState<
    Partial<Record<keyof FormState, string>>
  >({});

  React.useEffect(() => {
    if (data) setForm(fromConfig(data));
  }, [data]);

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((f) => ({ ...f, [key]: value }));
    if (errors[key]) setErrors((prev) => ({ ...prev, [key]: undefined }));
  };

  const mutation = useMutation({
    mutationFn: async (p: ComercioUpdatePayload) => updateComercio(p),
    onSuccess: () => {
      toast({
        title: "Configuración guardada",
        description: "Los datos del comercio se actualizaron.",
      });
      qc.invalidateQueries({ queryKey: ["comercio"] });
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: { error?: string } } };
      toast({
        title: "No pudimos guardar",
        description:
          e?.response?.data?.error ?? "Revisá los campos e intentá de nuevo.",
        variant: "destructive",
      });
    },
  });

  const validate = (): boolean => {
    const errs: Partial<Record<keyof FormState, string>> = {};
    if (!form.razon_social.trim()) errs.razon_social = "Requerido";
    if (form.cuit.trim() && !CUIT_REGEX.test(form.cuit.trim()))
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
    const payload: ComercioUpdatePayload = {
      razon_social: form.razon_social.trim(),
      nombre_fantasia: form.nombre_fantasia.trim() || null,
      cuit: form.cuit.trim(),
      condicion_iva: form.condicion_iva.trim(),
      domicilio: form.domicilio.trim() || null,
      localidad: form.localidad.trim() || null,
      provincia: form.provincia.trim() || null,
      cp: form.cp.trim() || null,
      telefono: form.telefono.trim() || null,
      email: form.email.trim() || null,
      iibb: form.iibb.trim() || null,
      inicio_actividades: form.inicio_actividades || null,
      pie_ticket: form.pie_ticket.trim() || null,
    };
    mutation.mutate(payload);
  };

  if (isLoading) {
    return (
      <Card className="p-8">
        <Skeleton className="h-7 w-48 mb-6" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      </Card>
    );
  }

  const loading = mutation.isPending;

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-5">
      <Card className="p-8 flex flex-col gap-6">
        <div>
          <h3 className="text-[16px] font-semibold tracking-tight">
            Datos del comercio
          </h3>
          <p className="mt-1 text-[13px] text-muted-foreground">
            Estos datos van al header de los tickets, facturas y otros
            comprobantes impresos.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="md:col-span-2 flex flex-col gap-2">
            <Label htmlFor="cm-razon">Razón social *</Label>
            <Input
              id="cm-razon"
              value={form.razon_social}
              onChange={(e) => set("razon_social", e.target.value)}
              maxLength={200}
              disabled={loading}
            />
            {errors.razon_social && (
              <p className="text-[12px] text-destructive">
                {errors.razon_social}
              </p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="cm-fantasia">Nombre de fantasía</Label>
            <Input
              id="cm-fantasia"
              value={form.nombre_fantasia}
              onChange={(e) => set("nombre_fantasia", e.target.value)}
              maxLength={200}
              disabled={loading}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="cm-cuit">CUIT</Label>
            <Input
              id="cm-cuit"
              value={form.cuit}
              onChange={(e) => set("cuit", e.target.value)}
              maxLength={13}
              placeholder="XX-XXXXXXXX-X"
              className="font-mono"
              disabled={loading}
            />
            {errors.cuit && (
              <p className="text-[12px] text-destructive">{errors.cuit}</p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="cm-cond">Condición IVA</Label>
            <select
              id="cm-cond"
              value={form.condicion_iva}
              onChange={(e) => set("condicion_iva", e.target.value)}
              disabled={loading}
              className={cn(
                "flex h-10 w-full items-center rounded-lg border border-input bg-background px-3 text-[14px]",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                "disabled:cursor-not-allowed disabled:opacity-50",
              )}
            >
              {CONDICIONES_IVA.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="cm-iibb">IIBB</Label>
            <Input
              id="cm-iibb"
              value={form.iibb}
              onChange={(e) => set("iibb", e.target.value)}
              maxLength={50}
              placeholder="900-XXXXXX"
              className="font-mono"
              disabled={loading}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="cm-dom">Domicilio</Label>
            <Input
              id="cm-dom"
              value={form.domicilio}
              onChange={(e) => set("domicilio", e.target.value)}
              maxLength={200}
              disabled={loading}
            />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="flex flex-col gap-2">
              <Label htmlFor="cm-loc">Localidad</Label>
              <Input
                id="cm-loc"
                value={form.localidad}
                onChange={(e) => set("localidad", e.target.value)}
                maxLength={100}
                disabled={loading}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="cm-prov">Provincia</Label>
              <Input
                id="cm-prov"
                value={form.provincia}
                onChange={(e) => set("provincia", e.target.value)}
                maxLength={100}
                disabled={loading}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="cm-cp">CP</Label>
              <Input
                id="cm-cp"
                value={form.cp}
                onChange={(e) => set("cp", e.target.value)}
                maxLength={10}
                disabled={loading}
                className="tabular-nums"
              />
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="cm-tel">Teléfono</Label>
            <Input
              id="cm-tel"
              value={form.telefono}
              onChange={(e) => set("telefono", e.target.value)}
              maxLength={50}
              disabled={loading}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="cm-mail">Email</Label>
            <Input
              id="cm-mail"
              type="email"
              value={form.email}
              onChange={(e) => set("email", e.target.value)}
              maxLength={120}
              disabled={loading}
            />
            {errors.email && (
              <p className="text-[12px] text-destructive">{errors.email}</p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="cm-ini">Inicio de actividades</Label>
            <Input
              id="cm-ini"
              type="date"
              value={form.inicio_actividades}
              onChange={(e) => set("inicio_actividades", e.target.value)}
              disabled={loading}
            />
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <Label htmlFor="cm-pie">Pie de ticket</Label>
          <Input
            id="cm-pie"
            value={form.pie_ticket}
            onChange={(e) => set("pie_ticket", e.target.value)}
            maxLength={255}
            placeholder="Gracias por su compra"
            disabled={loading}
          />
        </div>
      </Card>

      <div className="flex items-center justify-end gap-3">
        <Button type="submit" disabled={loading}>
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.5} />
          ) : (
            <Save className="h-4 w-4" strokeWidth={1.5} />
          )}
          {loading ? "Guardando…" : "Guardar"}
        </Button>
      </div>
    </form>
  );
}
