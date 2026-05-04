import * as React from "react";
import { cn } from "@/lib/utils";

export interface SegmentedTabItem<T extends string> {
  value: T;
  label: string;
  hidden?: boolean;
}

interface SegmentedTabsProps<T extends string> {
  value: T;
  onChange: (next: T) => void;
  items: SegmentedTabItem<T>[];
  className?: string;
}

export function SegmentedTabs<T extends string>({
  value,
  onChange,
  items,
  className,
}: SegmentedTabsProps<T>) {
  const visible = items.filter((i) => !i.hidden);
  return (
    <div
      className={cn(
        "inline-flex items-center gap-0.5 rounded-[10px] border border-border bg-muted/40 p-0.5",
        className,
      )}
      role="tablist"
    >
      {visible.map((item) => {
        const active = item.value === value;
        return (
          <button
            key={item.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(item.value)}
            className={cn(
              "h-8 rounded-[7px] px-3.5 text-[12px] font-medium transition-all duration-200 ease-apple",
              active
                ? "bg-background text-foreground shadow-apple"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

interface PillButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
}

export function PillButton({
  active,
  className,
  children,
  ...props
}: PillButtonProps) {
  return (
    <button
      type="button"
      className={cn(
        "h-8 rounded-full border px-3 text-[12px] font-medium transition-colors duration-200 ease-apple",
        active
          ? "border-foreground/15 bg-foreground text-background"
          : "border-border bg-background text-muted-foreground hover:bg-muted/60 hover:text-foreground",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}
