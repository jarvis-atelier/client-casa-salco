import * as React from "react";
import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { usePwaInstall } from "@/hooks/use-pwa-install";
import { useToast } from "@/hooks/use-toast";

/**
 * Botón sutil en topbar — se muestra solo si el browser disparó
 * `beforeinstallprompt` (Chrome / Edge / Android). En iOS muestra hint manual.
 */
export function InstallButton() {
  const { canInstall, isInstalled, isIOS, promptInstall } = usePwaInstall();
  const { toast } = useToast();

  const onClick = React.useCallback(async () => {
    if (isIOS) {
      toast({
        title: "Instalá Jarvis Core en tu iPhone",
        description:
          "Tocá Compartir → Añadir a pantalla principal para usarlo como app.",
      });
      return;
    }
    const outcome = await promptInstall();
    if (outcome === "accepted") {
      toast({
        title: "Jarvis Core instalado",
        description: "Ahora podés abrirlo desde tu pantalla principal.",
      });
    }
  }, [isIOS, promptInstall, toast]);

  if (isInstalled) return null;
  if (!canInstall && !isIOS) return null;

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={onClick}
      aria-label="Instalar Jarvis Core como app"
      title="Instalar como app"
    >
      <Download className="h-[18px] w-[18px]" strokeWidth={1.5} />
    </Button>
  );
}
