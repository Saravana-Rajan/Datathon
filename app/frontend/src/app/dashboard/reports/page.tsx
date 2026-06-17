"use client";

import * as React from "react";
import { AuthGate } from "@/components/AuthGate";
import { AppShell } from "@/components/shell/AppShell";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useKspStore } from "@/lib/store";
import {
  FileBarChart, Download, TrendingUp, Calendar, BarChart3, Sparkles,
} from "lucide-react";

interface ReportTpl {
  id: string;
  title: { en: string; kn: string };
  desc: { en: string; kn: string };
  icon: React.ComponentType<{ className?: string }>;
  cadence: string;
}

const TEMPLATES: ReportTpl[] = [
  { id: "shift", title: { en: "Shift handover brief", kn: "ಶಿಫ್ಟ್ ಹಸ್ತಾಂತರ ವರದಿ" }, desc: { en: "Auto-generated at every shift change.", kn: "ಪ್ರತಿ ಶಿಫ್ಟ್ ಬದಲಾವಣೆಯಲ್ಲಿ ಸ್ವಯಂ-ರಚಿತ." }, icon: Calendar, cadence: "8h" },
  { id: "weekly_dcp", title: { en: "Weekly DCP brief", kn: "ಸಾಪ್ತಾಹಿಕ DCP ವರದಿ" }, desc: { en: "12 wards, hotspots, top offenders, predictions.", kn: "12 ವಾರ್ಡ್, ಹಾಟ್‌ಸ್ಪಾಟ್, ಟಾಪ್ ಆರೋಪಿಗಳು, ಮುನ್ಸೂಚನೆಗಳು." }, icon: FileBarChart, cadence: "Weekly" },
  { id: "ward_summary", title: { en: "Ward summary", kn: "ವಾರ್ಡ್ ಸಾರಾಂಶ" }, desc: { en: "One PDF per ward, ready to share.", kn: "ಪ್ರತಿ ವಾರ್ಡ್‌ಗೆ ಒಂದು PDF, ಹಂಚಿಕೊಳ್ಳಲು ಸಿದ್ಧ." }, icon: BarChart3, cadence: "On demand" },
  { id: "forecast", title: { en: "24h forecast", kn: "24 ಗಂಟೆ ಮುನ್ಸೂಚನೆ" }, desc: { en: "Predicted incidents by beat, with confidence bands.", kn: "ಬೀಟ್ ಪ್ರಕಾರ ಮುನ್ಸೂಚಿತ ಘಟನೆಗಳು, ವಿಶ್ವಾಸ ಶ್ರೇಣಿಗಳೊಂದಿಗೆ." }, icon: TrendingUp, cadence: "Live" },
];

const RECENT = [
  { id: "r1", name: "Weekly DCP brief — W24", size: "2.1 MB", generated: "Today, 06:00", by: "Sarvik AI" },
  { id: "r2", name: "Shift handover — Night → Morning", size: "412 KB", generated: "Today, 06:00", by: "Sarvik AI" },
  { id: "r3", name: "Indiranagar ward summary", size: "1.8 MB", generated: "Yesterday, 18:42", by: "SHO Lakshmi" },
  { id: "r4", name: "24h forecast — Bengaluru Urban", size: "640 KB", generated: "Yesterday, 06:00", by: "Sarvik AI" },
];

function ReportsInner() {
  const language = useKspStore((s) => s.language);

  return (
    <AppShell
      title={language === "kn" ? "ವರದಿಗಳು" : "Reports"}
      subtitle={
        language === "kn"
          ? "ಸ್ವಯಂ-ರಚಿತ ಬ್ರೀಫ್‌ಗಳು, ಮುನ್ಸೂಚನೆಗಳು, PDF ರಫ್ತುಗಳು"
          : "Auto-generated briefs, forecasts, and audit-stamped PDFs"
      }
      actions={
        <Button size="sm" className="bg-[#1e3a8a] text-white hover:bg-[#162c6b]">
          <Sparkles className="mr-1.5 h-3.5 w-3.5" />
          {language === "kn" ? "ಹೊಸ ವರದಿ ರಚಿಸಿ" : "Generate new"}
        </Button>
      }
    >
      <section className="mb-6">
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          {language === "kn" ? "ಟೆಂಪ್ಲೇಟ್‌ಗಳು" : "Templates"}
        </h3>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {TEMPLATES.map((t) => {
            const Icon = t.icon;
            return (
              <div key={t.id} className="group rounded-xl border bg-white p-4 transition-all hover:-translate-y-0.5 hover:border-[#1e3a8a] hover:shadow-md dark:border-white/10 dark:bg-white/[0.03] dark:hover:border-[#C8A964]">
                <div
                  className="flex h-9 w-9 items-center justify-center rounded-md"
                  style={{ background: "rgba(30,58,138,0.08)", color: "#1e3a8a" }}
                >
                  <Icon className="h-4 w-4" />
                </div>
                <div className="mt-3 text-sm font-semibold">{t.title[language]}</div>
                <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">{t.desc[language]}</div>
                <div className="mt-3 flex items-center justify-between text-[10px]">
                  <span className="rounded bg-slate-100 px-1.5 py-0.5 font-medium text-slate-600 dark:bg-white/5 dark:text-slate-300">
                    {t.cadence}
                  </span>
                  <Button variant="ghost" size="sm" className="h-7 px-2 text-xs">
                    {language === "kn" ? "ತೆರೆಯಿರಿ" : "Open"} →
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
          <div>
            <CardTitle className="text-sm">
              {language === "kn" ? "ಇತ್ತೀಚಿನ ರಚನೆಗಳು" : "Recently generated"}
            </CardTitle>
            <CardDescription className="text-xs">
              {language === "kn"
                ? "ಎಲ್ಲಾ ರಫ್ತುಗಳು ಆಡಿಟ್-ಸ್ಟ್ಯಾಂಪ್ ಮಾಡಲ್ಪಟ್ಟಿವೆ."
                : "Every export is audit-stamped (IT Act § 67C)."}
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <ul className="divide-y divide-slate-100 dark:divide-white/5">
            {RECENT.map((r) => (
              <li key={r.id} className="flex items-center gap-3 px-4 py-3 hover:bg-slate-50/70 dark:hover:bg-white/[0.02]">
                <FileBarChart className="h-4 w-4 shrink-0 text-[#1e3a8a] dark:text-[#C8A964]" />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-xs font-medium">{r.name}</div>
                  <div className="text-[10px] text-slate-500 dark:text-slate-400">
                    {r.size} · {r.generated} · {r.by}
                  </div>
                </div>
                <Button variant="ghost" size="sm" className="h-7 px-2 text-xs">
                  <Download className="mr-1 h-3 w-3" />
                  PDF
                </Button>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </AppShell>
  );
}

export default function ReportsPage() {
  return (
    <AuthGate requireRoles={["inspector", "sho", "dcp", "psi", "sub_inspector", "scrb_analyst", "admin", "guest"]}>
      <ReportsInner />
    </AuthGate>
  );
}
