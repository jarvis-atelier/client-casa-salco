import * as React from "react";
import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AgentStatusIndicator } from "./agent-status-indicator";
import { ScaleStatusIndicator } from "./scale-status-indicator";
import { ThemeToggle } from "./theme-toggle";
import { UserMenu } from "./user-menu";
import { cn } from "@/lib/utils";

interface TopbarProps {
  title: string;
  onOpenMobileNav?: () => void;
}

export function Topbar({ title, onOpenMobileNav }: TopbarProps) {
  const [scrolled, setScrolled] = React.useState(false);

  React.useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 4);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={cn(
        "sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-transparent px-6 transition-all duration-200 ease-apple",
        scrolled && "apple-glass border-border",
      )}
    >
      <Button
        variant="ghost"
        size="icon"
        className="md:hidden -ml-2"
        onClick={onOpenMobileNav}
        aria-label="Abrir menú"
      >
        <Menu className="h-[18px] w-[18px]" strokeWidth={1.5} />
      </Button>

      <h1 className="text-[15px] font-semibold tracking-tight text-foreground">
        {title}
      </h1>

      <div className="ml-auto flex items-center gap-1">
        <ScaleStatusIndicator />
        <AgentStatusIndicator />
        <ThemeToggle />
        <div className="md:hidden">
          <UserMenu compact />
        </div>
      </div>
    </header>
  );
}
