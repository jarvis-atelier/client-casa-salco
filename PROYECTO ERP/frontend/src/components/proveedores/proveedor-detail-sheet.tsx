import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Pencil, Power } from "lucide-react";
import { listArticulos } from "@/api/articulos";
import { deactivateProveedor } from "@/api/proveedores";
import type { ProveedorFull } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/store/auth";

interface DataRowProps {
  label: string;
  value: React.ReactNode;
}
function DataRow({ label, value }: DataRowProps) {
  return (
    <div className="grid grid-cols-[120px_1fr] gap-3 py-1.5">
      <span className="text-[12px] uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <span className="text-[13px] text-foreground break-words">
        {value ?? "—"}
      </span>
    </div>
  );
}

interface Props {
  proveedor: ProveedorFull | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onEdit: (p: ProveedorFull) => void;
}

export function ProveedorDetailSheet({
  proveedor,
  open,
  onOpenChange,
  onEdit,
}: Props) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const user = useAuth((s) => s.user);
  const isAdmin = user?.rol === "admin";

  const articulosQ = useQuery({
    queryKey: ["articulos", "by-proveedor", proveedor?.id],
    queryFn: () =>
      proveedor
        ? listArticulos({ proveedor_id: proveedor.id, per_page: 1 })
        : Promise.resolve({ items: [], total: 0, page: 1, per_page: 1, pages: 0 }),
    enabled: open && Boolean(proveedor?.id),
    staleTime: 60_000,
  });

  const deactivateM = useMutation({
    mutationFn: (id: number) => deactivateProveedor(id),
    onSuccess: () => {
      toast({
        title: "Proveedor desactivado",
        description: proveedor?.razon_social,
      });
      qc.invalidateQueries({ queryKey: ["proveedores-full"] });
      qc.invalidateQueries({ queryKey: ["proveedores"] });
      onOpenChange(false);
    },
    onError: () => {
      toast({
        title: "No pudimos desactivar",
        description: "Probá de nuevo en un momento.",
        variant: "destructive",
      });
    },
  });

  if (!proveedor) return null;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-[440px] overflow-y-auto p-0"
      >
        <div className="px-6 py-6">
          <SheetHeader>
            <SheetTitle className="text-[20px] font-semibold tracking-tight">
              {proveedor.razon_social}
            </SheetTitle>
            <SheetDescription className="font-mono text-[12px]">
              {proveedor.codigo}
            </SheetDescription>
          </SheetHeader>

          <div className="mt-5">
            <Badge variant={proveedor.activo ? "success" : "secondary"}>
              {proveedor.activo ? "Activo" : "Inactivo"}
            </Badge>
          </div>

          <Separator className="my-5" />

          <div className="flex flex-col">
            <DataRow label="CUIT" value={proveedor.cuit ?? "—"} />
            <DataRow label="Email" value={proveedor.email ?? "—"} />
            <DataRow label="Teléfono" value={proveedor.telefono ?? "—"} />
            <DataRow label="Dirección" value={proveedor.direccion ?? "—"} />
          </div>

          <Separator className="my-5" />

          <div className="flex items-center justify-between">
            <span className="text-[14px] font-semibold tracking-tight">
              Artículos asociados
            </span>
            {articulosQ.isLoading ? (
              <Skeleton className="h-5 w-12" />
            ) : (
              <span className="text-[18px] font-semibold tabular-nums">
                {articulosQ.data?.total ?? 0}
              </span>
            )}
          </div>

          <Separator className="my-5" />

          <div className="flex items-center gap-2">
            <Button
              variant="default"
              onClick={() => onEdit(proveedor)}
              disabled={deactivateM.isPending}
            >
              <Pencil strokeWidth={1.5} />
              Editar
            </Button>
            {isAdmin && proveedor.activo && (
              <Button
                variant="outline"
                onClick={() => deactivateM.mutate(proveedor.id)}
                disabled={deactivateM.isPending}
              >
                {deactivateM.isPending ? (
                  <Loader2 className="animate-spin" strokeWidth={1.5} />
                ) : (
                  <Power strokeWidth={1.5} />
                )}
                Desactivar
              </Button>
            )}
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
