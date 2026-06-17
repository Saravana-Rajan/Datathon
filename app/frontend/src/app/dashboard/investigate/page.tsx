"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { AuthGate } from "@/components/AuthGate";
import { AppShell } from "@/components/shell/AppShell";
import { ChatPanel } from "@/components/ChatPanel";
import { MapPanel } from "@/components/MapPanel";
import { NetworkGraph } from "@/components/NetworkGraph";
import { AuditDrawer } from "@/components/AuditDrawer";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useKspStore } from "@/lib/store";

const ORCHESTRATOR_ENDPOINT = "/server/orchestrator/";

function InvestigateInner() {
  const language = useKspStore((s) => s.language);
  const auditTrail = useKspStore((s) => s.auditTrail);
  const [auditRequestId, setAuditRequestId] = React.useState<string | null>(null);
  const [auditOpen, setAuditOpen] = React.useState(false);

  // Listen for Why?/citation clicks from ChatMessage.
  React.useEffect(() => {
    function onOpenAudit(e: Event) {
      const detail = (e as CustomEvent<{ requestId?: string }>).detail;
      if (detail?.requestId) {
        setAuditRequestId(detail.requestId);
        setAuditOpen(true);
      }
    }
    window.addEventListener("ksp:open-audit", onOpenAudit as EventListener);
    return () => window.removeEventListener("ksp:open-audit", onOpenAudit as EventListener);
  }, []);

  const openLatestAudit = React.useCallback(() => {
    const latest = auditTrail[auditTrail.length - 1];
    setAuditRequestId(latest?.requestId ?? null);
    setAuditOpen(true);
  }, [auditTrail]);

  return (
    <AppShell
      title={language === "kn" ? "ತನಿಖೆ" : "Investigate"}
      subtitle={
        language === "kn"
          ? "ಸಾರ್ವಿಕ್‌ಗೆ ಯಾವುದೇ ಪ್ರಶ್ನೆ ಕೇಳಿ — ಧ್ವನಿ ಅಥವಾ ಪಠ್ಯ"
          : "Ask Sarvik anything — voice or text, bilingual"
      }
      actions={
        <Button variant="outline" size="sm" onClick={openLatestAudit}>
          {language === "kn" ? "ಏಕೆ? / ಆಡಿಟ್" : "Why? / Audit"}
        </Button>
      }
    >
      <div className="grid gap-3 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <div className="min-h-[60vh] sm:min-h-[70vh] lg:min-h-0">
          <ChatPanel apiEndpoint={ORCHESTRATOR_ENDPOINT} />
        </div>

        <div className="min-h-[50vh] sm:min-h-[70vh] lg:min-h-0">
          <Card className="flex h-full flex-col">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">
                {language === "kn" ? "ಕಾರ್ಯಸ್ಥಳ" : "Workspace"}
              </CardTitle>
              <CardDescription className="text-xs">
                {language === "kn"
                  ? "ನಕ್ಷೆ, ಜಾಲ, ಆಡಿಟ್ ಪ್ರತಿ ಪ್ರಶ್ನೆಯೊಂದಿಗೆ ಸ್ವಯಂಚಾಲಿತವಾಗಿ ನವೀಕರಿಸಲ್ಪಡುತ್ತದೆ."
                  : "Map, network, and audit views update with each query."}
              </CardDescription>
            </CardHeader>
            <CardContent className="flex-1 pt-2">
              <Tabs defaultValue="map" className="flex h-full flex-col">
                <TabsList>
                  <TabsTrigger value="map">{language === "kn" ? "ನಕ್ಷೆ" : "Map"}</TabsTrigger>
                  <TabsTrigger value="network">{language === "kn" ? "ಜಾಲ" : "Network"}</TabsTrigger>
                  <TabsTrigger value="audit">{language === "kn" ? "ಆಡಿಟ್" : "Audit"}</TabsTrigger>
                </TabsList>
                <TabsContent value="map" className="flex-1 pt-3">
                  <MapPanel />
                </TabsContent>
                <TabsContent value="network" className="flex-1 pt-3">
                  <NetworkGraph className="h-full w-full" />
                </TabsContent>
                <TabsContent value="audit" className="flex-1 overflow-y-auto pt-3">
                  {auditTrail.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      {language === "kn"
                        ? "ಇನ್ನೂ ಆಡಿಟ್ ನಮೂದುಗಳಿಲ್ಲ. ಪ್ರತಿ ಸಂಭಾಷಣೆ ಒಂದು ಪೂರ್ಣ ಆಡಿಟ್ ದಾಖಲೆಯನ್ನು ಬರೆಯುತ್ತದೆ."
                        : "No audit entries yet. Every chat turn writes a full audit record."}
                    </p>
                  ) : (
                    <ul className="space-y-3">
                      {auditTrail.map((entry) => (
                        <li key={entry.requestId} className="rounded-md border bg-card p-3 text-xs">
                          <div className="flex items-center justify-between">
                            <div className="font-mono text-[10px] text-muted-foreground">{entry.requestId}</div>
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
      </div>

      <AuditDrawer
        requestId={auditRequestId}
        open={auditOpen}
        onOpenChange={setAuditOpen}
      />
    </AppShell>
  );
}

export default function InvestigatePage() {
  return (
    <AuthGate
      requireRoles={["inspector", "sho", "dcp", "psi", "sub_inspector", "scrb_analyst", "admin", "guest"]}
    >
      <React.Suspense fallback={null}>
        <InvestigateInner />
      </React.Suspense>
    </AuthGate>
  );
}
