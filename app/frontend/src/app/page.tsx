"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ShieldCheck,
  Mic,
  Map as MapIcon,
  Share2,
  TrendingUp,
  ArrowRight,
  Github,
  Languages,
  Lock,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { useKspStore, type Language } from "@/lib/store";

// --------------------------------------------------------------------------
// Brand palette (KSP navy + khaki) — matches /login for visual continuity.
// --------------------------------------------------------------------------
const NAVY = "#0c1a3d";
const NAVY_DEEP = "#001F3F";
const KHAKI = "#C8A964";
const KHAKI_DEEP = "#b8860b";

const COPY: Record<
  Language,
  {
    eyebrow: string;
    heroTitle: React.ReactNode;
    heroSubtitle: string;
    primaryCta: string;
    secondaryCta: string;
    featuresTitle: string;
    feature1Title: string;
    feature1Desc: string;
    feature2Title: string;
    feature2Desc: string;
    feature3Title: string;
    feature3Desc: string;
    feature4Title: string;
    feature4Desc: string;
    statsTitle: string;
    stat1: string;
    stat1Label: string;
    stat2: string;
    stat2Label: string;
    stat3: string;
    stat3Label: string;
    complianceTitle: string;
    complianceItems: string[];
    footerNote: string;
    footerLine: string;
  }
> = {
  en: {
    eyebrow: "Karnataka State Police · Internal Tool · Restricted",
    heroTitle: (
      <>
        Karnataka Police&apos;s{" "}
        <span style={{ color: KHAKI }}>bilingual investigator AI.</span>
      </>
    ),
    heroSubtitle:
      "Ask any question about crime data in Kannada or English. Get instant answers with maps, criminal networks, predictions, and a full audit trail.",
    primaryCta: "Sign in",
    secondaryCta: "View demo as guest",
    featuresTitle: "Built for the field, not the data center",
    feature1Title: "Bilingual voice",
    feature1Desc:
      "Speak or type in Kannada or English. Sarvik understands code-mixed queries the way constables actually talk.",
    feature2Title: "Live maps",
    feature2Desc:
      "Every FIR, hotspot, and station plotted on a single India-rendered map. Time-scrub through any window.",
    feature3Title: "Criminal networks",
    feature3Desc:
      "See who knows whom. Phone, vehicle, and co-accused links surface gangs without manual link analysis.",
    feature4Title: "Predictive insights",
    feature4Desc:
      "Forecast crime patterns by ward and beat. Every prediction comes with confidence bands and a full audit trail.",
    statsTitle: "Karnataka, end to end",
    stat1: "1,100+",
    stat1Label: "police stations",
    stat2: "30",
    stat2Label: "districts covered",
    stat3: "100%",
    stat3Label: "India data residency",
    complianceTitle: "Compliance and data residency",
    complianceItems: [
      "Hosted on Zoho Catalyst — Mumbai DC (asia-south1)",
      "IT Act 2008 § 67C compliant immutable audit log",
      "DPDP Act 2023 ready — purpose-limited access",
      "JWT role claims revalidated server-side every call",
    ],
    footerNote: "Sarvik is a Datathon 2026 prototype built for Karnataka State Police.",
    footerLine:
      "Property of Karnataka State Police. Unauthorized access is a crime under IT Act § 66.",
  },
  kn: {
    eyebrow: "ಕರ್ನಾಟಕ ರಾಜ್ಯ ಪೊಲೀಸ್ · ಆಂತರಿಕ ಸಾಧನ · ನಿರ್ಬಂಧಿತ",
    heroTitle: (
      <>
        ಕರ್ನಾಟಕ ಪೊಲೀಸ್‌ನ{" "}
        <span style={{ color: KHAKI }}>ದ್ವಿಭಾಷಾ ತನಿಖಾ AI.</span>
      </>
    ),
    heroSubtitle:
      "ಕನ್ನಡ ಅಥವಾ ಇಂಗ್ಲಿಷ್‌ನಲ್ಲಿ ಅಪರಾಧ ದತ್ತಾಂಶ ಕುರಿತು ಯಾವುದೇ ಪ್ರಶ್ನೆ ಕೇಳಿ. ನಕ್ಷೆ, ಅಪರಾಧಿ ಜಾಲ, ಭವಿಷ್ಯವಾಣಿ ಮತ್ತು ಪೂರ್ಣ ಆಡಿಟ್‌ನೊಂದಿಗೆ ತಕ್ಷಣ ಉತ್ತರ ಪಡೆಯಿರಿ.",
    primaryCta: "ಸೈನ್ ಇನ್",
    secondaryCta: "ಅತಿಥಿಯಾಗಿ ಡೆಮೋ ನೋಡಿ",
    featuresTitle: "ಡೇಟಾ ಸೆಂಟರ್‌ಗಲ್ಲ — ಫೀಲ್ಡ್‌ಗಾಗಿ ನಿರ್ಮಿಸಲಾಗಿದೆ",
    feature1Title: "ದ್ವಿಭಾಷಾ ಧ್ವನಿ",
    feature1Desc:
      "ಕನ್ನಡ ಅಥವಾ ಇಂಗ್ಲಿಷ್‌ನಲ್ಲಿ ಮಾತನಾಡಿ ಅಥವಾ ಟೈಪ್ ಮಾಡಿ. ಕಾನ್‌ಸ್ಟೇಬಲ್‌ಗಳು ಮಾತನಾಡುವ ಮಿಶ್ರ ಭಾಷೆಯನ್ನು ಸಾರ್ವಿಕ್ ಅರ್ಥ ಮಾಡಿಕೊಳ್ಳುತ್ತದೆ.",
    feature2Title: "ಲೈವ್ ನಕ್ಷೆ",
    feature2Desc:
      "ಪ್ರತಿ FIR, ಹಾಟ್‌ಸ್ಪಾಟ್, ಸ್ಟೇಷನ್ ಒಂದೇ ಭಾರತೀಯ ನಕ್ಷೆಯಲ್ಲಿ. ಯಾವುದೇ ಸಮಯದ ಶ್ರೇಣಿಯ ಮೂಲಕ ಸ್ಕ್ರಬ್ ಮಾಡಿ.",
    feature3Title: "ಅಪರಾಧಿ ಜಾಲ",
    feature3Desc:
      "ಯಾರಿಗೆ ಯಾರು ಪರಿಚಯ ಎಂದು ನೋಡಿ. ಫೋನ್, ವಾಹನ, ಸಹ-ಆರೋಪಿ ಸಂಪರ್ಕಗಳು ಗ್ಯಾಂಗ್‌ಗಳನ್ನು ಸ್ವಯಂಚಾಲಿತವಾಗಿ ಕಂಡುಹಿಡಿಯುತ್ತವೆ.",
    feature4Title: "ಭವಿಷ್ಯಸೂಚಕ ಒಳನೋಟ",
    feature4Desc:
      "ವಾರ್ಡ್ ಮತ್ತು ಬೀಟ್ ಪ್ರಕಾರ ಅಪರಾಧ ಮಾದರಿಗಳನ್ನು ಮುನ್ಸೂಚಿಸಿ. ಪ್ರತಿ ಭವಿಷ್ಯವಾಣಿ ವಿಶ್ವಾಸ ಶ್ರೇಣಿ ಮತ್ತು ಪೂರ್ಣ ಆಡಿಟ್‌ನೊಂದಿಗೆ ಬರುತ್ತದೆ.",
    statsTitle: "ಕರ್ನಾಟಕ, ಪೂರ್ಣ ಶ್ರೇಣಿ",
    stat1: "1,100+",
    stat1Label: "ಪೊಲೀಸ್ ಠಾಣೆಗಳು",
    stat2: "30",
    stat2Label: "ಜಿಲ್ಲೆಗಳು",
    stat3: "100%",
    stat3Label: "ಭಾರತೀಯ ಡೇಟಾ ಸ್ಥಾನ",
    complianceTitle: "ಅನುಸರಣೆ ಮತ್ತು ಡೇಟಾ ನಿವಾಸ",
    complianceItems: [
      "Zoho Catalyst — ಮುಂಬೈ DC ನಲ್ಲಿ ಹೋಸ್ಟ್ ಮಾಡಲಾಗಿದೆ",
      "IT ಕಾಯ್ದೆ 2008 § 67C ಪಾಲನೆ — ಬದಲಾಯಿಸಲಾಗದ ಆಡಿಟ್ ಲಾಗ್",
      "DPDP ಕಾಯ್ದೆ 2023 ಸಿದ್ಧ — ಉದ್ದೇಶ-ನಿರ್ಬಂಧಿತ ಪ್ರವೇಶ",
      "ಪ್ರತಿ ಕರೆಯಲ್ಲೂ JWT ರೋಲ್ ಕ್ಲೈಮ್ ಸರ್ವರ್‌ನಲ್ಲಿ ಪರಿಶೀಲನೆ",
    ],
    footerNote:
      "ಸಾರ್ವಿಕ್ — ಕರ್ನಾಟಕ ರಾಜ್ಯ ಪೊಲೀಸ್‌ಗಾಗಿ ನಿರ್ಮಿಸಲಾದ Datathon 2026 ಮಾದರಿ.",
    footerLine:
      "ಕರ್ನಾಟಕ ರಾಜ್ಯ ಪೊಲೀಸ್ ಆಸ್ತಿ. ಅನಧಿಕೃತ ಪ್ರವೇಶ IT ಕಾಯ್ದೆ § 66 ಅಡಿಯಲ್ಲಿ ಶಿಕ್ಷಾರ್ಹ.",
  },
};

function SarvikShield({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 64 64"
      role="img"
      aria-label="Sarvik shield"
      className={className}
    >
      <defs>
        <linearGradient id="sarvik-shield-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1e3a8a" />
          <stop offset="100%" stopColor={NAVY} />
        </linearGradient>
        <linearGradient id="sarvik-shield-trim" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={KHAKI} />
          <stop offset="100%" stopColor={KHAKI_DEEP} />
        </linearGradient>
      </defs>
      <path
        d="M32 2 L58 12 V32 C58 46 46 58 32 62 C18 58 6 46 6 32 V12 Z"
        fill="url(#sarvik-shield-fill)"
        stroke="url(#sarvik-shield-trim)"
        strokeWidth="2"
      />
      <path
        d="M32 14 L46 20 V32 C46 41 39 49 32 52 C25 49 18 41 18 32 V20 Z"
        fill="none"
        stroke="url(#sarvik-shield-trim)"
        strokeWidth="1.2"
      />
      <text
        x="32"
        y="38"
        textAnchor="middle"
        fontFamily="serif"
        fontSize="16"
        fontWeight="700"
        fill="url(#sarvik-shield-trim)"
      >
        ಸ
      </text>
    </svg>
  );
}

interface Feature {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  desc: string;
}

export default function LandingPage() {
  const router = useRouter();
  const language = useKspStore((s) => s.language);
  const setLanguage = useKspStore((s) => s.setLanguage);
  const setRole = useKspStore((s) => s.setRole);
  const setSession = useKspStore((s) => s.setSession);
  const t = COPY[language];

  const features: Feature[] = [
    { icon: Mic, title: t.feature1Title, desc: t.feature1Desc },
    { icon: MapIcon, title: t.feature2Title, desc: t.feature2Desc },
    { icon: Share2, title: t.feature3Title, desc: t.feature3Desc },
    { icon: TrendingUp, title: t.feature4Title, desc: t.feature4Desc },
  ];

  const handleGuestDemo = React.useCallback(() => {
    // Lay down a guest session token so AuthGate accepts the visit without
    // hitting Catalyst Authentication. This is intentionally permissive — judges
    // and reviewers need to click into the workspace without provisioning.
    try {
      const now = new Date();
      const expires = new Date(now.getTime() + 1000 * 60 * 60 * 4).toISOString();
      const guestSession = {
        user: {
          id: "guest-demo",
          email: "guest@sarvik.local",
          name: "Guest Reviewer",
          role: "guest" as const,
          lastLoginAt: now.toISOString(),
        },
        jwt: "guest.guest.guest",
        expiresAt: expires,
      };
      localStorage.setItem("sarvik-auth-session", JSON.stringify(guestSession));
      localStorage.setItem("sarvik-guest-session", "true");
      window.dispatchEvent(new Event("sarvik-auth-change"));
    } catch {
      // localStorage unavailable — AuthGate will redirect to /login.
    }
    setRole("guest");
    setSession("guest-demo-session", "guest-demo");
    router.push("/dashboard");
  }, [router, setRole, setSession]);

  return (
    <main
      className="relative min-h-screen overflow-hidden text-slate-100"
      style={{ backgroundColor: NAVY }}
    >
      {/* Decorative khaki/navy radial wash */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
        <div
          className="absolute -left-32 -top-32 h-[520px] w-[520px] rounded-full blur-3xl"
          style={{ background: `${KHAKI}1a` }}
        />
        <div
          className="absolute -right-40 top-32 h-[560px] w-[560px] rounded-full blur-3xl"
          style={{ background: "rgba(30,58,138,0.45)" }}
        />
        <div
          className="absolute left-1/2 top-2/3 h-[800px] w-[800px] -translate-x-1/2 rounded-full border"
          style={{ borderColor: `${KHAKI}10` }}
        />
      </div>

      {/* Top bar */}
      <header className="relative z-10 mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
        <div className="flex items-center gap-3">
          <SarvikShield className="h-10 w-10 drop-shadow-[0_8px_24px_rgba(200,169,100,0.25)]" />
          <div className="leading-tight">
            <div className="text-lg font-semibold tracking-tight text-white">
              Sarvik
            </div>
            <div className="text-[10px] uppercase tracking-[0.22em]" style={{ color: KHAKI }}>
              {language === "kn" ? "ತನಿಖಾಧಿಕಾರಿಗಳ ಸಹಾಯಕ" : "Investigator's Companion"}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div
            className="hidden items-center gap-1 rounded-md border border-white/10 bg-white/5 p-0.5 backdrop-blur sm:flex"
            role="group"
            aria-label="Language"
          >
            <Languages className="ml-1 h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
            {(["en", "kn"] as Language[]).map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => setLanguage(opt)}
                aria-pressed={language === opt}
                className={
                  "rounded px-2 py-1 text-xs font-medium transition-colors " +
                  (language === opt
                    ? "text-[#0c1a3d]"
                    : "text-slate-300 hover:text-white")
                }
                style={
                  language === opt ? { backgroundColor: KHAKI } : undefined
                }
              >
                {opt === "en" ? "EN" : "ಕನ್ನಡ"}
              </button>
            ))}
          </div>

          <Link href="/login">
            <Button
              variant="outline"
              size="sm"
              className="border-white/20 bg-white/5 text-white hover:bg-white/10 hover:text-white"
            >
              <Lock className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
              {t.primaryCta}
            </Button>
          </Link>
        </div>
      </header>

      {/* Eyebrow */}
      <div className="relative z-10 mx-auto max-w-7xl px-6">
        <div
          className="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[10px] uppercase tracking-[0.2em]"
          style={{ borderColor: `${KHAKI}40`, color: KHAKI }}
        >
          <span className="h-1.5 w-1.5 animate-pulse rounded-full" style={{ background: KHAKI }} />
          {t.eyebrow}
        </div>
      </div>

      {/* Hero */}
      <section className="relative z-10 mx-auto max-w-7xl px-6 pb-16 pt-8">
        <div className="grid items-center gap-10 lg:grid-cols-[1.2fr_1fr]">
          <div>
            <h1 className="max-w-2xl text-balance text-4xl font-semibold leading-tight tracking-tight text-white sm:text-5xl lg:text-6xl">
              {t.heroTitle}
            </h1>
            <p className="mt-5 max-w-xl text-base text-slate-300 sm:text-lg">
              {t.heroSubtitle}
            </p>

            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link href="/login">
                <Button
                  size="lg"
                  className="h-12 px-6 text-base font-medium text-[#0c1a3d] hover:opacity-90"
                  style={{ backgroundColor: KHAKI }}
                >
                  <ShieldCheck className="mr-2 h-4 w-4" aria-hidden="true" />
                  {t.primaryCta}
                </Button>
              </Link>

              <Button
                onClick={handleGuestDemo}
                variant="outline"
                size="lg"
                className="h-12 border-white/20 bg-white/5 px-6 text-base text-white hover:bg-white/10 hover:text-white"
              >
                {t.secondaryCta}
                <ArrowRight className="ml-2 h-4 w-4" aria-hidden="true" />
              </Button>
            </div>

            {/* Stats strip */}
            <dl className="mt-10 grid max-w-xl grid-cols-3 gap-6 border-t border-white/10 pt-6">
              {[
                { v: t.stat1, l: t.stat1Label },
                { v: t.stat2, l: t.stat2Label },
                { v: t.stat3, l: t.stat3Label },
              ].map((s) => (
                <div key={s.l}>
                  <dt className="text-2xl font-semibold text-white sm:text-3xl" style={{ color: KHAKI }}>
                    {s.v}
                  </dt>
                  <dd className="mt-1 text-[11px] uppercase tracking-wider text-slate-400">
                    {s.l}
                  </dd>
                </div>
              ))}
            </dl>
          </div>

          {/* Visual: stylized shield + concentric rings */}
          <div className="relative hidden h-[420px] lg:block">
            <div className="absolute inset-0 flex items-center justify-center">
              <div
                className="absolute h-[420px] w-[420px] rounded-full border"
                style={{ borderColor: `${KHAKI}1a` }}
              />
              <div
                className="absolute h-[320px] w-[320px] rounded-full border"
                style={{ borderColor: `${KHAKI}26` }}
              />
              <div
                className="absolute h-[220px] w-[220px] rounded-full border"
                style={{ borderColor: `${KHAKI}40` }}
              />
              <SarvikShield className="relative h-44 w-44 drop-shadow-[0_24px_60px_rgba(200,169,100,0.35)]" />
            </div>

            {/* Floating capability tags */}
            <div
              className="absolute left-2 top-10 rounded-md border bg-white/5 px-3 py-2 text-xs text-slate-200 backdrop-blur"
              style={{ borderColor: `${KHAKI}40` }}
            >
              ಕನ್ನಡ · EN
            </div>
            <div
              className="absolute right-0 top-32 rounded-md border bg-white/5 px-3 py-2 text-xs text-slate-200 backdrop-blur"
              style={{ borderColor: `${KHAKI}40` }}
            >
              FIR · GD · Charge sheets
            </div>
            <div
              className="absolute bottom-12 left-6 rounded-md border bg-white/5 px-3 py-2 text-xs text-slate-200 backdrop-blur"
              style={{ borderColor: `${KHAKI}40` }}
            >
              India DC · IT Act 2008
            </div>
          </div>
        </div>
      </section>

      {/* Feature tiles */}
      <section className="relative z-10 mx-auto max-w-7xl px-6 pb-20">
        <h2 className="text-sm font-medium uppercase tracking-[0.22em]" style={{ color: KHAKI }}>
          {t.featuresTitle}
        </h2>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {features.map((f) => {
            const Icon = f.icon;
            return (
              <div
                key={f.title}
                className="group relative overflow-hidden rounded-xl border bg-white/[0.04] p-5 backdrop-blur transition-all hover:bg-white/[0.07]"
                style={{ borderColor: "rgba(255,255,255,0.08)" }}
              >
                <div
                  className="flex h-10 w-10 items-center justify-center rounded-md"
                  style={{ background: `${KHAKI}1a`, color: KHAKI }}
                >
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="mt-4 text-base font-semibold text-white">
                  {f.title}
                </h3>
                <p className="mt-1.5 text-sm leading-relaxed text-slate-300">
                  {f.desc}
                </p>
                <div
                  className="pointer-events-none absolute -bottom-12 -right-12 h-32 w-32 rounded-full blur-2xl opacity-0 transition-opacity group-hover:opacity-100"
                  style={{ background: `${KHAKI}26` }}
                />
              </div>
            );
          })}
        </div>
      </section>

      {/* Compliance strip */}
      <section className="relative z-10 mx-auto max-w-7xl px-6 pb-20">
        <div
          className="rounded-2xl border bg-white/[0.03] p-8 backdrop-blur"
          style={{ borderColor: "rgba(255,255,255,0.08)" }}
        >
          <div className="grid gap-8 lg:grid-cols-[1fr_1.4fr] lg:items-center">
            <div>
              <h2 className="text-2xl font-semibold text-white">
                {t.complianceTitle}
              </h2>
              <p className="mt-3 max-w-md text-sm text-slate-300">
                {language === "kn"
                  ? "ಪ್ರತಿ ಪ್ರಶ್ನೆ, ಪ್ರತಿ ಉತ್ತರ, ಪ್ರತಿ ರಫ್ತು — ಒಂದು ಬದಲಾಯಿಸಲಾಗದ ಆಡಿಟ್ ಲಾಗ್‌ನಲ್ಲಿ ದಾಖಲಿಸಲಾಗಿದೆ."
                  : "Every query, every answer, every export — written to a tamper-evident audit log."}
              </p>
            </div>
            <ul className="grid gap-3 sm:grid-cols-2">
              {t.complianceItems.map((item) => (
                <li
                  key={item}
                  className="flex items-start gap-2 text-sm text-slate-200"
                >
                  <ShieldCheck
                    className="mt-0.5 h-4 w-4 flex-shrink-0"
                    style={{ color: KHAKI }}
                    aria-hidden="true"
                  />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer
        className="relative z-10 border-t px-6 py-6"
        style={{ borderColor: "rgba(255,255,255,0.08)", background: NAVY_DEEP }}
      >
        <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-3 text-[11px] text-slate-400 sm:flex-row sm:items-center">
          <div className="flex flex-col gap-1">
            <span>{t.footerNote}</span>
            <span>{t.footerLine}</span>
          </div>
          <div className="flex items-center gap-4">
            <a
              href="https://github.com/"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-slate-300 hover:text-white"
            >
              <Github className="h-3.5 w-3.5" aria-hidden="true" />
              GitHub
            </a>
            <span className="hidden sm:inline">·</span>
            <span>India DC · asia-south1</span>
          </div>
        </div>
      </footer>
    </main>
  );
}
