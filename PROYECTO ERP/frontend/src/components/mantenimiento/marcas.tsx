import * as React from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { Loader2, Pencil, Plus, Sparkles, Trash2 } from "lucide-react";
import {
  createMarca,
  deleteMarca,
  listMarcasFull,
  updateMarca,
  type MarcaFull,
  type MarcaPayload,
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

export function MantenimientoMarcas() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const role = useAuth((s) => s.user?.rol);
  const isAdmin = role === "admin";

  const { data, isLoading } = useQuery({
    queryKey: ["mant-marcas"],
    queryFn: listMarcasFull,
  });

  const [busqueda, setBusqueda] = React.useState("");
  const [editing, setEditing] = React.useState<MarcaFull | null>(null);
  const [creating, setCreating] = React.useState(false);
  const [deleteTarget, setDeleteTarget] = React.useState<MarcaFull | null>(
    null,
  );

  const filtered = React.useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    if (!q) return data ?? [];
    return (data ?? []).filter((m) => m.nombre.toLowerCase().includes(q));
  }, [data, busqueda]);

  const deleteMut = useMutation({
    mutationFn: (id: number) => deleteMarca(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mant-marcas"] });
      toast({ title: "Marca eliminada" });
      setDeleteTarget(null);
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: { error?: string } } };
      toast({
        title: "No pudimos eliminar",
        description: e?.response?.data?.error ?? "Está en uso por artículos.",
        variant: "destructive",
      });
    },
  });

  return (
    <Card className="overflow-hidden p-0">
      <div className="flex flex-wrap items-center justify-between gap-3 p-5 border-b border-border">
        <div>
          <h3 className="text-[16px] font-semibold tracking-tight">Marcas</h3>
          <p className="mt-0.5 text-[13px] text-muted-foreground">
            Catálogo de marcas asignables a artículos.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Input
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            placeholder="Buscar marca…"
            className="h-9 w-[220px]"
          />
          <Button size="sm" onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" strokeWidth={1.5} />
            Nueva marca
          </Button>
        </div>
      </div>

      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead>Nombre</TableHead>
            <TableHead className="w-[100px]">Estado</TableHead>
            <TableHead className="w-[140px]" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <TableRow key={`sk-${i}`} className="hover:bg-transparent">
                <TableCell colSpan={3}>
                  <Skeleton className="h-5 w-full" />
                </TableCell>
              </TableRow>
            ))
          ) : filtered.length === 0 ? (
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={3} className="py-12">
                <div className="flex flex-col items-center gap-3 text-center">
                  <div className="rounded-full bg-muted/60 p-3">
                    <Sparkles
                      className="h-5 w-5 text-muted-foreground"
                      strokeWidth={1.5}
                    />
                  </div>
                  <p className="text-[13px] text-muted-foreground">
                    No hay marcas que coincidan.
                  </p>
                </div>
              </TableCell>
            </TableRow>
          ) : (
            filtered.map((m) => (
              <TableRow
                key={m.id}
                className="cursor-pointer"
                onClick={() => setEditing(m)}
              >
                <TableCell className="text-[13px] font-medium">
                  {m.nombre}
                </TableCell>
                <TableCell>
                  {m.activa ? (
                    <Badge variant="success">Activa</Badge>
                  ) : (
                    <Badge variant="secondary">Inactiva</Badge>
                  )}
                </TableCell>
                <TableCell>
                  <div
                    className="flex items-center justify-end gap-1"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setEditing(m)}
                      aria-label="Editar"
                    >
                      <Pencil className="h-4 w-4" strokeWidth={1.5} />
                    </Button>
                    {isAdmin && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setDeleteTarget(m)}
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

      <MarcaFormDialog
        open={creating || editing !== null}
        onOpenChange={(o) => {
          if (!o) {
            setCreating(false);
            setEditing(null);
          }
        }}
        marca={editing}
      />

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(o) => {
          if (!o) setDeleteTarget(null);
        }}
        destructive
        title="¿Eliminar marca?"
        description={`Se eliminará la marca "${deleteTarget?.nombre ?? ""}".`}
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
  marca: MarcaFull | null;
}

function MarcaFormDialog({ open, onOpenChange, marca }: FormDialogProps) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const editing = marca !== null;

  const [nombre, setNombre] = React.useState("");
  const [activa, setActiva] = React.useState(true);

  React.useEffect(() => {
    if (open && marca) {
      setNombre(marca.nombre);
      setActiva(Boolean(marca.activa));
    } else if (open) {
      setNombre("");
      setActiva(true);
    }
  }, [open, marca]);

  const mut = useMutation({
    mutationFn: async () => {
      const payload: MarcaPayload = { nombre: nombre.trim(), activa };
      if (editing && marca) return updateMarca(marca.id, payload);
      return createMarca(payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mant-marcas"] });
      toast({ title: editing ? "Marca actualizada" : "Marca creada" });
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
    if (!nombre.trim()) return;
    mut.mutate();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[440px]">
        <DialogHeader>
          <DialogTitle>{editing ? "Editar marca" : "Nueva marca"}</DialogTitle>
          <DialogDescription>Catálogo de marcas.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="mc-nom">Nombre *</Label>
            <Input
              id="mc-nom"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              autoFocus
              maxLength={100}
              disabled={mut.isPending}
            />
          </div>
          <label className="flex items-center gap-2.5 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={activa}
              onChange={(e) => setActiva(e.target.checked)}
              className="h-4 w-4 rounded-[4px] border border-input accent-primary"
              disabled={mut.isPending}
            />
            <span className="text-[13px] text-foreground">Activa</span>
          </label>
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
