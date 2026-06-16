"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  ShieldCheck,
  ArrowLeft,
  Repeat,
  Lock,
  Eye,
  EyeOff,
  MapPin,
  Users,
  TrendingUp,
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
import AuthGate from "@/components/AuthGate";
import {
  impersonateDemoPersona,
  useAuth,
  type CatalystUser,
} from "@/lib/catalyst-auth";
import type { Role } from "@/lib/store";

// --------------------------------------------------------------------------
// Demo personas (mirror DEMO_ACCOUNTS in catalyst-auth.ts)
// --------------------------------------------------------------------------

interface Persona {
  email: string;
  shortName: string; // "PSI Suresh"
  fullName: string; // "PSI Suresh Kumar"
  role: Role;
  jurisdiction: string; // "MG Road Police Station (Bengaluru Urban)"
  bullet: string; // one-liner describing scope
  color: string; // tailwind accent class for the active tab pill
}

const PERSONAS: Persona[] = [
  {
    email: "suresh@ksp.gov.in",
    shortName: "PSI Suresh",
    fullName: "PSI Suresh Kumar",
    role: "sub_inspector",
    jurisdiction: "MG Road PS · Bengaluru Urban",
    bullet: "Own station only · case-level PII for own station",
    color: "bg-blue-600 text-white",
  },
  {
    email: "lakshmi@ksp.gov.in",
    shortName: "SHO Lakshmi",
    fullName: "SHO Lakshmi Devi",
    role: "sho",
    jurisdiction: "Halasuru PS + neighbours · Bengaluru Urban",
    bullet: "Full station + neighbouring stations · cross-station patterns",
    color: "bg-amber-600 text-white",
  },
  {
    email: "mehta@ksp.gov.in",
    shortName: "DCP Mehta",
    fullName: "DCP Rajeev Mehta",
    role: "dcp",
    jurisdiction: "Bengaluru Urban · district-wide",
    bullet: "District aggregates only · no case-level PII outside own command",
    color: "bg-emerald-600 text-white",
  },
];

// --------------------------------------------------------------------------
// The shared query result. We render the SAME query with different masking
// per role to make the RBAC story land for judges in one screen.
//
// Query: "Show me recent burglary cases near MG Road / Indiranagar"
// --------------------------------------------------------------------------

interface CaseRow {
  firNo: string;
  station: string;
  date: string;
  crime: string;
  location: string;
  // Fields below are conditionally masked by role.
  complainant: string;
  complainantPhone: string;
  accused: string;
  accusedPhone: string;
  io: string;
  narrative: string;
}

const SHARED_CASES: CaseRow[] = [
  {
    firNo: "MGR/2025/00001",
    station: "MG Road PS",
    date: "2025-02-18",
    crime: "Burglary (IPC 380, 457)",
    location: "ITPL Road",
    complainant: "Manjunath Babu (40, M)",
    complainantPhone: "78XXXXXX26",
    accused: "Manpreet Chowdary (on bail)",
    accusedPhone: "91XXXXXX44",
    io: "Insp. Rashid Saldanha (KSP92397)",
    narrative:
      "Burglars entered through ventilation shaft of first floor flat; stole jewellery and laptop.",
  },
  {
    firNo: "HAL/2025/00114",
    station: "Halasuru PS",
    date: "2025-02-22",
    crime: "Burglary (IPC 454, 380)",
    location: "Indiranagar 100ft Rd",
    complainant: "Anitha S. (35, F)",
    complainantPhone: "98XXXXXX10",
    accused: "Manpreet Chowdary (on bail)",
    accusedPhone: "91XXXXXX44",
    io: "PSI Karthik Hegde (KSP44102)",
    narrative:
      "House break-in during daytime when occupants were away. CCTV captures match prior MO.",
  },
  {
    firNo: "ULS/2025/00088",
    station: "Ulsoor PS",
    date: "2025-02-25",
    crime: "Burglary (IPC 380)",
    location: "Cambridge Layout",
    complainant: "T. Ramesh (52, M)",
    complainantPhone: "90XXXXXX77",
    accused: "Unknown × 2",
    accusedPhone: "—",
    io: "PSI Vandana Patil (KSP55211)",
    narrative:
      "Lock broken on rear entrance during night hours; same ventilation-shaft MO reported.",
  },
];

// --------------------------------------------------------------------------
// Role-aware data view. The actual backend enforces this — we replicate the
// rules here so the UI can show what each persona would see without making
// three round-trips.
// --------------------------------------------------------------------------

function applyRoleMask(cases: CaseRow[], persona: Persona): CaseRow[] {
  switch (persona.role) {
    case "sub_inspector": {
      // PSI Suresh is posted at MG Road. He sees full case PII for MGR cases
      // and complete redaction for cases at other stations.
      return cases.map((c) =>
        c.station === "MG Road PS"
          ? c
          : {
              ...c,
              complainant: "█ redacted (other station)",
              complainantPhone: "███████",
              accused: "█ redacted (other station)",
              accusedPhone: "███████",
              io: "█ redacted",
              narrative: "Narrative withheld — request via SHO escalation.",
            }
      );
    }
    case "sho": {
      // SHO Lakshmi sees full PII for own + neighbouring stations. For this
      // demo all three rows fall in her cluster, so everything is visible —
      // except accused phone numbers which require DCP/SCRB.
      return cases.map((c) => ({
        ...c,
        accusedPhone: "███████",
      }));
    }
    case "dcp": {
      // DCP Mehta sees district-level aggregates: case counts, no PII.
      // We replace the table rows with summary tiles in the view below.
      return cases;
    }
    default:
      return cases;
  }
}

function maskedField(
  value: string,
  visible: boolean
): { display: string; visible: boolean } {
  return visible
    ? { display: value, visible: true }
    : { display: "▒▒▒▒▒▒▒▒▒", visible: false };
}

// --------------------------------------------------------------------------
// Visualizations per persona — only one is shown at a time, with cross-fade.
// --------------------------------------------------------------------------

function PsiView({ cases }: { cases: CaseRow[] }) {
  return (
    <div className="space-y-3">
      <div className="rounded-md border border-blue-200 bg-blue-50 p-3 text-xs text-blue-900 dark:border-blue-900/40 dark:bg-blue-950/40 dark:text-blue-200">
        <div className="flex items-start gap-2">
          <Eye className="mt-0.5 h-3.5 w-3.5" aria-hidden="true" />
          <span>
            <strong>Scope:</strong> own station only. Records from MG Road PS
            show full PII; records from Halasuru and Ulsoor are redacted with
            the official mask pattern used in CCTNS exports.
          </span>
        </div>
      </div>
      <CaseTable cases={cases} role="sub_inspector" />
    </div>
  );
}

function ShoView({ cases }: { cases: CaseRow[] }) {
  return (
    <div className="space-y-3">
      <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/40 dark:text-amber-200">
        <div className="flex items-start gap-2">
          <Eye className="mt-0.5 h-3.5 w-3.5" aria-hidden="true" />
          <span>
            <strong>Scope:</strong> own station + neighbouring stations.
            Cross-station MO match flagged — same suspect (Manpreet Chowdary)
            visible across MGR and HAL. Accused phone numbers require DCP/SCRB.
          </span>
        </div>
      </div>
      <CaseTable cases={cases} role="sho" />
    </div>
  );
}

function DcpView({ cases }: { cases: CaseRow[] }) {
  // Aggregate the same row set into district-level tiles. No case-level PII.
  const total = cases.length;
  const stations = Array.from(new Set(cases.map((c) => c.station))).length;
  const sameSuspect = cases.filter((c) =>
    c.accused.includes("Manpreet Chowdary")
  ).length;

  return (
    <div className="space-y-3">
      <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-900 dark:border-emerald-900/40 dark:bg-emerald-950/40 dark:text-emerald-200">
        <div className="flex items-start gap-2">
          <EyeOff className="mt-0.5 h-3.5 w-3.5" aria-hidden="true" />
          <span>
            <strong>Scope:</strong> district aggregates only. Case-level PII
            is intentionally not surfaced at this level — only DySP/SCRB roles
            with active investigative authority unmask individual rows.
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <SummaryTile
          icon={<MapPin className="h-4 w-4" aria-hidden="true" />}
          label="Burglary cases (last 7 days)"
          value={String(total)}
          hint="across Bengaluru Urban"
        />
        <SummaryTile
          icon={<Users className="h-4 w-4" aria-hidden="true" />}
          label="Affected stations"
          value={String(stations)}
          hint="MGR · HAL · ULS"
        />
        <SummaryTile
          icon={<TrendingUp className="h-4 w-4" aria-hidden="true" />}
          label="Cross-station MO match"
          value={`${sameSuspect}/${total}`}
          hint="same modus operandi"
        />
      </div>

      <div className="rounded-md border bg-card p-4 text-sm">
        <div className="mb-1 font-medium">Recommendation (resource hint)</div>
        <p className="text-xs text-muted-foreground">
          Coordinated MO across MGR, HAL, ULS in 7-day window suggests one
          working pattern. Suggest task-force briefing with SHOs of affected
          stations. Confidence interval: 0.78 · features: location cluster, MO
          text similarity, time-of-day overlap. <em>Caste/religion/community
          features excluded by policy.</em>
        </p>
      </div>
    </div>
  );
}

function SummaryTile({
  icon,
  label,
  value,
  hint,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="rounded-md border bg-card p-4">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className="mt-1 text-2xl font-semibold tracking-tight">{value}</div>
      <div className="text-[11px] text-muted-foreground">{hint}</div>
    </div>
  );
}

function CaseTable({ cases, role }: { cases: CaseRow[]; role: Role }) {
  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="min-w-full text-xs" role="table" aria-label="Cases">
        <thead className="bg-muted/50 text-muted-foreground">
          <tr>
            <th className="px-2 py-2 text-left font-medium">FIR</th>
            <th className="px-2 py-2 text-left font-medium">Station</th>
            <th className="px-2 py-2 text-left font-medium">Date</th>
            <th className="px-2 py-2 text-left font-medium">Location</th>
            <th className="px-2 py-2 text-left font-medium">Complainant</th>
            <th className="px-2 py-2 text-left font-medium">Accused</th>
            <th className="px-2 py-2 text-left font-medium">Phone (accused)</th>
            <th className="px-2 py-2 text-left font-medium">IO</th>
          </tr>
        </thead>
        <tbody>
          {cases.map((c) => {
            const masked =
              role === "sub_inspector" && c.station !== "MG Road PS";
            return (
              <tr
                key={c.firNo}
                className={
                  "border-t " +
                  (masked ? "bg-muted/30 text-muted-foreground" : "bg-card")
                }
              >
                <td className="px-2 py-2 font-mono">{c.firNo}</td>
                <td className="px-2 py-2">{c.station}</td>
                <td className="px-2 py-2 whitespace-nowrap">{c.date}</td>
                <td className="px-2 py-2">{c.location}</td>
                <td className="px-2 py-2">
                  <MaskedCell
                    value={c.complainant}
                    masked={masked}
                  />
                </td>
                <td className="px-2 py-2">
                  <MaskedCell value={c.accused} masked={masked} />
                </td>
                <td className="px-2 py-2">
                  <MaskedCell
                    value={c.accusedPhone}
                    masked={role !== "dcp" && c.accusedPhone === "███████"}
                    alwaysMasked={role === "sho" || masked}
                  />
                </td>
                <td className="px-2 py-2">
                  <MaskedCell value={c.io} masked={masked} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function MaskedCell({
  value,
  masked,
  alwaysMasked,
}: {
  value: string;
  masked: boolean;
  alwaysMasked?: boolean;
}) {
  const hide = masked || alwaysMasked;
  const m = maskedField(value, !hide);
  if (m.visible) return <span>{m.display}</span>;
  return (
    <span className="inline-flex items-center gap-1 font-mono text-[10px] text-muted-foreground">
      <Lock className="h-3 w-3" aria-hidden="true" />
      {m.display}
    </span>
  );
}

// --------------------------------------------------------------------------
// Page
// --------------------------------------------------------------------------

function RoleSwitchInner() {
  const router = useRouter();
  const { user } = useAuth();
  const [activeEmail, setActiveEmail] = React.useState<string>(
    user?.email && PERSONAS.some((p) => p.email === user.email)
      ? user.email
      : PERSONAS[0].email
  );
  const [switching, setSwitching] = React.useState(false);
  const [animKey, setAnimKey] = React.useState(0);

  const activePersona =
    PERSONAS.find((p) => p.email === activeEmail) ?? PERSONAS[0];

  const handleSwitchTo = async (email: string) => {
    if (email === activeEmail || switching) return;
    setSwitching(true);
    try {
      await impersonateDemoPersona(email);
      setActiveEmail(email);
      setAnimKey((k) => k + 1);
    } finally {
      // Slight delay so the "Switch role" transition reads as deliberate.
      setTimeout(() => setSwitching(false), 250);
    }
  };

  const handleNextRole = async () => {
    const idx = PERSONAS.findIndex((p) => p.email === activeEmail);
    const next = PERSONAS[(idx + 1) % PERSONAS.length];
    await handleSwitchTo(next.email);
  };

  const masked = applyRoleMask(SHARED_CASES, activePersona);

  return (
    <main className="min-h-screen bg-background">
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b bg-background/80 px-4 backdrop-blur">
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => router.push("/")}
            aria-label="Back to dashboard"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          </Button>
          <ShieldCheck className="h-5 w-5 text-primary" aria-hidden="true" />
          <div className="flex flex-col leading-tight">
            <span className="text-sm font-semibold">RBAC Live Demo</span>
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Feature 9 · Role-based secure access
            </span>
          </div>
        </div>

        <Button
          size="sm"
          onClick={handleNextRole}
          disabled={switching}
          className={
            "min-w-[140px] transition-all duration-300 " + activePersona.color
          }
          aria-label="Cycle to next role"
        >
          <Repeat
            className={
              "mr-2 h-4 w-4 transition-transform " +
              (switching ? "animate-spin" : "")
            }
            aria-hidden="true"
          />
          Switch role
        </Button>
      </header>

      <div className="mx-auto max-w-6xl space-y-4 px-4 py-6">
        <Card>
          <CardHeader>
            <CardTitle>One query, three views</CardTitle>
            <CardDescription>
              The same query — <em>&quot;Show recent burglary cases near MG Road
              / Indiranagar&quot;</em> — returns different data per role. Same
              records, different field-level access enforced by Catalyst
              Authentication custom claims.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs
              value={activeEmail}
              onValueChange={(v) => handleSwitchTo(v)}
              className="space-y-4"
            >
              <TabsList className="grid w-full grid-cols-3 gap-1">
                {PERSONAS.map((p) => (
                  <TabsTrigger
                    key={p.email}
                    value={p.email}
                    className="flex-col items-start gap-0.5 px-3 py-2 text-left data-[state=active]:shadow"
                  >
                    <span className="text-sm font-medium">{p.shortName}</span>
                    <span className="text-[10px] font-normal text-muted-foreground">
                      {p.jurisdiction}
                    </span>
                  </TabsTrigger>
                ))}
              </TabsList>

              {PERSONAS.map((p) => (
                <TabsContent key={p.email} value={p.email}>
                  <ActivePersonaHeader persona={p} user={user} />
                  <div
                    key={`${p.email}-${animKey}`}
                    className="animate-in fade-in-50 slide-in-from-bottom-2 duration-300"
                  >
                    {p.role === "sub_inspector" && (
                      <PsiView cases={masked} />
                    )}
                    {p.role === "sho" && <ShoView cases={masked} />}
                    {p.role === "dcp" && <DcpView cases={masked} />}
                  </div>
                </TabsContent>
              ))}
            </Tabs>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">How this is enforced</CardTitle>
            <CardDescription>
              The frontend just renders what it&apos;s given. The real RBAC
              boundary is in the Catalyst Function layer.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-3 text-xs sm:grid-cols-3">
            <Step
              n={1}
              title="JWT claims"
              body="Each user's Catalyst Auth JWT carries `ksp_role`, `station_code`, and `district` custom claims. The frontend reads them only for UI hints."
            />
            <Step
              n={2}
              title="SQL/Cypher rewrite"
              body="Specialist Functions append WHERE clauses based on the JWT (e.g. `station_code = 'MGR'` for PSI). Officers cannot bypass by editing the prompt."
            />
            <Step
              n={3}
              title="Field-level masking"
              body="The synthesizer masks PII fields per role policy before serializing the response. Every masking decision is logged to the audit trail."
            />
          </CardContent>
        </Card>
      </div>
    </main>
  );
}

function ActivePersonaHeader({
  persona,
  user,
}: {
  persona: Persona;
  user: CatalystUser | null;
}) {
  const youAreThem = user?.email === persona.email;
  return (
    <div className="mb-3 flex flex-col gap-2 rounded-md border bg-card p-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-3">
        <div
          className={
            "flex h-9 w-9 items-center justify-center rounded-full text-xs font-semibold " +
            persona.color
          }
          aria-hidden="true"
        >
          {persona.shortName
            .split(" ")
            .map((w) => w[0])
            .join("")}
        </div>
        <div>
          <div className="text-sm font-medium">{persona.fullName}</div>
          <div className="text-xs text-muted-foreground">{persona.bullet}</div>
        </div>
      </div>
      <div className="flex items-center gap-2 text-[11px]">
        <span className="rounded-md border bg-background px-2 py-1 font-mono uppercase">
          {persona.role}
        </span>
        {youAreThem && (
          <span className="rounded-md bg-emerald-100 px-2 py-1 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200">
            Current session
          </span>
        )}
      </div>
    </div>
  );
}

function Step({
  n,
  title,
  body,
}: {
  n: number;
  title: string;
  body: string;
}) {
  return (
    <div className="rounded-md border bg-card p-3">
      <div className="mb-1 flex items-center gap-2">
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
          {n}
        </span>
        <span className="text-sm font-medium">{title}</span>
      </div>
      <p className="text-xs leading-relaxed text-muted-foreground">{body}</p>
    </div>
  );
}

export default function RoleSwitchPage() {
  return (
    <AuthGate>
      <RoleSwitchInner />
    </AuthGate>
  );
}
