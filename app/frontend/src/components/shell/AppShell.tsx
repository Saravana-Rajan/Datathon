"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  MessageSquare,
  FolderOpen,
  Map as MapIcon,
  Share2,
  FileBarChart,
  ScrollText,
  Settings,
  ShieldAlert,
  Search,
  Bell,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  LogOut,
  Languages,
  Sun,
  Moon,
  Sparkles,
  ShieldCheck,
} from "lucide-react";

import { useAuth } from "@/lib/catalyst-auth";
import { useKspStore, type Language } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// --------------------------------------------------------------------------
// Navigation model — central source of truth for the sidebar + breadcrumbs.
// --------------------------------------------------------------------------

interface NavItem {
  href: string;
  label: { en: string; kn: string };
  icon: React.ComponentType<{ className?: string }>;
  group?: string;
  /** Roles allowed to see this nav item. Omitting = everyone signed in. */
  roles?: string[];
  /** Optional pill (e.g. "Beta", "3 new"). */
  badge?: { text: string; tone?: "info" | "success" | "warning" };
}

const NAV: NavItem[] = [
  {
    href: "/dashboard",
    label: { en: "Dashboard", kn: "ಡ್ಯಾಶ್‌ಬೋರ್ಡ್" },
    icon: LayoutDashboard,
    group: "workspace",
  },
  {
    href: "/dashboard/investigate",
    label: { en: "Investigate", kn: "ತನಿಖೆ" },
    icon: MessageSquare,
    group: "workspace",
    badge: { text: "AI", tone: "info" },
  },
  {
    href: "/dashboard/cases",
    label: { en: "Cases", kn: "ಪ್ರಕರಣಗಳು" },
    icon: FolderOpen,
    group: "workspace",
  },
  {
    href: "/dashboard/map",
    label: { en: "Crime Map", kn: "ಅಪರಾಧ ನಕ್ಷೆ" },
    icon: MapIcon,
    group: "intel",
  },
  {
    href: "/dashboard/network",
    label: { en: "Networks", kn: "ಜಾಲಗಳು" },
    icon: Share2,
    group: "intel",
  },
  {
    href: "/dashboard/reports",
    label: { en: "Reports", kn: "ವರದಿಗಳು" },
    icon: FileBarChart,
    group: "intel",
  },
  {
    href: "/dashboard/audit",
    label: { en: "Audit Log", kn: "ಆಡಿಟ್ ಲಾಗ್" },
    icon: ScrollText,
    group: "ops",
  },
  {
    href: "/dashboard/admin",
    label: { en: "Admin", kn: "ನಿರ್ವಹಣೆ" },
    icon: ShieldAlert,
    group: "ops",
    roles: ["dcp", "admin", "scrb_analyst", "guest"],
  },
  {
    href: "/settings",
    label: { en: "Settings", kn: "ಸೆಟ್ಟಿಂಗ್‌ಗಳು" },
    icon: Settings,
    group: "ops",
  },
];

const GROUP_LABEL: Record<string, { en: string; kn: string }> = {
  workspace: { en: "Workspace", kn: "ಕೆಲಸದ ಸ್ಥಳ" },
  intel:     { en: "Intelligence", kn: "ಗುಪ್ತಚರ" },
  ops:       { en: "Operations", kn: "ಕಾರ್ಯಾಚರಣೆ" },
};

// --------------------------------------------------------------------------
// Sub-components
// --------------------------------------------------------------------------

function Sidebar({
  collapsed,
  onToggleCollapse,
  language,
}: {
  collapsed: boolean;
  onToggleCollapse: () => void;
  language: Language;
}) {
  const pathname = usePathname() ?? "";
  const { user } = useAuth();
  const role = user?.role ?? "guest";

  const visible = NAV.filter((n) => !n.roles || n.roles.includes(role));
  const groups = Array.from(new Set(visible.map((n) => n.group ?? "other")));

  return (
    <aside
      className={cn(
        "sticky top-0 hidden h-screen shrink-0 flex-col border-r border-slate-200/80 bg-[#F5F5F7] text-slate-700 lg:flex dark:border-white/10 dark:bg-[#0c1a3d] dark:text-slate-200",
        collapsed ? "w-[68px]" : "w-[252px]"
      )}
      role="navigation"
      aria-label="Primary"
    >
      {/* Brand block */}
      <Link
        href="/dashboard"
        className="flex h-16 items-center gap-2.5 border-b border-slate-200/70 px-5 hover:bg-white/40 dark:border-white/5 dark:hover:bg-white/[0.03]"
      >
        <div
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl shadow-sm"
          style={{
            background:
              "linear-gradient(135deg, #7c5cfa 0%, #4f46e5 50%, #ec4899 100%)",
            boxShadow: "0 4px 12px rgba(124, 92, 250, 0.30)",
          }}
        >
          <ShieldCheck className="h-4 w-4 text-white" />
        </div>
        {!collapsed && (
          <div className="leading-tight">
            <div className="text-[15px] font-semibold tracking-tight text-slate-900 dark:text-white">
              Sarvik
            </div>
            <div className="text-[9px] font-medium uppercase tracking-[0.2em] text-slate-400 dark:text-slate-500">
              KSP Investigator
            </div>
          </div>
        )}
      </Link>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-2.5 py-3">
        {groups.map((g, gi) => {
          const items = visible.filter((n) => (n.group ?? "other") === g);
          const groupCopy = GROUP_LABEL[g];
          return (
            <div key={g} className={gi > 0 ? "mt-5" : ""}>
              {!collapsed && groupCopy && (
                <div className="px-3 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">
                  {groupCopy[language]}
                </div>
              )}
              <ul className="space-y-0.5">
                {items.map((item) => {
                  const Icon = item.icon;
                  const active =
                    pathname === item.href ||
                    (item.href !== "/dashboard" && pathname.startsWith(item.href));
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        className={cn(
                          "group relative flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium transition-all",
                          active
                            ? "bg-white text-[#4f46e5] shadow-sm dark:bg-white/10 dark:text-white"
                            : "text-slate-600 hover:bg-white/70 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-white/5 dark:hover:text-white"
                        )}
                        aria-current={active ? "page" : undefined}
                        title={collapsed ? item.label[language] : undefined}
                      >
                        {active && (
                          <span
                            className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r-full"
                            style={{
                              background:
                                "linear-gradient(180deg, #7c5cfa 0%, #4f46e5 100%)",
                            }}
                          />
                        )}
                        <Icon
                          className={cn(
                            "h-4 w-4 shrink-0 transition-colors",
                            active
                              ? "text-[#7c5cfa]"
                              : "text-slate-400 group-hover:text-slate-700 dark:text-slate-400 dark:group-hover:text-slate-200"
                          )}
                        />
                        {!collapsed && (
                          <>
                            <span className="flex-1 truncate">
                              {item.label[language]}
                            </span>
                            {item.badge && (
                              <span
                                className={cn(
                                  "rounded-full px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide",
                                  item.badge.tone === "warning"
                                    ? "bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300"
                                    : item.badge.tone === "success"
                                    ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300"
                                    : "bg-violet-100 text-[#7c5cfa] dark:bg-violet-500/20 dark:text-violet-300"
                                )}
                              >
                                {item.badge.text}
                              </span>
                            )}
                          </>
                        )}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </nav>

      {/* User card + collapse */}
      <div className="border-t border-slate-200/70 p-3 dark:border-white/5">
        {!collapsed && <SidebarUserCard />}
        <button
          type="button"
          onClick={onToggleCollapse}
          className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white/60 px-2.5 py-1.5 text-[11px] font-medium text-slate-500 transition-colors hover:bg-white hover:text-slate-700 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <ChevronsRight className="h-3.5 w-3.5" />
          ) : (
            <>
              <ChevronsLeft className="h-3.5 w-3.5" />
              <span>Collapse</span>
            </>
          )}
        </button>
        {!collapsed && (
          <div className="mt-2.5 flex items-center justify-center gap-1.5 text-[9px] font-medium uppercase tracking-[0.15em] text-slate-400 dark:text-slate-500">
            <span>powered by</span>
            <span className="spark-gradient-text font-semibold">Catalyst</span>
          </div>
        )}
      </div>
    </aside>
  );
}

/**
 * Sidebar user card — avatar (initials), name + email, sign-out arrow.
 * Designed to match the SparkFinch reference profile cell at the bottom of
 * the sidebar.
 */
function SidebarUserCard(): JSX.Element {
  const router = useRouter();
  const { user, signOut } = useAuth();

  const displayName = user?.name ?? "Guest Reviewer";
  const displayEmail = user?.email ?? "guest@sarvik.local";
  const initials = displayName
    .split(/\s+/)
    .map((s) => s[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();

  const handleSignOut = async () => {
    try {
      localStorage.removeItem("sarvik-guest-session");
    } catch {
      /* ignore */
    }
    await signOut();
    router.replace("/");
  };

  return (
    <div className="flex items-center gap-2.5 rounded-xl border border-slate-200/70 bg-white p-2.5 shadow-sm dark:border-white/10 dark:bg-white/5">
      <span
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold text-white shadow-sm"
        style={{
          background:
            "linear-gradient(135deg, #7c5cfa 0%, #ec4899 100%)",
        }}
        aria-hidden="true"
      >
        {initials || "G"}
      </span>
      <div className="flex min-w-0 flex-1 flex-col leading-tight">
        <span className="truncate text-[12px] font-semibold text-slate-800 dark:text-slate-100">
          {displayName}
        </span>
        <span className="truncate text-[10px] text-slate-500 dark:text-slate-400">
          {displayEmail}
        </span>
      </div>
      <button
        type="button"
        onClick={handleSignOut}
        className="rounded-md p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-rose-500 dark:hover:bg-white/10"
        aria-label="Sign out"
        title="Sign out"
      >
        <LogOut className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

function MobileNav({
  open,
  onClose,
  language,
}: {
  open: boolean;
  onClose: () => void;
  language: Language;
}) {
  const pathname = usePathname() ?? "";
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 lg:hidden">
      <div
        className="absolute inset-0 bg-slate-900/70 backdrop-blur"
        onClick={onClose}
      />
      <aside className="absolute left-0 top-0 h-full w-64 overflow-y-auto bg-[#0c1a3d] p-4 text-slate-100">
        <div className="mb-4 flex items-center justify-between">
          <span className="text-sm font-semibold text-white">Sarvik</span>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-white/10 px-2 py-1 text-xs text-slate-300"
            aria-label="Close navigation"
          >
            Close
          </button>
        </div>
        <ul className="space-y-1">
          {NAV.map((item) => {
            const Icon = item.icon;
            const active =
              pathname === item.href ||
              (item.href !== "/dashboard" && pathname.startsWith(item.href));
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  onClick={onClose}
                  className={cn(
                    "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm",
                    active
                      ? "bg-white/10 text-white"
                      : "text-slate-300 hover:bg-white/5 hover:text-white"
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {item.label[language]}
                </Link>
              </li>
            );
          })}
        </ul>
      </aside>
    </div>
  );
}

function TopBar({
  onOpenMobileNav,
  onSearch,
  pageTitle,
  pageSubtitle,
}: {
  onOpenMobileNav: () => void;
  onSearch: (q: string) => void;
  pageTitle: string;
  pageSubtitle?: string;
}) {
  const router = useRouter();
  const pathname = usePathname() ?? "";
  const { user, signOut } = useAuth();
  const language = useKspStore((s) => s.language);
  const setLanguage = useKspStore((s) => s.setLanguage);
  const [searchQ, setSearchQ] = React.useState("");
  const [theme, setTheme] = React.useState<"light" | "dark">("light");
  const [menuOpen, setMenuOpen] = React.useState(false);
  const menuRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    const stored = localStorage.getItem("ksp-theme") as "light" | "dark" | null;
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const initial: "light" | "dark" = stored ?? (prefersDark ? "dark" : "light");
    setTheme(initial);
    document.documentElement.classList.toggle("dark", initial === "dark");
  }, []);

  React.useEffect(() => {
    function onClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const toggleTheme = () => {
    setTheme((prev) => {
      const next = prev === "dark" ? "light" : "dark";
      document.documentElement.classList.toggle("dark", next === "dark");
      try {
        localStorage.setItem("ksp-theme", next);
      } catch {
        // ignore
      }
      return next;
    });
  };

  const handleSignOut = async () => {
    try {
      localStorage.removeItem("sarvik-guest-session");
    } catch {
      // ignore
    }
    await signOut();
    router.replace("/");
  };

  // Breadcrumbs — strip ".html" suffix that Catalyst hosting leaves in the URL.
  const cleanPath = pathname.replace(/\.html$/i, "");
  const segments = cleanPath.replace(/^\/+/, "").split("/").filter(Boolean);
  const crumbs = segments.map((seg, i) => {
    const href = "/" + segments.slice(0, i + 1).join("/");
    const navMatch = NAV.find((n) => n.href === href);
    const label = navMatch
      ? navMatch.label[language]
      : seg.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    return { href, label };
  });

  return (
    <header
      className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-slate-200/70 bg-[#FAFAFB]/85 px-5 backdrop-blur-xl dark:border-white/10 dark:bg-[#0c1a3d]/80"
      role="banner"
    >
      <button
        type="button"
        onClick={onOpenMobileNav}
        className="-ml-1 rounded-md border border-slate-200 p-1.5 lg:hidden dark:border-white/10"
        aria-label="Open navigation"
      >
        <ChevronsRight className="h-4 w-4" />
      </button>

      {/* Breadcrumbs / page title */}
      <div className="flex min-w-0 flex-col leading-tight">
        <nav
          className="flex items-center gap-1 text-[11px] text-slate-500 dark:text-slate-400"
          aria-label="Breadcrumb"
        >
          {crumbs.map((c, i) => (
            <React.Fragment key={c.href}>
              {i > 0 && <ChevronRight className="h-3 w-3 opacity-50" />}
              <Link
                href={c.href}
                className={cn(
                  "truncate hover:text-slate-800 dark:hover:text-slate-200",
                  i === crumbs.length - 1 && "font-medium text-slate-700 dark:text-slate-200"
                )}
              >
                {c.label}
              </Link>
            </React.Fragment>
          ))}
        </nav>
        <div className="flex items-baseline gap-2">
          <h1 className="truncate text-sm font-semibold tracking-tight text-slate-900 dark:text-white">
            {pageTitle}
          </h1>
          {pageSubtitle && (
            <span className="hidden truncate text-[11px] text-slate-500 sm:inline dark:text-slate-400">
              · {pageSubtitle}
            </span>
          )}
        </div>
      </div>

      {/* Global search */}
      <form
        className="ml-auto hidden flex-1 max-w-md md:flex"
        onSubmit={(e) => {
          e.preventDefault();
          onSearch(searchQ);
        }}
        role="search"
      >
        <label className="relative w-full">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400"
            aria-hidden="true"
          />
          <input
            type="search"
            value={searchQ}
            onChange={(e) => setSearchQ(e.target.value)}
            placeholder={
              language === "kn"
                ? "FIR, ವ್ಯಕ್ತಿ, ಪ್ರಕರಣ ಹುಡುಕಿ..."
                : "Search FIRs, people, cases..."
            }
            className="h-9 w-full rounded-full border border-slate-200 bg-white/80 pl-8 pr-2 text-xs placeholder:text-slate-400 focus:border-[#7c5cfa] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#7c5cfa]/20 dark:border-white/10 dark:bg-white/5 dark:text-slate-200"
          />
          <kbd className="pointer-events-none absolute right-2 top-1/2 hidden -translate-y-1/2 rounded border border-slate-200 bg-slate-50 px-1 text-[9px] font-medium text-slate-500 sm:inline-block dark:border-white/10 dark:bg-white/5 dark:text-slate-400">
            /
          </kbd>
        </label>
      </form>

      {/* Right cluster */}
      <div className="ml-auto flex items-center gap-1.5 md:ml-0">
        <div
          className="hidden items-center gap-1 rounded-md border border-slate-200 bg-white p-0.5 sm:flex dark:border-white/10 dark:bg-white/5"
          role="group"
          aria-label="Language"
        >
          <Languages className="ml-1 h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
          {(["en", "kn"] as Language[]).map((opt) => (
            <button
              key={opt}
              type="button"
              onClick={() => setLanguage(opt)}
              aria-pressed={language === opt}
              className={cn(
                "rounded-md px-2 py-0.5 text-[10px] font-semibold transition-all",
                language === opt
                  ? "spark-gradient text-white shadow-sm"
                  : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white"
              )}
            >
              {opt === "en" ? "EN" : "ಕನ್ನಡ"}
            </button>
          ))}
        </div>

        <Button
          variant="ghost"
          size="icon"
          onClick={toggleTheme}
          aria-label={theme === "dark" ? "Light mode" : "Dark mode"}
          className="h-8 w-8"
        >
          {theme === "dark" ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
        </Button>

        <button
          type="button"
          className="relative flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-medium text-slate-600 transition-all hover:border-slate-300 hover:shadow-sm dark:border-white/10 dark:bg-white/5 dark:text-slate-300"
          aria-label="Notifications"
        >
          <Bell className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Notification</span>
          <span className="absolute -right-0.5 -top-0.5 flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-rose-400 opacity-70" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-rose-500" />
          </span>
        </button>

        {/* User menu */}
        <div className="relative" ref={menuRef}>
          <button
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            className="flex items-center gap-2 rounded-md border border-slate-200 px-2 py-1 text-xs hover:bg-slate-50 dark:border-white/10 dark:hover:bg-white/5"
            aria-haspopup="menu"
            aria-expanded={menuOpen}
          >
            <span
              className="flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-semibold text-white shadow-sm"
              style={{
                background:
                  "linear-gradient(135deg, #7c5cfa 0%, #ec4899 100%)",
              }}
              aria-hidden="true"
            >
              {(user?.name ?? "G").slice(0, 1).toUpperCase()}
            </span>
            <span className="hidden flex-col items-start leading-tight sm:flex">
              <span className="font-medium text-slate-700 dark:text-slate-200">
                {user?.name ?? "Guest Reviewer"}
              </span>
              <span className="text-[9px] uppercase tracking-wide text-slate-400">
                {user?.role ?? "guest"}
              </span>
            </span>
          </button>

          {menuOpen && (
            <div
              role="menu"
              className="absolute right-0 top-full z-50 mt-1 w-56 rounded-md border border-slate-200 bg-white p-1 shadow-lg dark:border-white/10 dark:bg-[#0c1a3d]"
            >
              <div className="px-3 py-2 text-[11px]">
                <div className="font-medium text-slate-700 dark:text-slate-200">
                  {user?.name ?? "Guest Reviewer"}
                </div>
                <div className="text-slate-500 dark:text-slate-400">
                  {user?.email ?? "guest@sarvik.local"}
                </div>
                {user?.stationName && (
                  <div className="mt-1 text-[10px] text-slate-500 dark:text-slate-400">
                    {user.stationName} · {user.district}
                  </div>
                )}
              </div>
              <div className="my-1 h-px bg-slate-100 dark:bg-white/5" />
              <Link
                href="/settings"
                onClick={() => setMenuOpen(false)}
                className="flex items-center gap-2 rounded px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-white/5"
                role="menuitem"
              >
                <Settings className="h-3.5 w-3.5" />
                Settings
              </Link>
              <Link
                href="/demo/role-switch"
                onClick={() => setMenuOpen(false)}
                className="flex items-center gap-2 rounded px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-white/5"
                role="menuitem"
              >
                <Sparkles className="h-3.5 w-3.5" />
                Switch role (demo)
              </Link>
              <button
                type="button"
                onClick={handleSignOut}
                className="flex w-full items-center gap-2 rounded px-3 py-1.5 text-left text-xs text-rose-600 hover:bg-rose-50 dark:text-rose-300 dark:hover:bg-rose-500/10"
                role="menuitem"
              >
                <LogOut className="h-3.5 w-3.5" />
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

// --------------------------------------------------------------------------
// Public surface
// --------------------------------------------------------------------------

export interface AppShellProps {
  children: React.ReactNode;
  title: string;
  subtitle?: string;
  /** Action buttons rendered in the page header (right side). */
  actions?: React.ReactNode;
  /** Optional sub-header inside the content area (filters, tabs, etc.). */
  pageHeaderExtra?: React.ReactNode;
}

export function AppShell({
  children,
  title,
  subtitle,
  actions,
  pageHeaderExtra,
}: AppShellProps): JSX.Element {
  const language = useKspStore((s) => s.language);
  const router = useRouter();
  const [collapsed, setCollapsed] = React.useState(false);
  const [mobileNavOpen, setMobileNavOpen] = React.useState(false);

  React.useEffect(() => {
    const stored = localStorage.getItem("sarvik-sidebar-collapsed");
    if (stored === "1") setCollapsed(true);
  }, []);

  const toggleCollapse = () => {
    setCollapsed((v) => {
      const next = !v;
      try {
        localStorage.setItem("sarvik-sidebar-collapsed", next ? "1" : "0");
      } catch {
        // ignore
      }
      return next;
    });
  };

  const handleSearch = (q: string) => {
    if (!q.trim()) return;
    // Funnel global search into the Investigate page as a query param.
    router.push(`/dashboard/investigate?q=${encodeURIComponent(q.trim())}`);
  };

  return (
    <div className="flex min-h-screen bg-[#FAFAFB] text-slate-900 dark:bg-[#080f24] dark:text-slate-100">
      <Sidebar
        collapsed={collapsed}
        onToggleCollapse={toggleCollapse}
        language={language}
      />
      <MobileNav
        open={mobileNavOpen}
        onClose={() => setMobileNavOpen(false)}
        language={language}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          onOpenMobileNav={() => setMobileNavOpen(true)}
          onSearch={handleSearch}
          pageTitle={title}
          pageSubtitle={subtitle}
        />

        <main className="flex-1 px-4 pb-8 pt-4 sm:px-6 lg:px-8">
          {/* Page header strip (actions row) */}
          {(actions || pageHeaderExtra) && (
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-col">
                <h2 className="text-xl font-semibold tracking-tight text-slate-900 dark:text-white">
                  {title}
                </h2>
                {subtitle && (
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    {subtitle}
                  </p>
                )}
              </div>
              {actions && (
                <div className="flex flex-wrap items-center gap-2">{actions}</div>
              )}
            </div>
          )}
          {pageHeaderExtra}
          {children}
        </main>

        <footer className="border-t border-slate-200 bg-white/50 px-4 py-2 text-center text-[10px] text-slate-500 dark:border-white/5 dark:bg-transparent dark:text-slate-500">
          Hosted on Zoho Catalyst (India DC) · Data residency asia-south1 · IT Act 2008 § 67C audit-logged
        </footer>
      </div>
    </div>
  );
}

export default AppShell;
