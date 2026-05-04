import { useNavigate } from "@tanstack/react-router";
import { LogOut, User as UserIcon, Settings } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/store/auth";

function initials(name?: string | null, email?: string | null): string {
  const base = name || email || "";
  const parts = base.split(/[\s@._-]+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

interface UserMenuProps {
  compact?: boolean;
}

export function UserMenu({ compact = false }: UserMenuProps) {
  const navigate = useNavigate();
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);

  const handleLogout = () => {
    logout();
    navigate({ to: "/login" });
  };

  const label = user?.nombre || user?.email || "Usuario";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className={
            compact
              ? "flex items-center justify-center rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              : "flex w-full items-center gap-3 rounded-[10px] p-2 text-left transition-colors duration-200 ease-apple hover:bg-muted/60 outline-none focus-visible:ring-2 focus-visible:ring-ring"
          }
        >
          <Avatar className={compact ? "h-8 w-8" : "h-9 w-9"}>
            <AvatarFallback>{initials(user?.nombre, user?.email)}</AvatarFallback>
          </Avatar>
          {!compact && (
            <div className="flex-1 overflow-hidden">
              <div className="truncate text-[13px] font-medium text-foreground">
                {label}
              </div>
              {user?.email && user.email !== label && (
                <div className="truncate text-[11px] text-muted-foreground">
                  {user.email}
                </div>
              )}
            </div>
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[200px]">
        <DropdownMenuLabel>Mi cuenta</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem disabled>
          <UserIcon strokeWidth={1.5} />
          <span>Ver perfil</span>
        </DropdownMenuItem>
        <DropdownMenuItem disabled>
          <Settings strokeWidth={1.5} />
          <span>Configuración</span>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={handleLogout}>
          <LogOut strokeWidth={1.5} />
          <span>Cerrar sesión</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
