import * as React from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { Layers, Loader2, Pencil, Plus, Trash2 } from "lucide-react";
import {
  createRubro,
  deleteRubro,
  listFamilias,
  listRubrosByFamilia,
  updateRubro,
  type Rubro,
  type RubroPayload,
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

export function MantenimientoRubros() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const role = useAuth((s) => s.user?.rol);
  const isAdmin = role === "admin";

  const { data: familias = [], isLoading: famLoading } = useQuery({
    queryKey: ["mant-familias"],
    queryFn: listFamilias,
  });

  const [familiaId, setFamiliaId] = React.useState<number | null>(null);

  React.useEffect(() => {
    if (familiaId === null && familias.length > 0) {
      setFamiliaId(familias[0].id);
    }
  }, [familiaId, familias]);

  const {
    data: rubros = [],
    isLoading: rubLoading,
  } = useQuery({
    queryKey: ["mant-rubros", familiaId],
    queryFn: () => listRubrosByFamilia(familiaId as number),
    enabled: familiaId !== null,
  });

  const [editing, setEditing] = React.useState<Rubro | null>(null);
  const [creating, setCreating] = React.useState(false);
  const [deleteTarget, setDeleteTarget] = React.useState<Rubro | null>(null);

  const deleteMut = useMutation({
    mutationFn: (id: number) => deleteRubro(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mant-rubros", familiaId] });
      toast({ title: "Rubro eliminado" });
      setDeleteTarget(null);
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: { error?: string } } };
      toast({
        title: "No pudimos eliminar",
        description:
          e?.response?.data?.error ?? "Tiene subrubros asociados.",
        variant: "destructive",
      });
    },
  });

  return (
    <Card className="overflow-hidden p-0">
      <div className="flex flex-wrap items-center justify-between gap-3 p-5 border-b border-border">
        <div>
          <h3 className="text-[16px] font-semibold tracking-tight">Rubros</h3>
          <p className="mt-0.5 text-[13px] text-muted-foreground">
            Segundo nivel — anidados bajo familia.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={familiaId ?? ""}
            onChange={(e) =>
              setFamiliaId(e.target.value ? Number(e.target.value) : null)
            }
            disabled={famLoading}
            className={cn(
              "h-9 rounded-[8px] border border-border bg-background px-3 text-[13px] min-w-[180px]",
              "focus:outline-none focus:ring-2 focus:ring-ring",
            )}
          >
            <option value="">Seleccioná familia…</option>
            {familias.map((f) => (
              <option key={f.id} value={f.id}>
                {f.codigo} · {f.nombre}
              </option>
            ))}
          </select>
          <Button
            size="sm"
            onClick={() => setCreating(true)}
            disabled={familiaId === null}
          >
            <Plus className="h-4 w-4" strokeWidth={1.5} />
            Nuevo rubro
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
          {familiaId === null ? (
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={4} className="py-12 text-center">
                <p className="text-[13px] text-muted-foreground">
                  Elegí una familia para ver sus rubros.
                </p>
              </TableCell>
            </TableRow>
          ) : rubLoading ? (
            Array.from({ length: 4 }).map((_, i) => (
              <TableRow key={`sk-${i}`} className="hover:bg-transparent">
                <TableCell colSpan={4}>
                  <Skeleton className="h-5 w-full" />
                </TableCell>
              </TableRow>
            ))
          ) : rubros.length === 0 ? (
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={4} className="py-12">
                <div className="flex flex-col items-center gap-3 text-center">
                  <div className="rounded-full bg-muted/60 p-3">
                    <Layers
                      className="h-5 w-5 text-muted-foreground"
                      strokeWidth={1.5}
                    />
                  </div>
                  <p className="text-[13px] text-muted-foreground">
                    Esta familia no tiene rubros.
                  </p>
                </div>
              </TableCell>
            </TableRow>
          ) : (
            rubros.map((r) => (
              <TableRow
                key={r.id}
                className="cursor-pointer"
                onClick={() => setEditing(r)}
              >
                <TableCell className="font-mono text-[12px] text-muted-foreground">
                  {r.codigo}
                </TableCell>
                <TableCell className="text-[13px] font-medium">
                  {r.nombre}
                </TableCell>
                <TableCell className="text-right tabular-nums text-[13px] text-muted-foreground">
                  {r.orden}
                </TableCell>
                <TableCell>
                  <div
                    className="flex items-center justify-end gap-1"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setEditing(r)}
                      aria-label="Editar"
                    >
                      <Pencil className="h-4 w-4" strokeWidth={1.5} />
                    </Button>
                    {isAdmin && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setDeleteTarget(r)}
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

      <RubroFormDialog
        open={creating || editing !== null}
        onOpenChange={(o) => {
          if (!o) {
            setCreating(false);
            setEditing(null);
          }
        }}
        rubro={editing}
        familiaId={familiaId}
      />

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(o) => {
          if (!o) setDeleteTarget(null);
        }}
        destructive
        title="¿Eliminar rubro?"
        description={`Se eliminará el rubro "${deleteTarget?.nombre ?? ""}".`}
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
  rubro: Rubro | null;
  familiaId: number | null;
}

function RubroFormDialog({
  open,
  onOpenChange,
  rubro,
  familiaId,
}: FormDialogProps) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const editing = rubro !== null;

  const [codigo, setCodigo] = React.useState("");
  const [nombre, setNombre] = React.useState("");
  const [orden, setOrden] = React.useState("0");

  React.useEffect(() => {
    if (open && rubro) {
      setCodigo(rubro.codigo);
      setNombre(rubro.nombre);
      setOrden(String(rubro.orden ?? 0));
    } else if (open) {
      setCodigo("");
      setNombre("");
      setOrden("0");
    }
  }, [open, rubro]);

  const mut = useMutation({
    mutationFn: async () => {
      const payload: RubroPayload = {
        codigo: codigo.trim(),
        nombre: nombre.trim(),
        orden: Number(orden) || 0,
      };
      if (editing && rubro) return updateRubro(rubro.id, payload);
      if (familiaId === null) throw new Error("falta familia");
      return createRubro(familiaId, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mant-rubros", familiaId] });
      toast({
        title: editing ? "Rubro actualizado" : "Rubro creado",
      });
      onOpenChange(false);
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: { error?: string } } };
      toast({
        title: "No pudimos guardar",
        description: e?.response?.data?.error ?? "Revisá los campos.",
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
          <DialogTitle>{editing ? "Editar rubro" : "Nuevo rubro"}</DialogTitle>
          <DialogDescription>Segundo nivel del árbol.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="rub-cod">Código *</Label>
            <Input
              id="rub-cod"
              value={codigo}
              onChange={(e) => setCodigo(e.target.value)}
              maxLength={20}
              disabled={editing || mut.isPending}
              className="font-mono"
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="rub-nom">Nombre *</Label>
            <Input
              id="rub-nom"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              autoFocus
              maxLength={100}
              disabled={mut.isPending}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="rub-ord">Orden</Label>
            <Input
              id="rub-ord"
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
