/**
 * Matriz de permisos por rol — single source of truth de acceso a rutas
 * desde el frontend. El backend tiene su propia validación con
 * `@roles_required(...)`; esto es la cara UI: oculta menús y bloquea
 * navegación a rutas que el rol no puede usar.
 *
 * Roles posibles (alineados con `app/utils/auth_guards.py` del backend):
 *   admin · supervisor · cajero · fiambrero · repositor · contador
 */

export type Rol =
  | "admin"
  | "supervisor"
  | "cajero"
  | "fiambrero"
  | "repositor"
  | "contador";

export const ROLES_OPERATIVOS: Rol[] = [
  "admin",
  "supervisor",
  "cajero",
  "fiambrero",
  "repositor",
];

export const ROLES_BACKOFFICE: Rol[] = ["admin", "supervisor", "contador"];

export const ROLES_TODOS: Rol[] = [
  "admin",
  "supervisor",
  "cajero",
  "fiambrero",
  "repositor",
  "contador",
];

/**
 * Mapa de path → roles que pueden acceder.
 * Si una ruta no aparece, queda abierta a todos los roles autenticados.
 */
export const ROUTE_ACCESS: Record<string, Rol[]> = {
  "/": ROLES_TODOS,
  "/pos": ROLES_OPERATIVOS,
  "/facturas": ROLES_TODOS,
  "/movimientos": ROLES_TODOS,
  "/pagos": ROLES_BACKOFFICE,
  "/articulos": ROLES_TODOS,
  "/clientes": ROLES_TODOS,
  "/proveedores": ROLES_BACKOFFICE,
  "/compras": ROLES_BACKOFFICE,
  "/stock": ROLES_TODOS,
  "/stock/reposicion": ["admin", "supervisor"],
  "/sucursales": ["admin"],
  "/consultas": ROLES_BACKOFFICE,
  "/exports": ROLES_BACKOFFICE,
  "/mantenimiento": ["admin"],
};

/**
 * Devuelve true si el rol puede acceder a la ruta.
 * - rol vacío/null → false (no autenticado)
 * - ruta no listada → true (default abierto)
 */
export function hasAccess(
  rol: string | null | undefined,
  path: string,
): boolean {
  if (!rol) return false;
  const allowed = ROUTE_ACCESS[path];
  if (!allowed) return true;
  return (allowed as readonly string[]).includes(rol);
}

/**
 * Helper para usar como `beforeLoad` en `createRoute`. Si el usuario no
 * puede acceder a la ruta, lanza redirect a `/`. El backend igualmente
 * va a tirar 403 si se intenta llamar a un endpoint protegido — esto es
 * sólo para que la navegación UI sea coherente.
 */
import { redirect } from "@tanstack/react-router";
import { useAuth } from "@/store/auth";

export function requireAccess(path: string) {
  return () => {
    const { accessToken, user } = useAuth.getState();
    if (!accessToken) {
      throw redirect({ to: "/login" });
    }
    if (!hasAccess(user?.rol, path)) {
      throw redirect({ to: "/" });
    }
  };
}
