"use client";

import * as React from "react";
import { AuthGate } from "@/components/AuthGate";
import { AppShell } from "@/components/shell/AppShell";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useKspStore } from "@/lib/store";
import {
  FolderOpen,
  Plus,
  Filter,
  ArrowUpDown,
  CheckCircle2,
  Clock,
  AlertOctagon,
  FileText,
} from "lucide-react";

interface CaseRow {
  id: string;
  firNo: string;
  title: { en: string; kn: string };
  area: string;
  status: "open" | "investigating" | "charge_sheet" | "closed";
  priority: "high" | "medium" | "low";
  io: string;
  updated: string;
}

const CASES: CaseRow[] = [
  { id: "c1", firNo: "412/26", title: { en: "Vehicle theft — MG Road", kn: "ವಾಹನ ಕಳ್ಳತನ — ಎಂಜಿ ರಸ್ತೆ" }, area: "MG Road PS", status: "investigating", priority: "high", io: "PSI Suresh", updated: "12m ago" },
  { id: "c2", firNo: "411/26", title: { en: "Chain snatching — Indiranagar", kn: "ಚೈನ್ ಸ್ನ್ಯಾಚಿಂಗ್ — ಇಂದಿರಾನಗರ" }, area: "Indiranagar PS", status: "open", priority: "high", io: "SI Ramesh", updated: "1h ago" },
  { id: "c3", firNo: "408/26", title: { en: "Cyber fraud — UPI", kn: "ಸೈಬರ್ ವಂಚನೆ — UPI" }, area: "BTM Layout PS", status: "investigating", priority: "medium", io: "SI Pooja", updated: "3h ago" },
  { id: "c4", firNo: "402/26", title: { en: "House break-in", kn: "ಮನೆ ದರೋಡೆ" }, area: "Koramangala PS", status: "charge_sheet", priority: "medium", io: "PSI Anand", updated: "Yesterday" },
  { id: "c5", firNo: "398/26", title: { en: "Public nuisance — drunkenness", kn: "ಸಾರ್ವಜನಿಕ ಗದ್ದಲ — ಮದ್ಯಪಾನ" }, area: "Halasuru PS", status: "closed", priority: "low", io: "Constable Ravi", updated: "2 days ago" },
  { id: "c6", firNo: "395/26", title: { en: "Pickpocketing — bus stand", kn: "ಜೇಬು ಕಳ್ಳತನ — ಬಸ್ ನಿಲ್ದಾಣ" }, area: "Majestic PS", status: "investigating", priority: "medium", io: "SI Pooja", updated: "2 days ago" },
];

const STATUS_META: Record<CaseRow["status"], { label: { en: string; kn: string }; tone: string; icon: React.ComponentType<{ className?: string }> }> = {
  open:           { label: { en: "Open", kn: "ತೆರೆದ" },                     tone: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300", icon: AlertOctagon },
  investigating:  { label: { en: "Investigating", kn: "ತನಿಖೆಯಲ್ಲಿ" },          tone: "bg-blue-100 text-blue-800 dark:bg-blue-500/15 dark:text-blue-300",   icon: Clock },
  charge_sheet:   { label: { en: "Charge sheet filed", kn: "ಆರೋಪ ಪಟ್ಟಿ ದಾಖಲು" }, tone: "bg-violet-100 text-violet-800 dark:bg-violet-500/15 dark:text-violet-300", icon: FileText },
  closed:         { label: { en: "Closed", kn: "ಮುಚ್ಚಲಾಗಿದೆ" },              tone: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300", icon: CheckCircle2 },
};

function CasesInner() {
  const language = useKspStore((s) => s.language);
  const [q, setQ] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState<CaseRow["status"] | "all">("all");

  const filtered = CASES.filter((c) => {
    if (statusFilter !== "all" && c.status !== statusFilter) return false;
    if (!q.trim()) return true;
    const lower = q.toLowerCase();
    return (
      c.firNo.toLowerCase().includes(lower) ||
      c.title.en.toLowerCase().includes(lower) ||
      c.area.toLowerCase().includes(lower) ||
      c.io.toLowerCase().includes(lower)
    );
  });

  const counts = {
    all: CASES.length,
    open: CASES.filter((c) => c.status === "open").length,
    investigating: CASES.filter((c) => c.status === "investigating").length,
    charge_sheet: CASES.filter((c) => c.status === "charge_sheet").length,
    closed: CASES.filter((c) => c.status === "closed").length,
  };

  return (
    <AppShell
      title={language === "kn" ? "ಪ್ರಕರಣಗಳು" : "Cases"}
      subtitle={
        language === "kn"
          ? `${CASES.length} ಪ್ರಕರಣಗಳು ನಿಮ್ಮ ವ್ಯಾಪ್ತಿಯಲ್ಲಿ`
          : `${CASES.length} cases in your jurisdiction`
      }
      actions={
        <>
          <Button variant="outline" size="sm">
            <Filter className="mr-1.5 h-3.5 w-3.5" />
            {language === "kn" ? "ಫಿಲ್ಟರ್" : "Filters"}
          </Button>
          <Button size="sm" className="bg-[#1e3a8a] text-white hover:bg-[#162c6b]">
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            {language === "kn" ? "ಹೊಸ FIR" : "New FIR"}
          </Button>
        </>
      }
    >
      {/* Filter chips */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {(["all", "open", "investigating", "charge_sheet", "closed"] as const).map((s) => {
          const label =
            s === "all"
              ? language === "kn" ? "ಎಲ್ಲಾ" : "All"
              : STATUS_META[s].label[language];
          const active = statusFilter === s;
          return (
            <button
              key={s}
              type="button"
              onClick={() => setStatusFilter(s)}
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                active
                  ? "border-[#1e3a8a] bg-[#1e3a8a] text-white dark:border-[#C8A964] dark:bg-[#C8A964] dark:text-[#0c1a3d]"
                  : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 dark:border-white/10 dark:bg-white/[0.03] dark:text-slate-300"
              }`}
            >
              {label}
              <span className="rounded bg-white/30 px-1 text-[10px]">{counts[s]}</span>
            </button>
          );
        })}
        <Input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={language === "kn" ? "FIR ನಂ, ಪ್ರದೇಶ, IO..." : "FIR no, area, IO..."}
          className="ml-auto h-8 max-w-xs text-xs"
        />
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b bg-slate-50 text-left dark:bg-white/[0.03]">
                <tr className="text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  <th className="px-4 py-2.5">
                    <span className="inline-flex items-center gap-1">
                      FIR <ArrowUpDown className="h-3 w-3 opacity-50" />
                    </span>
                  </th>
                  <th className="px-4 py-2.5">{language === "kn" ? "ಶೀರ್ಷಿಕೆ" : "Title"}</th>
                  <th className="px-4 py-2.5">{language === "kn" ? "ಪ್ರದೇಶ" : "Area"}</th>
                  <th className="px-4 py-2.5">{language === "kn" ? "ಸ್ಥಿತಿ" : "Status"}</th>
                  <th className="px-4 py-2.5">{language === "kn" ? "ಆದ್ಯತೆ" : "Priority"}</th>
                  <th className="px-4 py-2.5">IO</th>
                  <th className="px-4 py-2.5">{language === "kn" ? "ನವೀಕರಿಸಲಾಗಿದೆ" : "Updated"}</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((c) => {
                  const meta = STATUS_META[c.status];
                  const Icon = meta.icon;
                  return (
                    <tr
                      key={c.id}
                      className="border-b text-xs last:border-0 hover:bg-slate-50/70 dark:hover:bg-white/[0.02]"
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <FolderOpen className="h-3.5 w-3.5 text-[#1e3a8a] dark:text-[#C8A964]" />
                          <span className="font-mono font-medium">{c.firNo}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 font-medium">{c.title[language]}</td>
                      <td className="px-4 py-3 text-slate-600 dark:text-slate-400">{c.area}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-semibold ${meta.tone}`}>
                          <Icon className="h-3 w-3" />
                          {meta.label[language]}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-block h-2 w-2 rounded-full ${
                          c.priority === "high" ? "bg-rose-500"
                          : c.priority === "medium" ? "bg-amber-500"
                          : "bg-slate-400"
                        } mr-1.5`} />
                        <span className="capitalize">{c.priority}</span>
                      </td>
                      <td className="px-4 py-3 text-slate-600 dark:text-slate-400">{c.io}</td>
                      <td className="px-4 py-3 text-[10px] text-slate-400">{c.updated}</td>
                    </tr>
                  );
                })}
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-xs text-slate-400">
                      {language === "kn" ? "ಯಾವುದೇ ಪ್ರಕರಣಗಳು ಸಿಗಲಿಲ್ಲ." : "No cases match your filters."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </AppShell>
  );
}

export default function CasesPage() {
  return (
    <AuthGate
      requireRoles={["inspector", "sho", "dcp", "psi", "sub_inspector", "scrb_analyst", "admin", "guest"]}
    >
      <CasesInner />
    </AuthGate>
  );
}
