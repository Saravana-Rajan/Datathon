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
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from "@/components/ui/drawer";
import { useKspStore, type Language } from "@/lib/store";
import { exportPdf } from "@/lib/api";

// NOTE: ChatPanel, MapPanel, NetworkGraph, AuditDrawer, VoiceRecorder,
// LanguageToggle, and AuthGate are owned by other agents. We render typed
// placeholders here that match the imports those agents will provide.
function ChatPanelPlaceholder() {
  return (
    <Card className="flex h-full flex-col">
      <CardHeader>
        <CardTitle>Chat</CardTitle>
        <CardDescription>
          Voice + text in Kannada and English. Streaming responses with citations.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex-1">
        <div className="flex h-full items-center justify-center rounded-md border border-dashed text-sm text-muted-foreground">
          ChatPanel mounts here (owned by Person D / Voice agent).
        </div>
      </CardContent>
    </Card>
  );
}

function MapPanelPlaceholder() {
  return (
    <div className="flex h-full items-center justify-center rounded-md border border-dashed text-sm text-muted-foreground">
      MapPanel — Google Maps + H3 hotspots
    </div>
  );
}

function NetworkGraphPlaceholder() {
  return (
    <div className="flex h-full items-center justify-center rounded-md border border-dashed text-sm text-muted-foreground">
      NetworkGraph — React Flow + Neo4j traversal
    </div>
  );
}

function AuditTrailPlaceholder() {
  const auditTrail = useKspStore((s) => s.auditTrail);
  if (auditTrail.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No audit entries yet. Every chat turn writes a full audit record.
      </p>
    );
  }
  return (
    <ul className="space-y-3">
      {auditTrail.map((entry) => (
        <li
          key={entry.requestId}
          className="rounded-md border bg-card p-3 text-xs"
        >
          <div className="font-mono text-[10px] text-muted-foreground">
            {entry.requestId}
          </div>
          <div className="mt-1 font-medium">{entry.intent}</div>
          <pre className="mt-1 whitespace-pre-wrap break-all text-muted-foreground">
            {entry.summary}
          </pre>
        </li>
      ))}
    </ul>
  );
}

const LANGUAGES: { value: Language; label: string }[] = [
  { value: "en", label: "English" },
  { value: "kn", label: "ಕನ್ನಡ" },
];

export default function DashboardPage() {
  const language = useKspStore((s) => s.language);
  const setLanguage = useKspStore((s) => s.setLanguage);
  const role = useKspStore((s) => s.role);
  const sessionId = useKspStore((s) => s.sessionId);

  const [theme, setTheme] = React.useState<"light" | "dark">("light");

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
      a.download = `ksp-saathi-${sessionId}.pdf`;
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
            <span className="text-sm font-semibold">KSP Saathi</span>
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
          <ChatPanelPlaceholder />
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
                <Drawer>
                  <DrawerTrigger asChild>
                    <Button variant="outline" size="sm">
                      Why? / Audit
                    </Button>
                  </DrawerTrigger>
                  <DrawerContent>
                    <DrawerHeader>
                      <DrawerTitle>Audit trail</DrawerTitle>
                      <DrawerDescription>
                        Every step the AI took for this session. Immutable,
                        exportable, IT Act 2008 compliant.
                      </DrawerDescription>
                    </DrawerHeader>
                    <div className="max-h-[60vh] overflow-y-auto px-4 pb-6">
                      <AuditTrailPlaceholder />
                    </div>
                  </DrawerContent>
                </Drawer>
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
                  <MapPanelPlaceholder />
                </TabsContent>
                <TabsContent value="network" className="flex-1 pt-3">
                  <NetworkGraphPlaceholder />
                </TabsContent>
                <TabsContent
                  value="audit"
                  className="flex-1 overflow-y-auto pt-3"
                >
                  <AuditTrailPlaceholder />
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
    </main>
  );
}
