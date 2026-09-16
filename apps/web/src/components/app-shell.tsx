"use client";

import {
  AudioLines,
  ChartLine,
  Dumbbell,
  History,
  House,
  type LucideIcon,
  Menu,
  MessagesSquare,
  PenLine,
  Settings,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode, useState } from "react";

import { BrandMark } from "@/components/brand-mark";
import { HealthBadge } from "@/components/health-badge";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type NavItem = { href: string; label: string; icon: LucideIcon; enabled: boolean };

// Items light up as their phase ships (docs/tasks/README.md).
export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Home", icon: House, enabled: true },
  { href: "/practice", label: "Practice", icon: MessagesSquare, enabled: false },
  { href: "/sessions", label: "History", icon: History, enabled: false },
  { href: "/pronunciation", label: "Pronunciation", icon: AudioLines, enabled: false },
  { href: "/drills", label: "Drills", icon: Dumbbell, enabled: false },
  { href: "/writing", label: "Writing", icon: PenLine, enabled: false },
  { href: "/progress", label: "Progress", icon: ChartLine, enabled: false },
  { href: "/settings", label: "Settings", icon: Settings, enabled: false },
];

function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="min-h-dvh md:grid md:grid-cols-[16rem_1fr]">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-background focus:px-3 focus:py-2"
      >
        Skip to content
      </a>

      <aside className="border-b border-sidebar-border bg-sidebar md:sticky md:top-0 md:flex md:h-dvh md:flex-col md:border-b-0 md:border-r">
        <div className="flex h-14 items-center justify-between px-4 md:h-auto md:px-5 md:pb-6 md:pt-7">
          <Link href="/" className="flex items-center gap-2.5 rounded-md">
            <BrandMark className="size-7" />
            <span className="font-heading text-lg font-semibold tracking-tight">Articulate AI</span>
          </Link>
          <button
            type="button"
            className="inline-flex size-9 items-center justify-center rounded-md hover:bg-sidebar-accent md:hidden"
            aria-expanded={menuOpen}
            aria-controls="app-nav"
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            onClick={() => setMenuOpen((open) => !open)}
          >
            {menuOpen ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>

        <div
          id="app-nav"
          className={cn(
            "flex-1 flex-col justify-between gap-6 px-3 pb-4 md:flex md:px-3 md:pb-6",
            menuOpen ? "flex" : "hidden",
          )}
        >
          <nav aria-label="Main">
            <ul className="space-y-0.5">
              {NAV_ITEMS.map(({ href, label, icon: Icon, enabled }) => {
                const active = enabled && isActive(pathname, href);
                const content = (
                  <>
                    <Icon className="size-4 shrink-0" aria-hidden />
                    <span className="flex-1">{label}</span>
                    {!enabled && (
                      <Badge variant="outline" className="font-normal text-muted-foreground">
                        Soon
                      </Badge>
                    )}
                  </>
                );
                const base = "flex items-center gap-3 rounded-md px-3 py-2 text-[0.95rem]";
                return (
                  <li key={href}>
                    {enabled ? (
                      <Link
                        href={href}
                        aria-current={active ? "page" : undefined}
                        onClick={() => setMenuOpen(false)}
                        className={cn(
                          base,
                          active
                            ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                            : "text-sidebar-foreground hover:bg-sidebar-accent/70",
                        )}
                      >
                        {content}
                      </Link>
                    ) : (
                      <span aria-disabled="true" className={cn(base, "text-muted-foreground")}>
                        {content}
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>
          </nav>
          <HealthBadge className="self-start" />
        </div>
      </aside>

      <main id="main" className="px-5 py-10 md:px-14 md:py-16">
        {children}
      </main>
    </div>
  );
}
