import { Link } from "react-router-dom";
import { Monitor, Moon, Sun } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/providers/theme";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/overlays";

export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn("size-8", className)} aria-hidden>
      <rect width="32" height="32" rx="10" fill="var(--teal-mist)" />
      <path d="M9 22c0-7.5 5.5-13 14-13-0.5 8.5-6 14-14 13z" fill="var(--teal)" />
      <path d="M9.5 22.5 19 13" stroke="var(--primary)" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

export function Logo({ to = "/", className }: { to?: string; className?: string }) {
  return (
    <Link to={to} className={cn("inline-flex items-center gap-2.5 rounded-xl", className)}>
      <LogoMark />
      <span className="font-serif text-xl font-medium tracking-tight text-foreground">Folium</span>
    </Link>
  );
}

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, resolved, setTheme } = useTheme();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="Change theme"
        className={cn(
          "inline-flex size-9 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-surface-2 hover:text-foreground",
          className,
        )}
      >
        {resolved === "dark" ? <Moon className="size-[18px]" /> : <Sun className="size-[18px]" />}
      </DropdownMenuTrigger>
      <DropdownMenuContent className="min-w-40">
        {(
          [
            ["light", "Light", Sun],
            ["dark", "Dark", Moon],
            ["system", "System", Monitor],
          ] as const
        ).map(([value, label, Icon]) => (
          <DropdownMenuItem
            key={value}
            onSelect={() => setTheme(value)}
            className={cn(theme === value && "bg-surface-2")}
          >
            <Icon /> {label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
