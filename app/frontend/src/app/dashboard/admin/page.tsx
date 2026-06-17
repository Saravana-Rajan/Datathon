"use client";

import * as React from "react";
import { AuthGate } from "@/components/AuthGate";
import { AppShell } from "@/components/shell/AppShell";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useKspStore } from "@/lib/store";
import {
  Users, Shield, Database, Activity, AlertTriangle, CheckCircle2, Server,
} from "lucide-react";

interface HealthItem {
  name: string;
  status: "ok" | "warn" | "down";
  latency?: string;
  detail?: string;
}

const HEALTH: HealthItem[] = [
  { name: "Orchestrator (basicio)", status: "warn", latency: "—", detail: "5xx for 12 min" },
  { name: "Gemini 2.5 Pro", status: "ok", latency: "418ms p50", detail: "us-central1" },
  { name: "Gemini Live (kn-IN STT)", status: "ok", latency: "~270ms RTT", detail: "asia-south1" },
  { name: "Neo4j Aura", status: "ok", latency: "12ms", detail: "graph-db @ asia-south1" },
  { name: "Catalyst Data Store", status: "ok", latency: "8ms", detail: "audit_log, session_state" },
  { name: "Catalyst Web Hosting", status: "ok", latency: "22ms", detail: "/app/" },
];

const USERS = [
  { name: "PSI Suresh Kumar", role: "sub_inspector", station: "MG Road PS", status: "online", last: "now" },
  { name: "SHO Lakshmi Devi", role: "sho", station: "Halasuru PS", status: "online", last: "3m" },
  { name: "DCP Rajeev Mehta", role: "dcp", station: "Bengaluru Urban", status: "away", last: "1h" },
  { name: "SCRB Analyst Priya", role: "scrb_analyst", station: "HQ", status: "offline", last: "2 days" },
  { name: "Constable Ravi M.", role: "constable", station: "Indiranagar PS", status: "online", last: "12m" },
];

const STATUS_DOT: Record<string, string> = {
  online: "bg-emerald-500",
  away: "bg-amber-500",
  offline: "bg-slate-400",
};

function AdminInner() {
  const language = useKspStore((s) => s.language);

  return (
    <AppShell
      title={language === "kn" ? "ನಿರ್ವಹಣೆ" : "Admin"}
      subtitle={
        language === "kn"
          ? "ವ್ಯವಸ್ಥೆ ಆರೋಗ್ಯ, ಬಳಕೆದಾರರು, RBAC"
          : "System health, users, RBAC"
      }
    >
      {/* Health grid */}
      <section className="mb-6">
        <h3 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          <Server className="h-3.5 w-3.5" />
          {language === "kn" ? "ವ್ಯವಸ್ಥೆ ಆರೋಗ್ಯ" : "System health"}
        </h3>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {HEALTH.map((h) => {
            const Icon =
              h.status === "ok" ? CheckCircle2 : h.status === "warn" ? AlertTriangle : AlertTriangle;
            const tone =
              h.status === "ok"
                ? "border-emerald-300/50 bg-emerald-50/60 text-emerald-800 dark:border-emerald-500/20 dark:bg-emerald-500/5 dark:text-emerald-200"
                : h.status === "warn"
                  ? "border-amber-300/50 bg-amber-50/60 text-amber-800 dark:border-amber-500/20 dark:bg-amber-500/5 dark:text-amber-200"
                  : "border-rose-300/50 bg-rose-50/60 text-rose-800 dark:border-rose-500/20 dark:bg-rose-500/5 dark:text-rose-200";
            return (
              <div key={h.name} className={`rounded-lg border p-3 text-xs ${tone}`}>
                <div className="flex items-start justify-between">
                  <div>
                    <div className="font-medium">{h.name}</div>
                    {h.detail && <div className="mt-0.5 text-[10px] opacity-80">{h.detail}</div>}
                  </div>
                  <Icon className="h-4 w-4" />
                </div>
                {h.latency && (
                  <div className="mt-2 font-mono text-[10px]">{h.latency}</div>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* Users + RBAC */}
      <section className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
            <div>
              <CardTitle className="flex items-center gap-2 text-sm">
                <Users className="h-3.5 w-3.5" />
                {language === "kn" ? "ಬಳಕೆದಾರರು" : "Users"}
              </CardTitle>
              <CardDescription className="text-xs">
                {language === "kn"
                  ? "ಇತ್ತೀಚಿನ ಸಕ್ರಿಯ ಅಧಿಕಾರಿಗಳು"
                  : "Recently active officers"}
              </CardDescription>
            </div>
            <Button variant="outline" size="sm">{language === "kn" ? "ಸೇರಿಸಿ" : "Invite"}</Button>
          </CardHeader>
          <CardContent className="p-0">
            <ul className="divide-y divide-slate-100 dark:divide-white/5">
              {USERS.map((u) => (
                <li key={u.name} className="flex items-center gap-3 px-4 py-3 text-xs hover:bg-slate-50/70 dark:hover:bg-white/[0.02]">
                  <span
                    className="flex h-7 w-7 items-center justify-center rounded-full text-[10px] font-semibold"
                    style={{ background: "#1e3a8a", color: "white" }}
                  >
                    {u.name.slice(0, 1)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium">{u.name}</div>
                    <div className="text-[10px] text-slate-500 dark:text-slate-400">
                      {u.station} · <span className="font-mono uppercase">{u.role}</span>
                    </div>
                  </div>
                  <span className="inline-flex items-center gap-1.5 text-[10px] text-slate-500">
                    <span className={`inline-block h-1.5 w-1.5 rounded-full ${STATUS_DOT[u.status]}`} />
                    {u.last}
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Shield className="h-3.5 w-3.5" />
              RBAC matrix
            </CardTitle>
            <CardDescription className="text-xs">
              {language === "kn"
                ? "JWT ksp_role ಪಾಲಿಸಿ ಸಾರಾಂಶ"
                : "JWT ksp_role policy summary"}
            </CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <table className="w-full text-[11px]">
              <thead className="text-left text-[9px] uppercase tracking-wider text-slate-500 dark:text-slate-400">
                <tr>
                  <th className="px-4 py-2">Role</th>
                  <th className="px-4 py-2">View</th>
                  <th className="px-4 py-2">Export</th>
                  <th className="px-4 py-2">Admin</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { r: "Constable", v: "Own beat", e: "—", a: "—" },
                  { r: "SI / PSI", v: "Own station", e: "PDF", a: "—" },
                  { r: "Inspector", v: "Own station+", e: "PDF", a: "—" },
                  { r: "SHO", v: "Own station", e: "PDF / CSV", a: "—" },
                  { r: "DCP", v: "District", e: "PDF / CSV / API", a: "Reports" },
                  { r: "SCRB", v: "State", e: "All", a: "All" },
                  { r: "Admin", v: "All", e: "All", a: "Full" },
                ].map((row) => (
                  <tr key={row.r} className="border-t border-slate-100 dark:border-white/5">
                    <td className="px-4 py-2 font-medium">{row.r}</td>
                    <td className="px-4 py-2 text-slate-500 dark:text-slate-400">{row.v}</td>
                    <td className="px-4 py-2 text-slate-500 dark:text-slate-400">{row.e}</td>
                    <td className="px-4 py-2 text-slate-500 dark:text-slate-400">{row.a}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </section>

      <section className="mt-6">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Database className="h-3.5 w-3.5" />
              {language === "kn" ? "ಡೇಟಾ ಮೂಲಗಳು" : "Data sources"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="grid gap-2 text-xs sm:grid-cols-2">
              <li className="flex items-center gap-2"><Activity className="h-3 w-3 text-emerald-500" /> CCTNS FIR feed · 14,212 records</li>
              <li className="flex items-center gap-2"><Activity className="h-3 w-3 text-emerald-500" /> Charge sheets · 8,401 docs</li>
              <li className="flex items-center gap-2"><Activity className="h-3 w-3 text-emerald-500" /> General diaries · 41,098 entries</li>
              <li className="flex items-center gap-2"><Activity className="h-3 w-3 text-amber-500" /> Vehicle DB · sync 2h delayed</li>
            </ul>
          </CardContent>
        </Card>
      </section>
    </AppShell>
  );
}

export default function AdminPage() {
  return (
    <AuthGate requireRoles={["dcp", "admin", "scrb_analyst", "guest"]}>
      <AdminInner />
    </AuthGate>
  );
}
