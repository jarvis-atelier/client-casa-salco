import * as React from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { Layers3, Loader2, Pencil, Plus, Trash2 } from "lucide-react";
import {
  createSubrubro,
  deleteSubrubro,
  listFamilias,
  listRubrosByFamilia,
  listSubrubrosByRubro,
  updateSubrubro,
  type Subrubro,
  type SubrubroPayload,
} from "@/api/mantenimiento";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { AlertDialog } from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/store/auth";
import { cn } from "@/lib/utils";

export function MantenimientoSubrubros() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const role = useAuth((s) => s.user?.rol);
  const isAdmin = role === "admin";

  const { data: familias = [] } = useQuery({
    queryKey: ["mant-familias"],
    queryFn: listFamilias,
  });

  const [familiaId, setFamiliaId] = React.useState<number | null>(null);
  const [rubroId, setRubroId] = React.useState<number | null>(null);

  React.useEffect(() => {
    if (familiaId === null && familias.length > 0) {
      setFamiliaId(familias[0].id);
    }
  }, [familiaId, familias]);

  const { data: rubros = [] } = useQuery({
    queryKey: ["mant-rubros", familiaId],
    queryFn: () => listRubrosByFamilia(familiaId as number),
    enabled: familiaId !== null,
  });

  React.useEffect(() => {
    setRubroId(null);
  }, [familiaId]);
  React.useEffect(() => {
    if (rubroId === null && rubros.length > 0) {
      setRubroId(rubros[0].id);
    }
  }, [rubroId, rubros]);

  const { data: subrubros = [], isLoading } = useQuery({
    queryKey: ["mant-subrubros", rubroId],
    queryFn: () => listSubrubrosByRubro(rubroId as number),
    enabled: rubroId !== null,
  });

  const [editing, setEditing] = React.useState<Subrubro | null>(null);
  const [creating, setCreating] = React.useState(false);
  const [deleteTarget, setDeleteTarget] = React.useState<Subrubro | null>(null);

  const deleteMut = useMutation({
    mutationFn: (id: number) => deleteSubrubro(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mant-subrubros", rubroId] });
      toast({ title: "Subrubro eliminado" });
      setDeleteTarget(null);
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: { error?: string } } };
      toast({
        title: "No pudimos eliminar",
        description: e?.response?.data?.error ?? "",
        variant: "destructive",
      });
    },
  });

  return (
    <Card className="overflow-hidden p-0">
      <div className="flex flex-wrap items-center justify-between gap-3 p-5 border-b border-border">
        <div>
          <h3 className="text-[16px] font-semibold tracking-tight">
            Subrubros
          </h3>
          <p className="mt-0.5 text-[13px] text-muted-foreground">
            Tercer nivel — anidado bajo rubro.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={familiaId ?? ""}
            onChange={(e) =>
              setFamiliaId(e.target.value ? Number(e.target.value) : null)
            }
            className={cn(
              "h-9 rounded-[8px] border border-border bg-background px-3 text-[13px] min-w-[160px]",
              "focus:outline-none focus:ring-2 focus:ring-ring",
            )}
          >
            <option value="">Familia…</option>
            {familias.map((f) => (
              <option key={f.id} value={f.id}>
                {f.codigo} · {f.nombre}
              </option>
            ))}
          </select>
          <select
            value={rubroId ?? ""}
            onChange={(e) =>
              setRubroId(e.target.value ? Number(e.target.value) : null)
            }
            disabled={familiaId === null}
            className={cn(
              "h-9 rounded-[8px] border border-border bg-background px-3 text-[13px] min-w-[160px]",
              "focus:outline-none focus:ring-2 focus:ring-ring",
              "disabled:opacity-50 disabled:cursor-not-allowed",
            )}
          >
            <option value="">Rubro…</option>
            {rubros.map((r) => (
              <option key={r.id} value={r.id}>
                {r.codigo} · {r.nombre}
              </option>
            ))}
          </select>
          <Button
            size="sm"
            onClick={() => setCreating(true)}
            disabled={rubroId === null}
          >
            <Plus className="h-4 w-4" strokeWidth={1.5} />
            Nuevo subrubro
          </Button>
        </div>
      </div>

      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="w-[140px]">Código</TableHead>
            <TableHead>Nombre</TableHead>
            <TableHead className="w-[100px] text-right">Orden</TableHead>
            <TableHead className="w-[140px]" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {rubroId === null ? (
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={4} className="py-12 text-center">
                <p className="text-[13px] text-muted-foreground">
                  Elegí familia y rubro.
                </p>
              </TableCell>
            </TableRow>
          ) : isLoading ? (
            Array.from({ length: 4 }).map((_, i) => (
              <TableRow key={`sk-${i}`} className="hover:bg-transparent">
                <TableCell colSpan={4}>
                  <Skeleton className="h-5 w-full" />
                </TableCell>
              </TableRow>
            ))
          ) : subrubros.length === 0 ? (
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={4} className="py-12">
                <div className="flex flex-col items-center gap-3 text-center">
                  <div className="rounded-full bg-muted/60 p-3">
                    <Layers3
                      className="h-5 w-5 text-muted-foreground"
                      strokeWidth={1.5}
                    />
                  </div>
                  <p className="text-[13px] text-muted-foreground">
                    Este rubro no tiene subrubros.
                  </p>
                </div>
              </TableCell>
            </TableRow>
          ) : (
            subrubros.map((s) => (
              <TableRow
                key={s.id}
                className="cursor-pointer"
                onClick={() => setEditing(s)}
              >
                <TableCell className="font-mono text-[12px] text-muted-foreground">
                  {s.codigo}
                </TableCell>
                <TableCell className="text-[13px] font-medium">
                  {s.nombre}
                </TableCell>
                <TableCell className="text-right tabular-nums text-[13px] text-muted-foreground">
                  {s.orden}
                </TableCell>
                <TableCell>
                  <div
                    className="flex items-center justify-end gap-1"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setEditing(s)}
                      aria-label="Editar"
                    >
                      <Pencil className="h-4 w-4" strokeWidth={1.5} />
                    </Button>
                    {isAdmin && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setDeleteTarget(s)}
                        aria-label="Eliminar"
                      >
                        <Trash2 className="h-4 w-4" strokeWidth={1.5} />
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      <SubrubroFormDialog
        open={creating || editing !== null}
        onOpenChange={(o) => {
          if (!o) {
            setCreating(false);
            setEditing(null);
          }
        }}
        subrubro={editing}
        rubroId={rubroId}
      />

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(o) => {
          if (!o) setDeleteTarget(null);
        }}
        destructive
        title="¿Eliminar subrubro?"
        description={`Se eliminará el subrubro "${deleteTarget?.nombre ?? ""}".`}
        confirmLabel={deleteMut.isPending ? "Eliminando…" : "Eliminar"}
        cancelLabel="Cancelar"
        loading={deleteMut.isPending}
        onConfirm={() => {
          if (deleteTarget) deleteMut.mutate(deleteTarget.id);
        }}
      />
    </Card>
  );
}

interface FormDialogProps {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  subrubro: Subrubro | null;
  rubroId: number | null;
}

function SubrubroFormDialog({
  open,
  onOpenChange,
  subrubro,
  rubroId,
}: FormDialogProps) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const editing = subrubro !== null;

  const [codigo, setCodigo] = React.useState("");
  const [nombre, setNombre] = React.useState("");
  const [orden, setOrden] = React.useState("0");

  React.useEffect(() => {
    if (open && subrubro) {
      setCodigo(subrubro.codigo);
      setNombre(subrubro.nombre);
      setOrden(String(subrubro.orden ?? 0));
    } else if (open) {
      setCodigo("");
      setNombre("");
      setOrden("0");
    }
  }, [open, subrubro]);

  const mut = useMutation({
    mutationFn: async () => {
      const payload: SubrubroPayload = {
        codigo: codigo.trim(),
        nombre: nombre.trim(),
        orden: Number(orden) || 0,
      };
      if (editing && subrubro) return updateSubrubro(subrubro.id, payload);
      if (rubroId === null) throw new Error("falta rubro");
      return createSubrubro(rubroId, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mant-subrubros", rubroId] });
      toast({ title: editing ? "Subrubro actualizado" : "Subrubro creado" });
      onOpenChange(false);
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: { error?: string } } };
      toast({
        title: "No pudimos guardar",
        description: e?.response?.data?.error ?? "",
        variant: "destructive",
      });
    },
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!codigo.trim() || !nombre.trim()) return;
    mut.mutate();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[480px]">
        <DialogHeader>
          <DialogTitle>
            {editing ? "Editar subrubro" : "Nuevo subrubro"}
          </DialogTitle>
          <DialogDescription>Tercer nivel.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="sub-cod">Código *</Label>
            <Input
              id="sub-cod"
              value={codigo}
              onChange={(e) => setCodigo(e.target.value)}
              maxLength={20}
              disabled={editing || mut.isPending}
              className="font-mono"
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="sub-nom">Nombre *</Label>
            <Input
              id="sub-nom"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              autoFocus
              maxLength={100}
              disabled={mut.isPending}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="sub-ord">Orden</Label>
            <Input
              id="sub-ord"
              type="number"
              value={orden}
              onChange={(e) => setOrden(e.target.value)}
              disabled={mut.isPending}
              className="tabular-nums max-w-[120px]"
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={mut.isPending}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={mut.isPending}>
              {mut.isPending && (
                <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.5} />
              )}
              {editing ? "Guardar cambios" : "Crear"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
