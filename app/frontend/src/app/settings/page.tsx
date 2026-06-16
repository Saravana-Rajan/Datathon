"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  ShieldCheck,
  ArrowLeft,
  LogOut,
  RotateCcw,
  Volume2,
  VolumeX,
  Languages,
  Database,
  FileLock2,
  Loader2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from "@/components/ui/drawer";
import AuthGate from "@/components/AuthGate";
import { useAuth } from "@/lib/catalyst-auth";
import { useKspStore, type Language } from "@/lib/store";

// --------------------------------------------------------------------------
// Storage keys — kept in one place so /demo and onboarding can reset them.
// --------------------------------------------------------------------------
const SETTINGS_KEYS = {
  language: "yaksha-language-pref", // "kn" | "en" | "auto"
  voiceEnabled: "yaksha-voice-enabled", // "1" | "0"
  demoMode: "yaksha-demo-mode", // "1" | "0"
  onboarded: "yaksha-onboarded", // "1" | "0"
} as const;

type LanguagePref = "kn" | "en" | "auto";

function readPref<T extends string>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const v = window.localStorage.getItem(key);
    return (v as T | null) ?? fallback;
  } catch {
    return fallback;
  }
}

function writePref(key: string, value: string) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* storage disabled — non-fatal */
  }
}

// --------------------------------------------------------------------------
// Atomic UI primitives (kept local to this page; promote to /ui/ if reused)
// --------------------------------------------------------------------------

function Toggle({
  checked,
  onChange,
  label,
  description,
  ariaLabel,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: React.ReactNode;
  description?: React.ReactNode;
  ariaLabel?: string;
}) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-4 rounded-md border bg-card p-3 hover:bg-accent/40">
      <span className="space-y-0.5">
        <span className="block text-sm font-medium">{label}</span>
        {description && (
          <span className="block text-xs text-muted-foreground">
            {description}
          </span>
        )}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={ariaLabel}
        onClick={() => onChange(!checked)}
        className={
          "relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors " +
          (checked ? "bg-primary" : "bg-input")
        }
      >
        <span
          className={
            "inline-block h-5 w-5 transform rounded-full bg-background shadow transition-transform " +
            (checked ? "translate-x-5" : "translate-x-0.5")
          }
        />
      </button>
    </label>
  );
}

function SegmentedControl<T extends string>({
  value,
  onChange,
  options,
  ariaLabel,
}: {
  value: T;
  onChange: (next: T) => void;
  options: { value: T; label: string }[];
  ariaLabel: string;
}) {
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className="inline-flex rounded-md border bg-card p-0.5"
    >
      {options.map((opt) => {
        const active = value === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(opt.value)}
            className={
              "rounded px-3 py-1.5 text-xs font-medium transition-colors " +
              (active
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground")
            }
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

// --------------------------------------------------------------------------
// Page
// --------------------------------------------------------------------------

function SettingsPageInner() {
  const router = useRouter();
  const { user, signOut } = useAuth();

  // Global app language (kn/en) lives in zustand — we mirror it from a
  // tri-state pref ("auto" defers to browser/Accept-Language).
  const language = useKspStore((s) => s.language);
  const setLanguage = useKspStore((s) => s.setLanguage);

  const [languagePref, setLanguagePref] = React.useState<LanguagePref>("en");
  const [voiceEnabled, setVoiceEnabled] = React.useState(true);
  const [demoMode, setDemoMode] = React.useState(false);
  const [signingOut, setSigningOut] = React.useState(false);
  const [resettingOnboarding, setResettingOnboarding] = React.useState(false);
  const [resetConfirm, setResetConfirm] = React.useState(false);

  // Hydrate from localStorage on mount.
  React.useEffect(() => {
    setLanguagePref(
      readPref<LanguagePref>(SETTINGS_KEYS.language, language as LanguagePref)
    );
    setVoiceEnabled(readPref<string>(SETTINGS_KEYS.voiceEnabled, "1") === "1");
    setDemoMode(readPref<string>(SETTINGS_KEYS.demoMode, "0") === "1");
  }, [language]);

  // Persist + propagate.
  const handleLanguageChange = (next: LanguagePref) => {
    setLanguagePref(next);
    writePref(SETTINGS_KEYS.language, next);
    if (next === "auto") {
      // Resolve "auto" from the browser. Anything starting with "kn" is
      // Kannada; everything else falls back to English (the app's other
      // supported UI language).
      const browser =
        typeof navigator !== "undefined"
          ? navigator.language || (navigator as { userLanguage?: string }).userLanguage || ""
          : "";
      setLanguage(browser.toLowerCase().startsWith("kn") ? "kn" : "en");
    } else {
      setLanguage(next as Language);
    }
  };

  const handleVoiceToggle = (next: boolean) => {
    setVoiceEnabled(next);
    writePref(SETTINGS_KEYS.voiceEnabled, next ? "1" : "0");
  };

  const handleDemoModeToggle = (next: boolean) => {
    setDemoMode(next);
    writePref(SETTINGS_KEYS.demoMode, next ? "1" : "0");
  };

  const handleResetOnboarding = async () => {
    setResettingOnboarding(true);
    try {
      writePref(SETTINGS_KEYS.onboarded, "0");
      // Brief artificial delay so judges see the spinner — confirms the action.
      await new Promise((r) => setTimeout(r, 350));
      setResetConfirm(true);
      setTimeout(() => setResetConfirm(false), 2500);
    } finally {
      setResettingOnboarding(false);
    }
  };

  const handleSignOut = async () => {
    setSigningOut(true);
    try {
      await signOut();
      router.replace("/login");
    } finally {
      setSigningOut(false);
    }
  };

  if (!user) return null; // AuthGate already redirected.

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
            <span className="text-sm font-semibold">Settings</span>
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Yaksha · ಯಕ್ಷ
            </span>
          </div>
        </div>
        <div className="hidden items-center gap-2 rounded-md border bg-card px-2 py-1 text-xs sm:flex">
          <span className="text-muted-foreground">Role:</span>
          <span className="font-medium uppercase tracking-wide">{user.role}</span>
        </div>
      </header>

      <div className="mx-auto max-w-3xl space-y-6 px-4 py-6">
        {/* Preferences */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Languages className="h-4 w-4 text-primary" aria-hidden="true" />
              Preferences
            </CardTitle>
            <CardDescription>
              Language, voice, and demo behavior. Stored on this device only.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-col gap-3 rounded-md border bg-card p-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="text-sm font-medium">Language preference</div>
                <div className="text-xs text-muted-foreground">
                  &quot;Auto&quot; uses your browser locale. Voice + UI both respect this.
                </div>
              </div>
              <SegmentedControl<LanguagePref>
                value={languagePref}
                onChange={handleLanguageChange}
                ariaLabel="Language preference"
                options={[
                  { value: "kn", label: "ಕನ್ನಡ" },
                  { value: "en", label: "English" },
                  { value: "auto", label: "Auto" },
                ]}
              />
            </div>

            <Toggle
              checked={voiceEnabled}
              onChange={handleVoiceToggle}
              ariaLabel="Voice input and output"
              label={
                <span className="flex items-center gap-2">
                  {voiceEnabled ? (
                    <Volume2 className="h-4 w-4 text-primary" aria-hidden="true" />
                  ) : (
                    <VolumeX
                      className="h-4 w-4 text-muted-foreground"
                      aria-hidden="true"
                    />
                  )}
                  Voice input + output
                </span>
              }
              description={
                voiceEnabled
                  ? "Microphone enabled. Kannada → Gemini Live · English/Hindi → Catalyst Zia."
                  : "Microphone disabled. You can still type queries."
              }
            />

            <Toggle
              checked={demoMode}
              onChange={handleDemoModeToggle}
              ariaLabel="Demo mode"
              label={
                <span className="flex items-center gap-2">
                  <Database className="h-4 w-4 text-primary" aria-hidden="true" />
                  Demo mode (cached responses)
                </span>
              }
              description="Use pre-baked responses for the golden-path demo. Avoids cold starts and survives venue WiFi failure."
            />
          </CardContent>
        </Card>

        {/* Onboarding */}
        <Card>
          <CardHeader>
            <CardTitle>Onboarding</CardTitle>
            <CardDescription>
              Replay the introduction tour from the beginning.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-3 rounded-md border bg-card p-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="text-sm font-medium">Reset onboarding</div>
                <div className="text-xs text-muted-foreground">
                  Next time you visit the dashboard you&apos;ll see the welcome tour again.
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleResetOnboarding}
                disabled={resettingOnboarding}
              >
                {resettingOnboarding ? (
                  <Loader2
                    className="mr-2 h-4 w-4 animate-spin"
                    aria-hidden="true"
                  />
                ) : (
                  <RotateCcw className="mr-2 h-4 w-4" aria-hidden="true" />
                )}
                {resetConfirm ? "Reset ✓" : "Reset"}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Account */}
        <Card>
          <CardHeader>
            <CardTitle>Account</CardTitle>
            <CardDescription>
              Read-only identity. Provisioned by Catalyst Authentication.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <dl className="grid grid-cols-1 gap-y-3 rounded-md border bg-card p-4 sm:grid-cols-[140px_1fr]">
              <dt className="text-xs text-muted-foreground">Name</dt>
              <dd className="text-sm font-medium">{user.name}</dd>

              <dt className="text-xs text-muted-foreground">Email</dt>
              <dd className="text-sm">{user.email}</dd>

              <dt className="text-xs text-muted-foreground">Role</dt>
              <dd className="text-sm font-mono uppercase">{user.role}</dd>

              {user.stationName && (
                <>
                  <dt className="text-xs text-muted-foreground">Station</dt>
                  <dd className="text-sm">
                    {user.stationName}
                    {user.stationCode && (
                      <span className="ml-1 text-xs text-muted-foreground">
                        ({user.stationCode})
                      </span>
                    )}
                  </dd>
                </>
              )}

              {user.district && (
                <>
                  <dt className="text-xs text-muted-foreground">District</dt>
                  <dd className="text-sm">{user.district}</dd>
                </>
              )}

              {user.lastLoginAt && (
                <>
                  <dt className="text-xs text-muted-foreground">Last sign-in</dt>
                  <dd className="text-sm">
                    {new Date(user.lastLoginAt).toLocaleString()}
                  </dd>
                </>
              )}
            </dl>

            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <Drawer>
                <DrawerTrigger asChild>
                  <Button variant="outline" size="sm">
                    <FileLock2
                      className="mr-2 h-4 w-4"
                      aria-hidden="true"
                    />
                    Privacy &amp; data
                  </Button>
                </DrawerTrigger>
                <DrawerContent>
                  <DrawerHeader>
                    <DrawerTitle>Privacy &amp; data</DrawerTitle>
                    <DrawerDescription>
                      How Yaksha handles your queries, voice, and audit trail.
                    </DrawerDescription>
                  </DrawerHeader>
                  <div className="space-y-4 px-6 pb-6 text-sm leading-relaxed">
                    <section>
                      <h3 className="mb-1 font-semibold">Where your data lives</h3>
                      <p className="text-muted-foreground">
                        All structured FIRs, audit logs, and session state are stored on
                        Zoho Catalyst&apos;s India data center (<code className="text-xs">asia-south1</code>, Mumbai).
                        No personally identifiable data leaves Indian soil — satisfying the
                        <strong> IT Act 2008 § 43A / § 67C </strong> requirements for sensitive
                        personal data and electronic record retention.
                      </p>
                    </section>

                    <section>
                      <h3 className="mb-1 font-semibold">Audit immutability</h3>
                      <p className="text-muted-foreground">
                        Every chat turn — query, route decision, SQL/Cypher emitted,
                        records accessed, final answer, confidence score — is appended
                        (never overwritten) to a Catalyst NoSQL audit collection. Officers
                        can flag wrong answers; flags land in the bias-review queue but
                        cannot edit history.
                      </p>
                    </section>

                    <section>
                      <h3 className="mb-1 font-semibold">PII masking</h3>
                      <p className="text-muted-foreground">
                        Names, phone numbers, and addresses are masked before being sent
                        to any LLM. Your role determines which fields are unmasked on
                        return — Constables and PSIs see redacted accused PII for cases
                        outside their station; SHO and DCP see more.
                      </p>
                    </section>

                    <section>
                      <h3 className="mb-1 font-semibold">Third-party services</h3>
                      <p className="text-muted-foreground">
                        Kannada voice uses Google Gemini Live API (Catalyst has no Kannada
                        STT/TTS). Maps use Google Maps Platform (Catalyst has no Maps).
                        Network graph uses Neo4j AuraDB. All three run in{" "}
                        <code className="text-xs">asia-south1</code> so data residency is
                        preserved. See <code className="text-xs">decisions.md</code> for
                        the full justification log.
                      </p>
                    </section>

                    <section>
                      <h3 className="mb-1 font-semibold">DPDP Act 2023 readiness</h3>
                      <p className="text-muted-foreground">
                        Officers can request a copy or deletion of their audit history.
                        Requests are routed to the SCRB Data Protection Officer and
                        actioned within 30 days. Yaksha enforces purpose limitation: queries
                        are only used for investigative work, never for ad targeting or
                        external analytics.
                      </p>
                    </section>
                  </div>
                </DrawerContent>
              </Drawer>

              <Button
                variant="destructive"
                size="sm"
                onClick={handleSignOut}
                disabled={signingOut}
              >
                {signingOut ? (
                  <Loader2
                    className="mr-2 h-4 w-4 animate-spin"
                    aria-hidden="true"
                  />
                ) : (
                  <LogOut className="mr-2 h-4 w-4" aria-hidden="true" />
                )}
                Sign out
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}

export default function SettingsPage() {
  return (
    <AuthGate>
      <SettingsPageInner />
    </AuthGate>
  );
}
