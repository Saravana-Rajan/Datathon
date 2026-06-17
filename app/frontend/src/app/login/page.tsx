"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ShieldCheck,
  Loader2,
  Eye,
  EyeOff,
  AlertCircle,
  Languages,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useAuth, type AuthError } from "@/lib/catalyst-auth";
import { useKspStore, type Language } from "@/lib/store";

// --------------------------------------------------------------------------
// Brand palette
// --------------------------------------------------------------------------
// KSP visual identity: navy + khaki, mirroring the actual Karnataka State
// Police uniform/insignia. We layer this on top of the shadcn tokens with
// inline gradients so the page reads as distinctly "KSP" the moment a judge
// loads /login.

const COPY: Record<
  Language,
  {
    title: string;
    subtitle: string;
    productName: string;
    eyebrow: string;
    welcome: string;
    welcomeBody: string;
    emailLabel: string;
    emailPlaceholder: string;
    passwordLabel: string;
    passwordPlaceholder: string;
    signIn: string;
    signInWorking: string;
    googleSignIn: string;
    orDivider: string;
    forgot: string;
    needHelp: string;
    demoHint: string;
    languageToggleAria: string;
    showPassword: string;
    hidePassword: string;
    invalidCreds: string;
    networkErr: string;
    footerCompliance: string;
    footerRegion: string;
    footerLine: string;
  }
> = {
  en: {
    title: "Sarvik",
    subtitle: "Karnataka Police Investigator AI",
    productName: "ಯಕ್ಷ — Karnataka Police Investigator AI",
    eyebrow: "Restricted system · Authorized officers only",
    welcome: "Sign in to continue",
    welcomeBody:
      "Use your KSP officer credentials. All sessions are logged to an immutable audit trail.",
    emailLabel: "Email",
    emailPlaceholder: "name@ksp.gov.in",
    passwordLabel: "Password",
    passwordPlaceholder: "Your KSP password",
    signIn: "Sign in",
    signInWorking: "Signing in…",
    googleSignIn: "Sign in with Google",
    orDivider: "OR",
    forgot: "Forgot password?",
    needHelp: "Need help? Contact your SHO.",
    demoHint:
      "Demo: suresh@ksp.gov.in · lakshmi@ksp.gov.in · mehta@ksp.gov.in (password: demo)",
    languageToggleAria: "Language",
    showPassword: "Show password",
    hidePassword: "Hide password",
    invalidCreds: "Email or password is incorrect.",
    networkErr: "Could not reach Catalyst Authentication. Try again.",
    footerCompliance: "IT Act 2008 compliant · DPDP Act 2023 ready",
    footerRegion: "Hosted on Zoho Catalyst (India DC) · Data residency: asia-south1",
    footerLine: "Property of Karnataka State Police. Unauthorized access is a crime.",
  },
  kn: {
    title: "ಯಕ್ಷ",
    subtitle: "ಕರ್ನಾಟಕ ಪೊಲೀಸ್ ತನಿಖಾಧಿಕಾರಿಗಳ ಸಹಾಯಕ",
    productName: "ಯಕ್ಷ — ಕರ್ನಾಟಕ ಪೊಲೀಸ್ ತನಿಖಾಧಿಕಾರಿಗಳ ಸಹಾಯಕ",
    eyebrow: "ನಿರ್ಬಂಧಿತ ವ್ಯವಸ್ಥೆ · ಅಧಿಕೃತ ಅಧಿಕಾರಿಗಳಿಗೆ ಮಾತ್ರ",
    welcome: "ಮುಂದುವರಿಯಲು ಸೈನ್ ಇನ್ ಮಾಡಿ",
    welcomeBody:
      "ನಿಮ್ಮ ಕೆಎಸ್‌ಪಿ ಅಧಿಕಾರಿ ಲಾಗಿನ್ ಬಳಸಿ. ಪ್ರತಿ ಸತ್ರವನ್ನು ಬದಲಾಯಿಸಲಾಗದ ಆಡಿಟ್ ಲಾಗ್‌ನಲ್ಲಿ ದಾಖಲಿಸಲಾಗುತ್ತದೆ.",
    emailLabel: "ಇಮೇಲ್",
    emailPlaceholder: "name@ksp.gov.in",
    passwordLabel: "ಪಾಸ್‌ವರ್ಡ್",
    passwordPlaceholder: "ನಿಮ್ಮ ಕೆಎಸ್‌ಪಿ ಪಾಸ್‌ವರ್ಡ್",
    signIn: "ಸೈನ್ ಇನ್",
    signInWorking: "ಸೈನ್ ಇನ್ ಆಗುತ್ತಿದೆ…",
    googleSignIn: "ಗೂಗಲ್‌ನೊಂದಿಗೆ ಸೈನ್ ಇನ್",
    orDivider: "ಅಥವಾ",
    forgot: "ಪಾಸ್‌ವರ್ಡ್ ಮರೆತಿರಾ?",
    needHelp: "ಸಹಾಯ ಬೇಕೇ? ನಿಮ್ಮ ಎಸ್‌ಎಚ್‌ಒ ಅವರನ್ನು ಸಂಪರ್ಕಿಸಿ.",
    demoHint:
      "ಡೆಮೋ: suresh@ksp.gov.in · lakshmi@ksp.gov.in · mehta@ksp.gov.in (ಪಾಸ್‌ವರ್ಡ್: demo)",
    languageToggleAria: "ಭಾಷೆ",
    showPassword: "ಪಾಸ್‌ವರ್ಡ್ ತೋರಿಸಿ",
    hidePassword: "ಪಾಸ್‌ವರ್ಡ್ ಮರೆಮಾಡಿ",
    invalidCreds: "ಇಮೇಲ್ ಅಥವಾ ಪಾಸ್‌ವರ್ಡ್ ತಪ್ಪಾಗಿದೆ.",
    networkErr: "Catalyst Authentication ಅನ್ನು ತಲುಪಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
    footerCompliance: "ಐಟಿ ಕಾಯ್ದೆ 2008 ಪಾಲನೆ · DPDP ಕಾಯ್ದೆ 2023 ಸಿದ್ಧ",
    footerRegion: "Zoho Catalyst (ಭಾರತ DC) · ಡೇಟಾ ಸ್ಥಳ: asia-south1",
    footerLine: "ಕರ್ನಾಟಕ ರಾಜ್ಯ ಪೊಲೀಸ್ ಆಸ್ತಿ. ಅನಧಿಕೃತ ಪ್ರವೇಶ ಶಿಕ್ಷಾರ್ಹ ಅಪರಾಧವಾಗಿದೆ.",
  },
};

// KSP shield SVG placeholder — stylized triskele-on-shield in khaki+navy.
// Inline so /login renders with zero asset dependencies during the demo.
function KspShield({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 64 64"
      role="img"
      aria-label="Karnataka State Police shield"
      className={className}
    >
      <defs>
        <linearGradient id="ksp-shield-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1e3a8a" />
          <stop offset="100%" stopColor="#0c1a3d" />
        </linearGradient>
        <linearGradient id="ksp-shield-trim" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#d4a857" />
          <stop offset="100%" stopColor="#b8860b" />
        </linearGradient>
      </defs>
      <path
        d="M32 2 L58 12 V32 C58 46 46 58 32 62 C18 58 6 46 6 32 V12 Z"
        fill="url(#ksp-shield-fill)"
        stroke="url(#ksp-shield-trim)"
        strokeWidth="2"
      />
      <path
        d="M32 14 L46 20 V32 C46 41 39 49 32 52 C25 49 18 41 18 32 V20 Z"
        fill="none"
        stroke="url(#ksp-shield-trim)"
        strokeWidth="1.2"
      />
      <text
        x="32"
        y="36"
        textAnchor="middle"
        fontFamily="serif"
        fontSize="14"
        fontWeight="700"
        fill="url(#ksp-shield-trim)"
      >
        ಯ
      </text>
      <text
        x="32"
        y="48"
        textAnchor="middle"
        fontFamily="sans-serif"
        fontSize="5"
        letterSpacing="1.5"
        fill="#d4a857"
      >
        KSP
      </text>
    </svg>
  );
}

function GoogleMark({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 18 18" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.81.54-1.85.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A8.997 8.997 0 0 0 9 18z"
      />
      <path
        fill="#FBBC05"
        d="M3.97 10.72A5.41 5.41 0 0 1 3.68 9c0-.6.1-1.18.29-1.72V4.95H.96A8.997 8.997 0 0 0 0 9c0 1.45.35 2.82.96 4.05l3.01-2.33z"
      />
      <path
        fill="#EA4335"
        d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0A8.997 8.997 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58z"
      />
    </svg>
  );
}

function LoginPageInner() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params?.get("next") || "/";

  const { user, loading, signIn, signInWithGoogle } = useAuth();

  // Pull the global language so the toggle persists across pages.
  const language = useKspStore((s) => s.language);
  const setLanguage = useKspStore((s) => s.setLanguage);
  const t = COPY[language];

  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [showPassword, setShowPassword] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);
  const [googleSubmitting, setGoogleSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // If we're already signed in (e.g. user typed /login by mistake), bounce
  // them to their intended destination.
  React.useEffect(() => {
    if (!loading && user) {
      router.replace(next);
    }
  }, [loading, user, router, next]);

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await signIn(email, password);
      router.replace(next);
    } catch (err) {
      const code = (err as AuthError).code;
      setError(code === "network" ? t.networkErr : t.invalidCreds);
    } finally {
      setSubmitting(false);
    }
  };

  const handleGoogle = async () => {
    setError(null);
    setGoogleSubmitting(true);
    try {
      await signInWithGoogle();
      router.replace(next);
    } catch (err) {
      const code = (err as AuthError).code;
      if (code !== "oauth_cancelled") {
        setError(t.networkErr);
      }
    } finally {
      setGoogleSubmitting(false);
    }
  };

  return (
    <main
      className="relative flex min-h-screen flex-col overflow-hidden bg-[#0c1a3d] text-slate-100"
      // Inline bg keeps the brand palette intact regardless of theme/dark-mode
      // overrides elsewhere in the app.
    >
      {/* Decorative background — radial khaki bloom + faint chakra ring */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
        <div className="absolute -left-32 -top-32 h-[480px] w-[480px] rounded-full bg-[#d4a857]/10 blur-3xl" />
        <div className="absolute -right-40 bottom-0 h-[520px] w-[520px] rounded-full bg-[#1e3a8a]/40 blur-3xl" />
        <div className="absolute left-1/2 top-1/2 h-[800px] w-[800px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-[#d4a857]/5" />
        <div className="absolute left-1/2 top-1/2 h-[560px] w-[560px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-[#d4a857]/10" />
      </div>

      {/* Top bar */}
      <header className="relative z-10 flex items-center justify-between px-6 py-4">
        <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-[#d4a857]/80">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#d4a857]" />
          {t.eyebrow}
        </div>

        <div
          className="flex items-center gap-1 rounded-md border border-white/10 bg-white/5 p-0.5 backdrop-blur"
          role="group"
          aria-label={t.languageToggleAria}
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
                  ? "bg-[#d4a857] text-[#0c1a3d]"
                  : "text-slate-300 hover:text-white")
              }
            >
              {opt === "en" ? "EN" : "ಕನ್ನಡ"}
            </button>
          ))}
        </div>
      </header>

      {/* Card */}
      <section className="relative z-10 flex flex-1 items-center justify-center px-4 py-6">
        <div className="grid w-full max-w-5xl items-center gap-8 lg:grid-cols-[1.05fr_1fr]">
          {/* Brand pane */}
          <div className="hidden flex-col gap-6 px-2 lg:flex">
            <div className="flex items-center gap-3">
              <KspShield className="h-14 w-14 drop-shadow-[0_8px_24px_rgba(212,168,87,0.25)]" />
              <div>
                <div className="text-3xl font-semibold tracking-tight">
                  {t.title}
                </div>
                <div className="text-xs uppercase tracking-[0.2em] text-[#d4a857]">
                  {t.subtitle}
                </div>
              </div>
            </div>

            <h1 className="max-w-md text-balance text-3xl font-semibold leading-tight text-white">
              {language === "kn" ? (
                <>
                  ಕರ್ನಾಟಕದ <span className="text-[#d4a857]">1,100+</span>{" "}
                  ಪೊಲೀಸ್ ಠಾಣೆಗಳ ಅಪರಾಧ ಮಾಹಿತಿ — ಒಂದು ಸಂಭಾಷಣೆಯಲ್ಲಿ.
                </>
              ) : (
                <>
                  Crime data from{" "}
                  <span className="text-[#d4a857]">1,100+ stations</span>{" "}
                  across Karnataka — in one conversation.
                </>
              )}
            </h1>

            <ul className="space-y-2 text-sm text-slate-300">
              {(language === "kn"
                ? [
                    "ಕನ್ನಡ ಮತ್ತು ಇಂಗ್ಲಿಷ್ ಧ್ವನಿ + ಪಠ್ಯ",
                    "ಅಪರಾಧಿಗಳ ಜಾಲ ದೃಶ್ಯೀಕರಣ",
                    "ಭವಿಷ್ಯವಾಣಿ + ವಿವರಿಸಬಹುದಾದ AI",
                    "ಭಾರತದಲ್ಲಿ ಮಾತ್ರ ಡೇಟಾ — IT ಕಾಯ್ದೆ 2008",
                  ]
                : [
                    "Kannada + English voice and text",
                    "Criminal network visualization",
                    "Predictive analytics with full explainability",
                    "India-only data residency — IT Act 2008",
                  ]
              ).map((line) => (
                <li key={line} className="flex items-start gap-2">
                  <span className="mt-1.5 h-1 w-3 rounded-full bg-[#d4a857]" />
                  {line}
                </li>
              ))}
            </ul>
          </div>

          {/* Sign-in card */}
          <Card className="border-white/10 bg-white/95 text-slate-900 shadow-2xl backdrop-blur dark:bg-white/95">
            <CardHeader className="space-y-3">
              <div className="flex items-center gap-3 lg:hidden">
                <KspShield className="h-10 w-10" />
                <div>
                  <div className="text-xl font-semibold leading-tight">
                    {t.title}
                  </div>
                  <div className="text-[10px] uppercase tracking-[0.18em] text-[#1e3a8a]">
                    {t.subtitle}
                  </div>
                </div>
              </div>

              <div className="space-y-1">
                <CardTitle className="text-xl text-slate-900">
                  {t.welcome}
                </CardTitle>
                <CardDescription className="text-slate-600">
                  {t.welcomeBody}
                </CardDescription>
              </div>
            </CardHeader>

            <CardContent className="space-y-4">
              <Button
                type="button"
                variant="outline"
                onClick={handleGoogle}
                disabled={googleSubmitting || submitting}
                className="w-full border-slate-300 bg-white text-slate-800 hover:bg-slate-50"
              >
                {googleSubmitting ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <GoogleMark className="mr-2 h-4 w-4" />
                )}
                {t.googleSignIn}
              </Button>

              <div
                className="relative my-1 flex items-center text-[10px] uppercase tracking-[0.2em] text-slate-400"
                aria-hidden="true"
              >
                <div className="h-px flex-1 bg-slate-200" />
                <span className="px-3">{t.orDivider}</span>
                <div className="h-px flex-1 bg-slate-200" />
              </div>

              <form className="space-y-4" onSubmit={handleEmailSubmit} noValidate>
                <div className="space-y-1.5">
                  <label
                    htmlFor="login-email"
                    className="text-xs font-medium text-slate-700"
                  >
                    {t.emailLabel}
                  </label>
                  <Input
                    id="login-email"
                    type="email"
                    autoComplete="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder={t.emailPlaceholder}
                    className="bg-white text-slate-900 placeholder:text-slate-400"
                    aria-invalid={error ? "true" : "false"}
                    aria-describedby={error ? "login-error" : undefined}
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label
                      htmlFor="login-password"
                      className="text-xs font-medium text-slate-700"
                    >
                      {t.passwordLabel}
                    </label>
                    <a
                      href="#"
                      className="text-xs text-[#1e3a8a] hover:underline"
                      onClick={(e) => e.preventDefault()}
                    >
                      {t.forgot}
                    </a>
                  </div>
                  <div className="relative">
                    <Input
                      id="login-password"
                      type={showPassword ? "text" : "password"}
                      autoComplete="current-password"
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder={t.passwordPlaceholder}
                      className="bg-white pr-10 text-slate-900 placeholder:text-slate-400"
                      aria-invalid={error ? "true" : "false"}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                      aria-label={showPassword ? t.hidePassword : t.showPassword}
                      className="absolute inset-y-0 right-0 flex items-center px-3 text-slate-400 hover:text-slate-700"
                    >
                      {showPassword ? (
                        <EyeOff className="h-4 w-4" aria-hidden="true" />
                      ) : (
                        <Eye className="h-4 w-4" aria-hidden="true" />
                      )}
                    </button>
                  </div>
                </div>

                {error && (
                  <div
                    id="login-error"
                    role="alert"
                    className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-2.5 text-xs text-red-700"
                  >
                    <AlertCircle
                      className="mt-0.5 h-3.5 w-3.5 flex-shrink-0"
                      aria-hidden="true"
                    />
                    <span>{error}</span>
                  </div>
                )}

                <Button
                  type="submit"
                  disabled={submitting || googleSubmitting}
                  className="h-11 w-full bg-[#1e3a8a] text-white hover:bg-[#162c6b]"
                >
                  {submitting ? (
                    <>
                      <Loader2
                        className="mr-2 h-4 w-4 animate-spin"
                        aria-hidden="true"
                      />
                      {t.signInWorking}
                    </>
                  ) : (
                    <span className="flex items-center">
                      <ShieldCheck
                        className="mr-2 h-4 w-4"
                        aria-hidden="true"
                      />
                      {t.signIn}
                    </span>
                  )}
                </Button>
              </form>

              <p className="text-[11px] leading-relaxed text-slate-500">
                {t.demoHint}
              </p>
            </CardContent>

            <CardFooter className="flex flex-col items-start gap-1.5 border-t pt-4 text-[11px] text-slate-500">
              <span>{t.needHelp}</span>
              <span>{t.footerCompliance}</span>
            </CardFooter>
          </Card>
        </div>
      </section>

      {/* Bottom strip */}
      <footer className="relative z-10 border-t border-white/5 px-6 py-3 text-center text-[10px] text-slate-400">
        {t.footerRegion} · {t.footerLine}
      </footer>
    </main>
  );
}

// Wrap in Suspense so useSearchParams() doesn't break static export.
export default function LoginPage() {
  return (
    <React.Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center bg-[#0c1a3d] text-slate-100">
          <Loader2 className="h-6 w-6 animate-spin text-[#d4a857]" aria-hidden="true" />
        </main>
      }
    >
      <LoginPageInner />
    </React.Suspense>
  );
}
