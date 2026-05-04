import * as React from "react";
import { Download, Loader2 } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

interface ExportCardProps {
  title: string;
  description: string;
  /** Acción async — debe disparar la descarga; si throwea se muestra toast error. */
  onDownload: () => Promise<void>;
  /** Form opcional con filtros (date pickers, sucursal). */
  children?: React.ReactNode;
  /** Botón disabled si los filtros no son válidos. */
  disabled?: boolean;
  /** Texto del botón (por defecto: "Descargar .xlsx"). */
  buttonLabel?: string;
}

export function ExportCard({
  title,
  description,
  onDownload,
  children,
  disabled,
  buttonLabel = "Descargar .xlsx",
}: ExportCardProps) {
  const { toast } = useToast();
  const [busy, setBusy] = React.useState(false);

  const handleClick = React.useCallback(async () => {
    setBusy(true);
    try {
      await onDownload();
      toast({
        title: "Exportación lista",
        description: `${title} se descargó correctamente.`,
      });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "No se pudo generar el archivo.";
      toast({
        title: "Error al exportar",
        description: message,
        variant: "destructive",
      });
    } finally {
      setBusy(false);
    }
  }, [onDownload, toast, title]);

  return (
    <Card className={cn("flex flex-col")}>
      <CardHeader>
        <CardTitle className="text-[16px]">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-4">
        {children ? <div className="flex flex-col gap-3">{children}</div> : null}
        <div className="flex-1" />
        <Button
          onClick={handleClick}
          disabled={disabled || busy}
          className="self-start"
        >
          {busy ? (
            <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.5} />
          ) : (
            <Download className="h-4 w-4" strokeWidth={1.5} />
          )}
          {busy ? "Generando…" : buttonLabel}
        </Button>
      </CardContent>
    </Card>
  );
}
