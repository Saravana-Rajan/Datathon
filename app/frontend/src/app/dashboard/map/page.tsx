"use client";

import * as React from "react";
import { AuthGate } from "@/components/AuthGate";
import { AppShell } from "@/components/shell/AppShell";
import { MapPanel } from "@/components/MapPanel";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useKspStore } from "@/lib/store";
import { Layers, Calendar, Download, Maximize2 } from "lucide-react";

function MapPageInner() {
  const language = useKspStore((s) => s.language);
  const mapLayers = useKspStore((s) => s.mapLayers);
  const setMapLayers = useKspStore((s) => s.setMapLayers);

  const layers = [
    { key: "incidents" as const, label: { en: "Incidents", kn: "ಘಟನೆಗಳು" } },
    { key: "hotspots" as const,  label: { en: "Hotspots",  kn: "ಹಾಟ್‌ಸ್ಪಾಟ್‌ಗಳು" } },
    { key: "stations" as const,  label: { en: "Stations",  kn: "ಠಾಣೆಗಳು" } },
    { key: "heatmap" as const,   label: { en: "Heatmap",   kn: "ಶಾಖ ನಕ್ಷೆ" } },
  ];

  return (
    <AppShell
      title={language === "kn" ? "ಅಪರಾಧ ನಕ್ಷೆ" : "Crime Map"}
      subtitle={
        language === "kn"
          ? "FIR, ಹಾಟ್‌ಸ್ಪಾಟ್, ಠಾಣೆಗಳು — ಲೈವ್"
          : "FIRs, hotspots, and stations — live"
      }
      actions={
        <>
          <Button variant="outline" size="sm">
            <Calendar className="mr-1.5 h-3.5 w-3.5" />
            {language === "kn" ? "ಕಳೆದ 7 ದಿನಗಳು" : "Last 7 days"}
          </Button>
          <Button variant="outline" size="sm">
            <Download className="mr-1.5 h-3.5 w-3.5" />
            {language === "kn" ? "ರಫ್ತು" : "Export"}
          </Button>
          <Button size="sm" className="bg-[#1e3a8a] text-white hover:bg-[#162c6b]">
            <Maximize2 className="mr-1.5 h-3.5 w-3.5" />
            {language === "kn" ? "ಪೂರ್ಣ ಪರದೆ" : "Fullscreen"}
          </Button>
        </>
      }
    >
      <div className="grid gap-4 lg:grid-cols-[240px_minmax(0,1fr)]">
        {/* Layer controls */}
        <Card>
          <CardContent className="p-4">
            <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              <Layers className="h-3.5 w-3.5" />
              {language === "kn" ? "ಲೇಯರ್‌ಗಳು" : "Layers"}
            </div>
            <ul className="space-y-2">
              {layers.map((l) => (
                <li key={l.key} className="flex items-center justify-between text-xs">
                  <span>{l.label[language]}</span>
                  <button
                    type="button"
                    onClick={() => setMapLayers({ [l.key]: !mapLayers[l.key] })}
                    className={`relative h-4 w-7 rounded-full transition-colors ${
                      mapLayers[l.key] ? "bg-[#1e3a8a] dark:bg-[#C8A964]" : "bg-slate-300 dark:bg-white/10"
                    }`}
                    role="switch"
                    aria-checked={mapLayers[l.key]}
                  >
                    <span
                      className={`absolute top-0.5 h-3 w-3 rounded-full bg-white transition-all ${
                        mapLayers[l.key] ? "right-0.5" : "left-0.5"
                      }`}
                    />
                  </button>
                </li>
              ))}
            </ul>

            <div className="my-4 h-px bg-slate-100 dark:bg-white/5" />

            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              {language === "kn" ? "ಶ್ರೇಣಿ" : "Legend"}
            </div>
            <ul className="space-y-1.5 text-[11px]">
              <li className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-rose-500" />
                {language === "kn" ? "ಹೆಚ್ಚು ತೀವ್ರತೆ" : "High severity"}
              </li>
              <li className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-amber-500" />
                {language === "kn" ? "ಮಧ್ಯಮ" : "Medium"}
              </li>
              <li className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-slate-400" />
                {language === "kn" ? "ಕಡಿಮೆ" : "Low"}
              </li>
            </ul>
          </CardContent>
        </Card>

        {/* Map */}
        <Card className="overflow-hidden">
          <CardContent className="h-[72vh] p-0">
            <MapPanel />
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}

export default function MapPage() {
  return (
    <AuthGate requireRoles={["inspector", "sho", "dcp", "psi", "sub_inspector", "scrb_analyst", "admin", "guest"]}>
      <MapPageInner />
    </AuthGate>
  );
}
