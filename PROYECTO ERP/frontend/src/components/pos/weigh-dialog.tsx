/**
 * Modal de pesaje — para confirmar visualmente el peso antes de cargarlo.
 *
 * Cuando se abre, hace polling cada 500 ms a `/scale/weight`. Muestra:
 * - el peso actual en grande con tabular-nums
 * - un dot que indica estabilidad (emerald = stable, amber = motion)
 * - botones Tarar / Confirmar / Cancelar
 *
 * Si la balanza no responde, mostramos el error del agente y deshabilitamos
 * "Confirmar" — el usuario puede cerrar y entrar manualmente.
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2, Scale, X } from "lucide-react";
import { readWeight, tareScale } from "@/api/agent";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

interface WeighDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  articuloDescripcion: string;
  onConfirm: (kg: number) => void;
}

export function WeighDialog({
  open,
  onOpenChange,
  articuloDescripcion,
  onConfirm,
}: WeighDialogProps) {
  const { toast } = useToast();

  const query = useQuery({
    queryKey: ["scale-weight"],
    queryFn: readWeight,
    enabled: open,
    refetchInterval: open ? 500 : false,
    refetchOnWindowFocus: false,
    retry: 0,
    staleTime: 0,
    gcTime: 0,
  });

  const tareMutation = useMutation({
    mutationFn: tareScale,
    onSuccess: () => {
      toast({
        title: "Balanza tarada",
        description: "El peso del recipiente quedó en cero.",
      });
      query.refetch();
    },
    onError: () => {
      toast({
        title: "No se pudo tarar",
        description: "Verificá que la balanza esté conectada.",
        variant: "destructive",
      });
    },
  });

  const reading = query.data;
  const kgString = reading?.weight_kg ?? "0.000";
  const stable = reading?.stable ?? false;
  const isError = !!query.error;

  const handleConfirm = () => {
    if (!reading) return;
    const kg = parseFloat(reading.weight_kg);
    if (!Number.isFinite(kg) || kg <= 0) {
      toast({
        title: "Peso inválido",
        description: "La balanza devolvió un valor en cero o no numérico.",
        variant: "destructive",
      });
      return;
    }
    if (!stable) {
      toast({
        title: "Peso no estable",
        description: "Esperá un momento a que la balanza se asiente.",
        variant: "destructive",
      });
      return;
    }
    onConfirm(kg);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Scale className="h-5 w-5" strokeWidth={1.5} />
            Pesar artículo
          </DialogTitle>
          <DialogDescription className="truncate">
            {articuloDescripcion}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col items-center gap-4 py-4">
          {isError ? (
            <div className="flex flex-col items-center gap-2 text-center">
              <X className="h-8 w-8 text-rose-500" strokeWidth={1.5} />
              <p className="text-[14px] font-medium">
                Balanza no responde
              </p>
              <p className="text-[12px] text-muted-foreground max-w-xs">
                Revisá el cable serial / Ethernet o el estado del agente local.
                Mientras tanto podés cargar la cantidad a mano.
              </p>
            </div>
          ) : (
            <>
              <div className="flex items-baseline gap-2">
                <span className="text-5xl font-semibold tabular-nums tracking-tight">
                  {kgString}
                </span>
                <span className="text-[14px] text-muted-foreground">kg</span>
              </div>

              <div className="flex items-center gap-2 text-[12px]">
                <span
                  className={cn(
                    "inline-block h-2 w-2 rounded-full transition-colors",
                    stable
                      ? "bg-emerald-500 shadow-[0_0_4px_rgba(16,185,129,0.6)]"
                      : "bg-amber-500",
                  )}
                />
                <span
                  className={cn(
                    stable ? "text-emerald-600" : "text-amber-600",
                  )}
                >
                  {stable ? "Estable" : "Esperá un momento…"}
                </span>
                {query.isFetching && (
                  <Loader2
                    className="h-3 w-3 animate-spin text-muted-foreground"
                    strokeWidth={1.5}
                  />
                )}
              </div>

              {reading && parseFloat(reading.tare_kg) > 0 && (
                <p className="text-[11px] text-muted-foreground tabular-nums">
                  Tara: {reading.tare_kg} kg
                </p>
              )}
            </>
          )}
        </div>

        <DialogFooter className="sm:justify-between gap-2">
          <Button
            variant="outline"
            onClick={() => tareMutation.mutate()}
            disabled={tareMutation.isPending || isError}
          >
            {tareMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.5} />
                Tarando…
              </>
            ) : (
              "Tarar"
            )}
          </Button>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button
              onClick={handleConfirm}
              disabled={isError || !reading || !stable}
            >
              Confirmar peso
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default WeighDialog;
