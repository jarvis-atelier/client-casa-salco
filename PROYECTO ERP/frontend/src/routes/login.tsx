import * as React from "react";
import { createRoute, redirect, useNavigate } from "@tanstack/react-router";
import { AxiosError } from "axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/store/auth";
import { login } from "@/api/auth";
import { rootRoute } from "./root";

export const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  beforeLoad: () => {
    const { accessToken } = useAuth.getState();
    if (accessToken) {
      throw redirect({ to: "/" });
    }
  },
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const setAuth = useAuth((s) => s.login);

  const [email, setEmail] = React.useState("admin@casasalco.app");
  const [password, setPassword] = React.useState("");
  const [loading, setLoading] = React.useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      toast({
        title: "Datos incompletos",
        description: "Ingresá tu email y contraseña.",
        variant: "destructive",
      });
      return;
    }
    setLoading(true);
    try {
      const data = await login(email, password);
      setAuth(data);
      navigate({ to: "/" });
    } catch (err) {
      const message =
        err instanceof AxiosError
          ? err.response?.status === 401
            ? "Credenciales inválidas"
            : err.response?.data?.message ?? "No pudimos iniciar sesión"
          : "No pudimos iniciar sesión";
      toast({
        title: "Error al ingresar",
        description: message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-[400px]">
        <div className="rounded-2xl bg-card shadow-apple-lg p-10 border border-border">
          <div className="flex flex-col items-center mb-10">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[32px] font-semibold tracking-tight leading-none">
                CASA SALCO
              </span>
              <span className="h-2 w-2 rounded-full bg-primary" />
            </div>
            <p className="text-[13px] text-muted-foreground">
              Accedé a tu cuenta
            </p>
          </div>

          <form onSubmit={onSubmit} className="flex flex-col gap-5">
            <div className="flex flex-col gap-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={loading}
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="password">Contraseña</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loading}
              />
            </div>

            <Button
              type="submit"
              className="w-full h-11 mt-2"
              disabled={loading}
            >
              {loading ? "Ingresando…" : "Ingresar"}
            </Button>
          </form>
        </div>

        <p className="mt-6 text-center text-[11px] text-muted-foreground">
          CASA SALCO · v0.1.0
        </p>
      </div>
    </div>
  );
}
