import { Link, createRoute } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { rootRoute } from "./root";

export const notFoundRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "*",
  component: NotFoundPage,
});

function NotFoundPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="flex flex-col items-center gap-6 text-center max-w-md">
        <span className="text-[80px] font-semibold tracking-tight leading-none text-muted-foreground/40 tabular-nums">
          404
        </span>
        <div className="flex flex-col gap-2">
          <h1 className="text-[22px] font-semibold tracking-tight">
            Página no encontrada
          </h1>
          <p className="text-[14px] text-muted-foreground">
            La ruta que buscás no existe o fue movida.
          </p>
        </div>
        <Button asChild>
          <Link to="/">Volver al inicio</Link>
        </Button>
      </div>
    </div>
  );
}
