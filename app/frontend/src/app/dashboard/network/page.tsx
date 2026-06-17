"use client";

import * as React from "react";
import { AuthGate } from "@/components/AuthGate";
import { AppShell } from "@/components/shell/AppShell";
import { NetworkGraph } from "@/components/NetworkGraph";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useKspStore } from "@/lib/store";
import { Phone, Car, User as UserIcon, FileText, Search } from "lucide-react";

const SAMPLE_QUERIES = [
  { en: "Co-accused with Ravi K.", kn: "ರವಿ ಕೆ. ಅವರ ಸಹ-ಆರೋಪಿಗಳು" },
  { en: "Phone 9845*** network", kn: "ಫೋನ್ 9845*** ಜಾಲ" },
  { en: "Vehicle KA-01-1234 history", kn: "ವಾಹನ KA-01-1234 ಇತಿಹಾಸ" },
  { en: "Indiranagar gang last 90d", kn: "ಇಂದಿರಾನಗರ ಗ್ಯಾಂಗ್ ಕಳೆದ 90 ದಿನಗಳು" },
];

function NetworkInner() {
  const language = useKspStore((s) => s.language);
  const [q, setQ] = React.useState("");

  return (
    <AppShell
      title={language === "kn" ? "ಅಪರಾಧಿ ಜಾಲಗಳು" : "Criminal Networks"}
      subtitle={
        language === "kn"
          ? "ಫೋನ್, ವಾಹನ, ಸಹ-ಆರೋಪಿ ಸಂಪರ್ಕಗಳು — ಸ್ವಯಂಚಾಲಿತ ಜಾಲ ವಿಶ್ಲೇಷಣೆ"
          : "Phone, vehicle, and co-accused links — automatic link analysis"
      }
    >
      <div className="grid gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
        <Card>
          <CardContent className="p-4">
            <form
              onSubmit={(e) => e.preventDefault()}
              className="mb-4 flex items-center gap-2"
            >
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
                <Input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder={language === "kn" ? "ಹೆಸರು, ಫೋನ್, ವಾಹನ..." : "Name, phone, vehicle..."}
                  className="h-8 pl-8 text-xs"
                />
              </div>
            </form>

            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              {language === "kn" ? "ಮಾದರಿ ಪ್ರಶ್ನೆಗಳು" : "Sample queries"}
            </div>
            <ul className="space-y-1.5">
              {SAMPLE_QUERIES.map((s) => (
                <li key={s.en}>
                  <button
                    type="button"
                    onClick={() => setQ(s[language])}
                    className="w-full rounded-md border border-slate-200 px-2.5 py-2 text-left text-[11px] hover:border-[#1e3a8a] hover:bg-[#1e3a8a]/[0.04] dark:border-white/10 dark:hover:border-[#C8A964] dark:hover:bg-[#C8A964]/[0.04]"
                  >
                    {s[language]}
                  </button>
                </li>
              ))}
            </ul>

            <div className="my-4 h-px bg-slate-100 dark:bg-white/5" />

            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              {language === "kn" ? "ಸಂಪರ್ಕ ವಿಧಗಳು" : "Edge types"}
            </div>
            <ul className="space-y-1.5 text-[11px]">
              <li className="flex items-center gap-2">
                <UserIcon className="h-3 w-3 text-[#1e3a8a] dark:text-[#C8A964]" />
                {language === "kn" ? "ಸಹ-ಆರೋಪಿ" : "Co-accused"}
              </li>
              <li className="flex items-center gap-2">
                <Phone className="h-3 w-3 text-emerald-600" />
                {language === "kn" ? "ಫೋನ್ ಲಿಂಕ್" : "Phone link"}
              </li>
              <li className="flex items-center gap-2">
                <Car className="h-3 w-3 text-amber-600" />
                {language === "kn" ? "ವಾಹನ ಲಿಂಕ್" : "Vehicle link"}
              </li>
              <li className="flex items-center gap-2">
                <FileText className="h-3 w-3 text-violet-600" />
                {language === "kn" ? "FIR ಲಿಂಕ್" : "FIR link"}
              </li>
            </ul>
          </CardContent>
        </Card>

        <Card className="overflow-hidden">
          <CardContent className="h-[72vh] p-0">
            <NetworkGraph className="h-full w-full" />
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}

export default function NetworkPage() {
  return (
    <AuthGate requireRoles={["inspector", "sho", "dcp", "psi", "sub_inspector", "scrb_analyst", "admin", "guest"]}>
      <NetworkInner />
    </AuthGate>
  );
}
