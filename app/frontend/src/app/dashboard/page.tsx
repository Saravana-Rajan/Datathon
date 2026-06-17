"use client";

import * as React from "react";
import {
  ShieldCheck,
  Languages,
  Sun,
  Moon,
  FileDown,
  LogOut,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useKspStore, type Language } from "@/lib/store";
import { exportPdf } from "@/lib/api";
import { useAuth } from "@/lib/catalyst-auth";

// Real components from other agents.
import { ChatPanel } from "@/components/ChatPanel";
import { MapPanel } from "@/components/MapPanel";
import { NetworkGraph } from "@/components/NetworkGraph";
import { AuditDrawer } from "@/components/AuditDrawer";
import { AuthGate } from "@/components/AuthGate";

const LANGUAGES: { value: Language; label: string }[] = [
  { value: "en", label: "English" },
  { value: "kn", label: "ಕನ್ನಡ" },
];

// Endpoint where the orchestrator's SSE stream lives. Same origin so no CORS.
const ORCHESTRATOR_ENDPOINT = "/server/orchestrator/";

function DashboardInner() {
  const language = useKspStore((s) => s.language);
  const setLanguage = useKspStore((s) => s.setLanguage);
  const role = useKspStore((s) => s.role);
  const sessionId = useKspStore((s) => s.sessionId);
  const auditTrail = useKspStore((s) => s.auditTrail);

  const router = useRouter();
  const { signOut } = useAuth();

  const [theme, setTheme] = React.useState<"light" | "dark">("light");

  // Audit drawer is opened by either the toolbar button or by inline "Why?"
  // links inside chat messages, which dispatch a `ksp:open-audit` CustomEvent.
  const [auditRequestId, setAuditRequestId] = React.useState<string | null>(
    null
  );
  const [auditOpen, setAuditOpen] = React.useState(false);

  React.useEffect(() => {
    const stored = localStorage.getItem("ksp-theme") as "light" | "dark" | null;
    const prefersDark = window.matchMedia(
      "(prefers-color-scheme: dark)"
    ).matches;
    const initial: "light" | "dark" =
      stored ?? (prefersDark ? "dark" : "light");
    setTheme(initial);
    document.documentElement.classList.toggle("dark", initial === "dark");
  }, []);

  // Listen for ChatMessage citation/why clicks.
  React.useEffect(() => {
    function onOpenAudit(e: Event) {
      const detail = (e as CustomEvent<{ requestId?: string }>).detail;
      if (detail?.requestId) {
        setAuditRequestId(detail.requestId);
        setAuditOpen(true);
      }
    }
    window.addEventListener("ksp:open-audit", onOpenAudit as EventListener);
    return () =>
      window.removeEventListener(
        "ksp:open-audit",
        onOpenAudit as EventListener
      );
  }, []);

  const toggleTheme = React.useCallback(() => {
    setTheme((prev) => {
      const next = prev === "dark" ? "light" : "dark";
      document.documentElement.classList.toggle("dark", next === "dark");
      try {
        localStorage.setItem("ksp-theme", next);
      } catch {
        // ignore quota / disabled storage
      }
      return next;
    });
  }, []);

  const [exporting, setExporting] = React.useState(false);
  const handleExport = React.useCallback(async () => {
    if (!sessionId) return;
    setExporting(true);
    try {
      const blob = await exportPdf(sessionId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `sarvik-${sessionId}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("PDF export failed", err);
    } finally {
      setExporting(false);
    }
  }, [sessionId]);

  const handleSignOut = React.useCallback(async () => {
    try {
      // Clear guest token too if it was set.
      try {
        localStorage.removeItem("sarvik-guest-session");
      } catch {
        // ignore
      }
      await signOut();
    } finally {
      router.replace("/");
    }
  }, [signOut, router]);

  // Open the audit drawer to the most recent assistant turn (toolbar button).
  const openLatestAudit = React.useCallback(() => {
    const latest = auditTrail[auditTrail.length - 1];
    if (latest?.requestId) {
      setAuditRequestId(latest.requestId);
    } else {
      setAuditRequestId(null);
    }
    setAuditOpen(true);
  }, [auditTrail]);

  return (
    <main className="flex min-h-screen flex-col">
      <header
        className="sticky top-0 z-30 flex h-14 items-center justify-between border-b bg-background/80 px-4 backdrop-blur"
        role="banner"
      >
        <div className="flex items-center gap-2">
          <ShieldCheck
            className="h-5 w-5 text-primary"
            aria-hidden="true"
          />
          <div className="flex flex-col leading-tight">
            <span className="text-sm font-semibold">Sarvik</span>
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Investigator&apos;s Companion
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div
            className="flex items-center gap-1 rounded-md border bg-card p-0.5"
            role="group"
            aria-label="Language selector"
          >
            <Languages
              className="ml-1 h-3.5 w-3.5 text-muted-foreground"
              aria-hidden="true"
            />
            {LANGUAGES.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setLanguage(opt.value)}
                aria-pressed={language === opt.value}
                className={
                  "rounded px-2 py-1 text-xs font-medium transition-colors " +
                  (language === opt.value
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground")
                }
              >
                {opt.label}
              </button>
            ))}
          </div>

          <Button
            variant="ghost"
            size="icon"
            onClick={toggleTheme}
            aria-label={
              theme === "dark" ? "Switch to light mode" : "Switch to dark mode"
            }
          >
            {theme === "dark" ? (
              <Sun className="h-4 w-4" aria-hidden="true" />
            ) : (
              <Moon className="h-4 w-4" aria-hidden="true" />
            )}
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={handleExport}
            disabled={!sessionId || exporting}
            aria-label="Export conversation to PDF"
          >
            <FileDown className="mr-1.5 h-4 w-4" aria-hidden="true" />
            {exporting ? "Exporting..." : "Export PDF"}
          </Button>

          <div className="hidden items-center gap-2 rounded-md border bg-card px-2 py-1 text-xs sm:flex">
            <span className="text-muted-foreground">Role:</span>
            <span className="font-medium uppercase tracking-wide">
              {role ?? "guest"}
            </span>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              aria-label="Sign out"
              onClick={handleSignOut}
            >
              <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
            </Button>
          </div>
        </div>
      </header>

      <section
        className="grid flex-1 grid-cols-1 gap-3 p-3 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]"
        aria-label="Main workspace"
      >
        <div className="min-h-[60vh] lg:min-h-0">
          <ChatPanel apiEndpoint={ORCHESTRATOR_ENDPOINT} />
        </div>

        <div className="min-h-[60vh] lg:min-h-0">
          <Card className="flex h-full flex-col">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Workspace</CardTitle>
                  <CardDescription>
                    Map, network, and audit views update with each query.
                  </CardDescription>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={openLatestAudit}
                  aria-label="Open audit trail for the latest answer"
                >
                  Why? / Audit
                </Button>
              </div>
            </CardHeader>
            <CardContent className="flex-1 pt-2">
              <Tabs defaultValue="map" className="flex h-full flex-col">
                <TabsList>
                  <TabsTrigger value="map">Map</TabsTrigger>
                  <TabsTrigger value="network">Network</TabsTrigger>
                  <TabsTrigger value="audit">Audit</TabsTrigger>
                </TabsList>
                <TabsContent value="map" className="flex-1 pt-3">
                  <MapPanel />
                </TabsContent>
                <TabsContent value="network" className="flex-1 pt-3">
                  <NetworkGraph className="h-full w-full" />
                </TabsContent>
                <TabsContent
                  value="audit"
                  className="flex-1 overflow-y-auto pt-3"
                >
                  {auditTrail.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      No audit entries yet. Every chat turn writes a full
                      audit record.
                    </p>
                  ) : (
                    <ul className="space-y-3">
                      {auditTrail.map((entry) => (
                        <li
                          key={entry.requestId}
                          className="rounded-md border bg-card p-3 text-xs"
                        >
                          <div className="flex items-center justify-between">
                            <div className="font-mono text-[10px] text-muted-foreground">
                              {entry.requestId}
                            </div>
                            <button
                              type="button"
                              onClick={() => {
                                setAuditRequestId(entry.requestId);
                                setAuditOpen(true);
                              }}
                              className="rounded border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground hover:bg-muted hover:text-foreground"
                            >
                              Open
                            </button>
                          </div>
                          <div className="mt-1 font-medium">{entry.intent}</div>
                          <pre className="mt-1 whitespace-pre-wrap break-all text-muted-foreground">
                            {entry.summary}
                          </pre>
                        </li>
                      ))}
                    </ul>
                  )}
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </div>
      </section>

      <footer
        className="border-t px-4 py-2 text-center text-[10px] text-muted-foreground"
        role="contentinfo"
      >
        Hosted on Zoho Catalyst (India DC) • Data residency: asia-south1 • IT
        Act 2008 compliant
      </footer>

      {/* Slide-in audit drawer — opened by the toolbar button OR by any
          chat-message "Why?" click (which dispatches `ksp:open-audit`). */}
      <AuditDrawer
        requestId={auditRequestId}
        open={auditOpen}
        onOpenChange={setAuditOpen}
      />
    </main>
  );
}

export default function DashboardPage() {
  return (
    <AuthGate
      requireRoles={[
        "inspector",
        "sho",
        "dcp",
        "psi",
        "sub_inspector",
        "scrb_analyst",
        "admin",
        "guest",
      ]}
    >
      <DashboardInner />
    </AuthGate>
  );
}
