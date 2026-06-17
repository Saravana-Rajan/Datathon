"use client";

import * as React from "react";
import { AuthGate } from "@/components/AuthGate";
import { AppShell } from "@/components/shell/AppShell";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useKspStore } from "@/lib/store";
import { ScrollText, Filter, Download, ShieldCheck, ExternalLink } from "lucide-react";

interface AuditRow {
  id: string;
  ts: string;
  actor: string;
  role: string;
  action: { en: string; kn: string };
  resource: string;
  result: "ok" | "denied" | "warning";
}

const AUDIT_ROWS: AuditRow[] = [
  { id: "req_3a1f", ts: "2026-06-17 09:18:42", actor: "PSI Suresh", role: "sub_inspector", action: { en: "Queried offenders near Indiranagar", kn: "ಇಂದಿರಾನಗರ ಬಳಿ ಆರೋಪಿಗಳನ್ನು ವಿಚಾರಿಸಿದರು" }, resource: "FIR · 90d window", result: "ok" },
  { id: "req_3a1e", ts: "2026-06-17 09:14:11", actor: "SHO Lakshmi", role: "sho", action: { en: "Exported case 412/26 as PDF", kn: "ಪ್ರಕರಣ 412/26 PDF ಆಗಿ ರಫ್ತು ಮಾಡಿದರು" }, resource: "PDF export", result: "ok" },
  { id: "req_3a1d", ts: "2026-06-17 09:02:38", actor: "Constable Ravi", role: "constable", action: { en: "Attempted to view DCP brief", kn: "DCP ವರದಿಯನ್ನು ನೋಡಲು ಪ್ರಯತ್ನಿಸಿದರು" }, resource: "Report:weekly_dcp", result: "denied" },
  { id: "req_3a1c", ts: "2026-06-17 08:51:09", actor: "Sarvik AI", role: "system", action: { en: "Generated hotspot alert (Indiranagar)", kn: "ಹಾಟ್‌ಸ್ಪಾಟ್ ಎಚ್ಚರಿಕೆ ರಚಿಸಲಾಗಿದೆ" }, resource: "Alert · auto", result: "ok" },
  { id: "req_3a1b", ts: "2026-06-17 08:42:55", actor: "PSI Suresh", role: "sub_inspector", action: { en: "Voice query in Kannada", kn: "ಕನ್ನಡದಲ್ಲಿ ಧ್ವನಿ ಪ್ರಶ್ನೆ" }, resource: "Live STT · 6.2s", result: "ok" },
  { id: "req_3a1a", ts: "2026-06-17 08:38:21", actor: "DCP Mehta", role: "dcp", action: { en: "Cross-jurisdiction query", kn: "ಜಿಲ್ಲಾ-ಪಾರ ಪ್ರಶ್ನೆ" }, resource: "FIR · 5 districts", result: "warning" },
];

const RESULT_TONE: Record<AuditRow["result"], string> = {
  ok: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  denied: "bg-rose-500/15 text-rose-700 dark:text-rose-300",
  warning: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
};

function AuditInner() {
  const language = useKspStore((s) => s.language);
  const [q, setQ] = React.useState("");

  const filtered = AUDIT_ROWS.filter((r) => {
    if (!q.trim()) return true;
    const lower = q.toLowerCase();
    return (
      r.id.toLowerCase().includes(lower) ||
      r.actor.toLowerCase().includes(lower) ||
      r.action.en.toLowerCase().includes(lower) ||
      r.resource.toLowerCase().includes(lower)
    );
  });

  return (
    <AppShell
      title={language === "kn" ? "ಆಡಿಟ್ ಲಾಗ್" : "Audit Log"}
      subtitle={
        language === "kn"
          ? "ಪ್ರತಿ ಪ್ರಶ್ನೆ, ರಫ್ತು, ಎಚ್ಚರಿಕೆ — ಬದಲಾಯಿಸಲಾಗದ ದಾಖಲೆ"
          : "Every query, export, and alert — immutable record (IT Act § 67C)"
      }
      actions={
        <>
          <Button variant="outline" size="sm">
            <Filter className="mr-1.5 h-3.5 w-3.5" />
            {language === "kn" ? "ಫಿಲ್ಟರ್" : "Filters"}
          </Button>
          <Button variant="outline" size="sm">
            <Download className="mr-1.5 h-3.5 w-3.5" />
            {language === "kn" ? "CSV ರಫ್ತು" : "Export CSV"}
          </Button>
        </>
      }
    >
      <div className="mb-4 flex items-center gap-3 rounded-md border border-emerald-300/40 bg-emerald-50 p-3 text-xs dark:border-emerald-500/20 dark:bg-emerald-500/10">
        <ShieldCheck className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
        <div className="text-emerald-800 dark:text-emerald-200">
          {language === "kn"
            ? "ಆಡಿಟ್ ಲಾಗ್ ಸ್ಥಿತಿ: ಆರೋಗ್ಯಕರ · ಚೈನ್‌ನಲ್ಲಿ 1,284 ನಮೂದುಗಳು · SHA-256 ಬೆಸುಗೆ ಪರಿಶೀಲನೆ ಯಶಸ್ವಿ"
            : "Audit chain status: healthy · 1,284 entries · SHA-256 hash chain verified"}
        </div>
        <span className="ml-auto font-mono text-[10px] text-emerald-700 dark:text-emerald-300">
          chain @ block 1284
        </span>
      </div>

      <div className="mb-3 flex items-center gap-3">
        <Input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={language === "kn" ? "request_id, ಬಳಕೆದಾರ, ಕ್ರಿಯೆ..." : "request_id, actor, action..."}
          className="h-8 max-w-md text-xs"
        />
        <span className="text-[10px] text-slate-500">
          {filtered.length} / {AUDIT_ROWS.length}
        </span>
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="border-b bg-slate-50 text-left dark:bg-white/[0.03]">
                <tr className="text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  <th className="px-4 py-2.5">request_id</th>
                  <th className="px-4 py-2.5">{language === "kn" ? "ಸಮಯ" : "Timestamp"}</th>
                  <th className="px-4 py-2.5">{language === "kn" ? "ಬಳಕೆದಾರ" : "Actor"}</th>
                  <th className="px-4 py-2.5">{language === "kn" ? "ಕ್ರಿಯೆ" : "Action"}</th>
                  <th className="px-4 py-2.5">{language === "kn" ? "ಸಂಪನ್ಮೂಲ" : "Resource"}</th>
                  <th className="px-4 py-2.5">{language === "kn" ? "ಫಲಿತಾಂಶ" : "Result"}</th>
                  <th className="px-4 py-2.5" />
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => (
                  <tr key={r.id} className="border-b last:border-0 hover:bg-slate-50/70 dark:hover:bg-white/[0.02]">
                    <td className="px-4 py-3 font-mono text-[10px] text-slate-500">{r.id}</td>
                    <td className="px-4 py-3 font-mono text-[10px] text-slate-600 dark:text-slate-400">{r.ts}</td>
                    <td className="px-4 py-3">
                      <div className="text-xs font-medium">{r.actor}</div>
                      <div className="text-[9px] uppercase tracking-wider text-slate-400">{r.role}</div>
                    </td>
                    <td className="px-4 py-3">{r.action[language]}</td>
                    <td className="px-4 py-3 font-mono text-[10px] text-slate-500">{r.resource}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${RESULT_TONE[r.result]}`}>
                        {r.result}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <button className="text-slate-400 hover:text-[#1e3a8a] dark:hover:text-[#C8A964]" aria-label="Open detail">
                        <ExternalLink className="h-3 w-3" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <div className="mt-4 flex items-start gap-2 text-[11px] text-slate-500 dark:text-slate-400">
        <ScrollText className="mt-0.5 h-3 w-3" />
        <span>
          {language === "kn"
            ? "ಲಾಗ್ ನಮೂದುಗಳನ್ನು ಬದಲಾಯಿಸಲಾಗದು. ಪ್ರತಿ ಸಾಲು SHA-256 ಬೆಸುಗೆ-ಸರಪಳಿಯಲ್ಲಿ ಲಾಕ್ ಆಗಿದೆ ಮತ್ತು 7 ವರ್ಷಗಳವರೆಗೆ ಉಳಿಸಲ್ಪಡುತ್ತದೆ."
            : "Log entries are immutable. Each row is locked into a SHA-256 hash chain and retained for 7 years."}
        </span>
      </div>
    </AppShell>
  );
}

export default function AuditPage() {
  return (
    <AuthGate requireRoles={["inspector", "sho", "dcp", "psi", "sub_inspector", "scrb_analyst", "admin", "guest"]}>
      <AuditInner />
    </AuthGate>
  );
}
