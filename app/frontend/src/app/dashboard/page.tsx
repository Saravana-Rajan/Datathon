"use client";

import * as React from "react";
import Link from "next/link";
import {
  MessageSquare,
  Map as MapIcon,
  Share2,
  FileBarChart,
  ScrollText,
  ArrowUpRight,
  ArrowRight,
  TrendingUp,
  TrendingDown,
  Activity as ActivityIcon,
  Sparkles,
  Clock,
} from "lucide-react";
import { AuthGate } from "@/components/AuthGate";
import { AppShell } from "@/components/shell/AppShell";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useKspStore } from "@/lib/store";
import { useAuth } from "@/lib/catalyst-auth";

interface Stat {
  label: { en: string; kn: string };
  value: string;
  delta?: string;
  trend?: "up" | "down" | "flat";
  hint?: string;
}

const STATS: Stat[] = [
  { label: { en: "Open FIRs", kn: "ತೆರೆದ FIR" }, value: "42", delta: "+4", trend: "up", hint: "vs last week" },
  { label: { en: "Hotspots active", kn: "ಸಕ್ರಿಯ ಹಾಟ್‌ಸ್ಪಾಟ್‌ಗಳು" }, value: "7", delta: "-2", trend: "down", hint: "vs last week" },
  { label: { en: "Repeat offenders", kn: "ಪುನರಾವರ್ತಿತ ಅಪರಾಧಿಗಳು" }, value: "118", delta: "+11", trend: "up", hint: "active in last 90d" },
  { label: { en: "Predicted incidents (24h)", kn: "ಮುನ್ಸೂಚಿತ ಘಟನೆಗಳು (24 ಗಂ)" }, value: "9", delta: "±2", trend: "flat", hint: "P50 forecast" },
];

interface QuickAction {
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  title: { en: string; kn: string };
  desc: { en: string; kn: string };
}

const QUICK_ACTIONS: QuickAction[] = [
  { href: "/dashboard/investigate", icon: MessageSquare, title: { en: "Investigate", kn: "ತನಿಖೆ" }, desc: { en: "Ask Sarvik anything — Kannada or English.", kn: "ಕನ್ನಡ ಅಥವಾ ಇಂಗ್ಲಿಷ್‌ನಲ್ಲಿ ಯಾವುದೇ ಪ್ರಶ್ನೆ ಕೇಳಿ." } },
  { href: "/dashboard/map", icon: MapIcon, title: { en: "Crime Map", kn: "ಅಪರಾಧ ನಕ್ಷೆ" }, desc: { en: "Plot FIRs, hotspots, and beats live.", kn: "FIR, ಹಾಟ್‌ಸ್ಪಾಟ್, ಬೀಟ್‌ಗಳನ್ನು ಲೈವ್ ತೋರಿಸಿ." } },
  { href: "/dashboard/network", icon: Share2, title: { en: "Networks", kn: "ಜಾಲಗಳು" }, desc: { en: "Find gangs by phone, vehicle, co-accused.", kn: "ಫೋನ್, ವಾಹನ, ಸಹ-ಆರೋಪಿಗಳ ಜಾಲ ಹುಡುಕಿ." } },
  { href: "/dashboard/reports", icon: FileBarChart, title: { en: "Reports", kn: "ವರದಿಗಳು" }, desc: { en: "Forecasts, ward summaries, PDF exports.", kn: "ಮುನ್ಸೂಚನೆ, ವಾರ್ಡ್ ಸಾರಾಂಶ, PDF ರಫ್ತು." } },
];

interface ActivityEntry {
  id: string;
  ts: string;
  who: string;
  what: { en: string; kn: string };
  tag?: { text: string; tone: "info" | "warning" | "success" };
}

const ACTIVITY: ActivityEntry[] = [
  { id: "a1", ts: "2 min ago", who: "PSI Suresh", what: { en: "Filed FIR 412/26 (vehicle theft, MG Road)", kn: "FIR 412/26 ದಾಖಲಿಸಿದರು (ವಾಹನ ಕಳ್ಳತನ, ಎಂಜಿ ರಸ್ತೆ)" }, tag: { text: "FIR", tone: "info" } },
  { id: "a2", ts: "11 min ago", who: "Sarvik AI", what: { en: "Hotspot alert: chain-snatching cluster forming near Indiranagar 100ft Road", kn: "ಹಾಟ್‌ಸ್ಪಾಟ್ ಎಚ್ಚರಿಕೆ: ಇಂದಿರಾನಗರ 100 ಅಡಿ ರಸ್ತೆ ಬಳಿ ಚೈನ್ ಸ್ನ್ಯಾಚಿಂಗ್" }, tag: { text: "Alert", tone: "warning" } },
  { id: "a3", ts: "47 min ago", who: "SHO Lakshmi", what: { en: "Marked case 198/26 resolved — accused arrested", kn: "ಪ್ರಕರಣ 198/26 ಪರಿಹಾರ ಎಂದು ಗುರುತಿಸಿದರು — ಆರೋಪಿ ಬಂಧಿಸಲಾಗಿದೆ" }, tag: { text: "Resolved", tone: "success" } },
  { id: "a4", ts: "1 hr ago", who: "Sarvik AI", what: { en: "Generated weekly DCP brief (12 wards, 47 hotspots)", kn: "ಸಾಪ್ತಾಹಿಕ DCP ವರದಿ ತಯಾರಿಸಿದೆ (12 ವಾರ್ಡ್, 47 ಹಾಟ್‌ಸ್ಪಾಟ್)" } },
  { id: "a5", ts: "3 hr ago", who: "SI Ramesh", what: { en: "Exported case file 372/26 as PDF (audit-stamped)", kn: "ಪ್ರಕರಣ 372/26 PDF ಆಗಿ ರಫ್ತು ಮಾಡಿದರು (ಆಡಿಟ್ ಸ್ಟ್ಯಾಂಪ್)" } },
];

interface Hotspot {
  rank: number;
  area: string;
  count: number;
  type: { en: string; kn: string };
  severity: "high" | "medium" | "low";
}

const HOTSPOTS: Hotspot[] = [
  { rank: 1, area: "Indiranagar 100ft Rd", count: 14, type: { en: "Chain snatching", kn: "ಚೈನ್ ಸ್ನ್ಯಾಚಿಂಗ್" }, severity: "high" },
  { rank: 2, area: "MG Road · Brigade Jn", count: 11, type: { en: "Two-wheeler theft", kn: "ಎರಡು ಚಕ್ರ ವಾಹನ ಕಳ್ಳತನ" }, severity: "high" },
  { rank: 3, area: "Halasuru Market", count: 8, type: { en: "Pickpocketing", kn: "ಜೇಬು ಕಳ್ಳತನ" }, severity: "medium" },
  { rank: 4, area: "Koramangala 5th Blk", count: 6, type: { en: "House break-in", kn: "ಮನೆ ದರೋಡೆ" }, severity: "medium" },
  { rank: 5, area: "BTM Layout", count: 4, type: { en: "Cyber fraud", kn: "ಸೈಬರ್ ವಂಚನೆ" }, severity: "low" },
];

function DashboardInner() {
  const language = useKspStore((s) => s.language);
  const { user } = useAuth();
  const role = user?.role ?? "guest";

  const hour = new Date().getHours();
  const greeting =
    language === "kn"
      ? hour < 12 ? "ಶುಭೋದಯ" : hour < 17 ? "ಶುಭ ಮಧ್ಯಾಹ್ನ" : "ಶುಭ ಸಂಜೆ"
      : hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  const firstName = (user?.name ?? "Officer").split(" ").slice(0, 2).join(" ");
  const station = user?.stationName ?? "Karnataka State Police";

  return (
    <AppShell
      title={language === "kn" ? "ಡ್ಯಾಶ್‌ಬೋರ್ಡ್" : "Dashboard"}
      subtitle={`${greeting}, ${firstName} · ${station}`}
      actions={
        <>
          <Link href="/dashboard/reports">
            <Button variant="outline" size="sm">
              <FileBarChart className="mr-1.5 h-3.5 w-3.5" />
              {language === "kn" ? "ಶಿಫ್ಟ್ ವರದಿ" : "Shift report"}
            </Button>
          </Link>
          <Link href="/dashboard/investigate">
            <Button size="sm" className="bg-[#1e3a8a] text-white hover:bg-[#162c6b]">
              <Sparkles className="mr-1.5 h-3.5 w-3.5" />
              {language === "kn" ? "ಸಾರ್ವಿಕ್‌ಗೆ ಕೇಳಿ" : "Ask Sarvik"}
            </Button>
          </Link>
        </>
      }
    >
      <section aria-label="Key metrics" className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {STATS.map((s) => {
          const TrendIcon = s.trend === "up" ? TrendingUp : s.trend === "down" ? TrendingDown : ActivityIcon;
          const trendColor =
            s.trend === "up" ? "text-emerald-600 dark:text-emerald-400"
            : s.trend === "down" ? "text-rose-600 dark:text-rose-400"
            : "text-slate-500";
          return (
            <Card key={s.label.en} className="overflow-hidden">
              <CardContent className="p-4">
                <div className="text-[11px] uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  {s.label[language]}
                </div>
                <div className="mt-1 flex items-baseline gap-2">
                  <div className="text-2xl font-semibold tracking-tight">{s.value}</div>
                  {s.delta && (
                    <span className={`inline-flex items-center gap-0.5 text-[10px] font-medium ${trendColor}`}>
                      <TrendIcon className="h-3 w-3" />
                      {s.delta}
                    </span>
                  )}
                </div>
                {s.hint && <div className="mt-1 text-[10px] text-slate-400">{s.hint}</div>}
              </CardContent>
            </Card>
          );
        })}
      </section>

      <section aria-label="Quick actions" className="mb-6">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {QUICK_ACTIONS.map((q) => {
            const Icon = q.icon;
            return (
              <Link
                key={q.href}
                href={q.href}
                className="group flex flex-col gap-1.5 rounded-xl border bg-white p-4 transition-all hover:-translate-y-0.5 hover:border-[#1e3a8a] hover:shadow-md dark:border-white/10 dark:bg-white/[0.03] dark:hover:border-[#C8A964]"
              >
                <div className="flex items-center justify-between">
                  <div
                    className="flex h-9 w-9 items-center justify-center rounded-md"
                    style={{ background: "rgba(30,58,138,0.08)", color: "#1e3a8a" }}
                  >
                    <Icon className="h-4 w-4" />
                  </div>
                  <ArrowUpRight className="h-4 w-4 text-slate-300 transition-colors group-hover:text-[#1e3a8a] dark:text-slate-600 dark:group-hover:text-[#C8A964]" />
                </div>
                <div className="mt-1 text-sm font-semibold">{q.title[language]}</div>
                <div className="text-xs text-slate-500 dark:text-slate-400">{q.desc[language]}</div>
              </Link>
            );
          })}
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
            <div>
              <CardTitle className="text-sm">{language === "kn" ? "ಇತ್ತೀಚಿನ ಚಟುವಟಿಕೆ" : "Recent activity"}</CardTitle>
              <CardDescription className="text-xs">
                {language === "kn" ? "ನಿಮ್ಮ ವ್ಯಾಪ್ತಿಯಲ್ಲಿ ಲೈವ್ ಘಟನೆಗಳು ಮತ್ತು AI ಎಚ್ಚರಿಕೆಗಳು." : "Live events and AI alerts inside your jurisdiction."}
              </CardDescription>
            </div>
            <Link href="/dashboard/audit" className="text-xs text-[#1e3a8a] hover:underline dark:text-[#C8A964]">
              {language === "kn" ? "ಎಲ್ಲಾ ನೋಡಿ" : "View all"} →
            </Link>
          </CardHeader>
          <CardContent className="pt-0">
            <ol className="relative space-y-3 border-l border-slate-200 pl-4 dark:border-white/10">
              {ACTIVITY.map((a) => (
                <li key={a.id} className="relative">
                  <span
                    className="absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full border-2 border-white bg-[#1e3a8a] dark:border-[#0c1a3d] dark:bg-[#C8A964]"
                    aria-hidden="true"
                  />
                  <div className="flex flex-wrap items-baseline gap-2 text-xs">
                    <span className="font-medium">{a.who}</span>
                    {a.tag && (
                      <span className={`rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide ${
                        a.tag.tone === "warning" ? "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300"
                        : a.tag.tone === "success" ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300"
                        : "bg-slate-100 text-slate-700 dark:bg-white/5 dark:text-slate-300"
                      }`}>
                        {a.tag.text}
                      </span>
                    )}
                    <span className="ml-auto flex items-center gap-1 text-[10px] text-slate-400">
                      <Clock className="h-3 w-3" />
                      {a.ts}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-slate-600 dark:text-slate-300">{a.what[language]}</div>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
            <div>
              <CardTitle className="text-sm">{language === "kn" ? "ಟಾಪ್ ಹಾಟ್‌ಸ್ಪಾಟ್‌ಗಳು" : "Top hotspots"}</CardTitle>
              <CardDescription className="text-xs">
                {language === "kn" ? "ಕಳೆದ 7 ದಿನಗಳಲ್ಲಿ ಸಕ್ರಿಯ." : "Active in the last 7 days."}
              </CardDescription>
            </div>
            <Link href="/dashboard/map" className="text-xs text-[#1e3a8a] hover:underline dark:text-[#C8A964]">
              {language === "kn" ? "ನಕ್ಷೆಯಲ್ಲಿ" : "On map"} →
            </Link>
          </CardHeader>
          <CardContent className="pt-0">
            <ul className="space-y-1">
              {HOTSPOTS.map((h) => (
                <li key={h.rank} className="flex items-center gap-3 rounded-md px-2 py-2 hover:bg-slate-50 dark:hover:bg-white/[0.03]">
                  <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded text-[10px] font-bold ${
                    h.severity === "high" ? "bg-rose-500/15 text-rose-600 dark:text-rose-300"
                    : h.severity === "medium" ? "bg-amber-500/15 text-amber-700 dark:text-amber-300"
                    : "bg-slate-500/15 text-slate-600 dark:text-slate-300"
                  }`}>
                    {h.rank}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-xs font-medium">{h.area}</div>
                    <div className="truncate text-[10px] text-slate-500 dark:text-slate-400">
                      {h.type[language]} · {h.count} {language === "kn" ? "ಘಟನೆಗಳು" : "incidents"}
                    </div>
                  </div>
                  <ArrowRight className="h-3.5 w-3.5 text-slate-300 dark:text-slate-600" />
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </section>

      <div className="mt-6 flex items-start gap-3 rounded-xl border bg-[#1e3a8a]/[0.04] p-4 dark:border-white/10 dark:bg-[#C8A964]/[0.06]">
        <ScrollText className="mt-0.5 h-4 w-4 text-[#1e3a8a] dark:text-[#C8A964]" />
        <div className="text-xs leading-relaxed text-slate-700 dark:text-slate-300">
          <span className="font-medium">{language === "kn" ? "ನೆನಪು: " : "Reminder: "}</span>
          {language === "kn"
            ? "ಪ್ರತಿ ಪ್ರಶ್ನೆ, ಎಚ್ಚರಿಕೆ, ಮತ್ತು ರಫ್ತು — ಬದಲಾಯಿಸಲಾಗದ ಆಡಿಟ್ ಲಾಗ್‌ನಲ್ಲಿ (IT ಕಾಯ್ದೆ 2008 § 67C) ದಾಖಲಾಗುತ್ತದೆ. ಪ್ರಸ್ತುತ ಪಾತ್ರ: "
            : "Every query, alert, and export you take is written to an immutable audit log (IT Act 2008 § 67C). Current role: "}
          <span className="font-mono font-semibold uppercase">{role}</span>
        </div>
      </div>
    </AppShell>
  );
}

export default function DashboardPage() {
  return (
    <AuthGate
      requireRoles={["inspector", "sho", "dcp", "psi", "sub_inspector", "scrb_analyst", "admin", "guest"]}
    >
      <DashboardInner />
    </AuthGate>
  );
}
