import * as React from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { Folder, Loader2, Pencil, Plus, Trash2 } from "lucide-react";
import {
  createFamilia,
  deleteFamilia,
  listFamilias,
  updateFamilia,
  type Familia,
  type FamiliaPayload,
} from "@/api/mantenimiento";
import { Badge } from "@/components/ui/badge";
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

export function MantenimientoFamilias() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const role = useAuth((s) => s.user?.rol);
  const isAdmin = role === "admin";

  const { data, isLoading, isError } = useQuery({
    queryKey: ["mant-familias"],
    queryFn: listFamilias,
  });

  const [editing, setEditing] = React.useState<Familia | null>(null);
  const [creating, setCreating] = React.useState(false);
  const [deleteTarget, setDeleteTarget] = React.useState<Familia | null>(null);

  const deleteMut = useMutation({
    mutationFn: (id: number) => deleteFamilia(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mant-familias"] });
      toast({ title: "Familia eliminada" });
      setDeleteTarget(null);
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: { error?: string } } };
      toast({
        title: "No pudimos eliminar",
        description: e?.response?.data?.error ?? "Tiene rubros asociados.",
        variant: "destructive",
      });
    },
  });

  return (
    <Card className="overflow-hidden p-0">
      <div className="flex items-center justify-between p-5 border-b border-border">
        <div>
          <h3 className="text-[16px] font-semibold tracking-tight">Familias</h3>
          <p className="mt-0.5 text-[13px] text-muted-foreground">
            Primer nivel de la taxonomía de artículos.
          </p>
        </div>
        <Button size="sm" onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4" strokeWidth={1.5} />
          Nueva familia
        </Button>
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
          {isLoading
            ? Array.from({ length: 4 }).map((_, i) => (
                <TableRow key={`sk-${i}`} className="hover:bg-transparent">
                  <TableCell colSpan={4}>
                    <Skeleton className="h-5 w-full" />
                  </TableCell>
                </TableRow>
              ))
            : (data ?? []).map((f) => (
                <TableRow
                  key={f.id}
                  className="cursor-pointer"
                  onClick={() => setEditing(f)}
                >
                  <TableCell className="font-mono text-[12px] text-muted-foreground">
                    {f.codigo}
                  </TableCell>
                  <TableCell className="text-[13px] font-medium">
                    {f.nombre}
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-[13px] text-muted-foreground">
                    {f.orden}
                  </TableCell>
                  <TableCell>
                    <div
                      className="flex items-center justify-end gap-1"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setEditing(f)}
                        aria-label="Editar"
                      >
                        <Pencil className="h-4 w-4" strokeWidth={1.5} />
                      </Button>
                      {isAdmin && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setDeleteTarget(f)}
                          aria-label="Eliminar"
                        >
                          <Trash2 className="h-4 w-4" strokeWidth={1.5} />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
          {!isLoading && (data ?? []).length === 0 && (
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={4} className="py-12">
                <div className="flex flex-col items-center gap-3 text-center">
                  <div className="rounded-full bg-muted/60 p-3">
                    <Folder
                      className="h-5 w-5 text-muted-foreground"
                      strokeWidth={1.5}
                    />
                  </div>
                  <p className="text-[13px] text-muted-foreground">
                    No hay familias cargadas.
                  </p>
                </div>
              </TableCell>
            </TableRow>
          )}
          {isError && (
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={4} className="py-8 text-center">
                <Badge variant="destructive">No pudimos cargar familias</Badge>
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      <FamiliaFormDialog
        open={creating || editing !== null}
        onOpenChange={(o) => {
          if (!o) {
            setCreating(false);
            setEditing(null);
          }
        }}
        familia={editing}
      />

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(o) => {
          if (!o) setDeleteTarget(null);
        }}
        destructive
        title="¿Eliminar familia?"
        description={`Se eliminará la familia "${deleteTarget?.nombre ?? ""}". Si tiene rubros asociados, fallará.`}
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
  familia: Familia | null;
}

function FamiliaFormDialog({ open, onOpenChange, familia }: FormDialogProps) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const editing = familia !== null;

  const [codigo, setCodigo] = React.useState("");
  const [nombre, setNombre] = React.useState("");
  const [orden, setOrden] = React.useState("0");

  React.useEffect(() => {
    if (open && familia) {
      setCodigo(familia.codigo);
      setNombre(familia.nombre);
      setOrden(String(familia.orden ?? 0));
    } else if (open) {
      setCodigo("");
      setNombre("");
      setOrden("0");
    }
  }, [open, familia]);

  const mut = useMutation({
    mutationFn: async () => {
      const payload: FamiliaPayload = {
        codigo: codigo.trim(),
        nombre: nombre.trim(),
        orden: Number(orden) || 0,
      };
      if (editing && familia) {
        return updateFamilia(familia.id, payload);
      }
      return createFamilia(payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mant-familias"] });
      toast({
        title: editing ? "Familia actualizada" : "Familia creada",
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
          <DialogTitle>
            {editing ? "Editar familia" : "Nueva familia"}
          </DialogTitle>
          <DialogDescription>
            Catálogo maestro — primer nivel.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="fam-cod">Código *</Label>
            <Input
              id="fam-cod"
              value={codigo}
              onChange={(e) => setCodigo(e.target.value)}
              maxLength={20}
              disabled={editing || mut.isPending}
              className="font-mono"
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="fam-nom">Nombre *</Label>
            <Input
              id="fam-nom"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              maxLength={100}
              autoFocus
              disabled={mut.isPending}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="fam-ord">Orden</Label>
            <Input
              id="fam-ord"
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
