"use client";

import * as React from "react";
import { useRouter, usePathname } from "next/navigation";
import { ShieldAlert, Loader2 } from "lucide-react";

import { useAuth } from "@/lib/catalyst-auth";
import { useKspStore, type Role } from "@/lib/store";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface AuthGateProps {
  children: React.ReactNode;
  /**
   * If provided, the current user must hold one of these roles. Anyone else
   * (including signed-in users with the wrong role) sees an "Access denied"
   * page rather than being silently redirected — clarity matters for the
   * RBAC story we're telling judges.
   */
  requireRoles?: Role[];
  /**
   * Where to redirect unauthenticated users. Defaults to /login with a
   * `next` query param so we can bounce them back after sign-in.
   * Next.js automatically prefixes the configured basePath (`/app`).
   */
  redirectTo?: string;
  /** Override the default Loading fallback. */
  fallback?: React.ReactNode;
  /**
   * Aliased prop kept for callers that prefer the more idiomatic name.
   * If both are supplied, `requiredRoles` wins.
   */
  requiredRoles?: Role[];
}

/**
 * Gates any page behind Catalyst Authentication + an optional role check.
 *
 * Used by:
 *   - /            (dashboard — any signed-in user)
 *   - /settings    (any signed-in user)
 *   - /demo/role-switch (any signed-in user; the page itself impersonates)
 *
 * Behavior:
 *   • While the auth state is hydrating from localStorage, render a spinner.
 *   • If no user → redirect to /login?next=<current path>.
 *   • If user but role isn't allowed → render a friendly Access Denied card
 *     showing the user's current role + the roles required. This is intentional
 *     UX, not a security boundary; the backend re-checks role claims on every
 *     Catalyst Function call.
 *   • On success, also mirrors the user into useKspStore so the rest of the
 *     dashboard (header role badge, audit log filter) stays in sync.
 */
export function AuthGate({
  children,
  requireRoles,
  requiredRoles,
  redirectTo = "/login",
  fallback,
}: AuthGateProps): React.ReactElement | null {
  const { user, loading, signOut } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const effectiveRoles = requiredRoles ?? requireRoles;

  const setRole = useKspStore((s) => s.setRole);
  const setSession = useKspStore((s) => s.setSession);

  // Keep the global store in sync with the auth session. This lets the
  // existing dashboard header read role from the store without knowing about
  // the auth lib.
  React.useEffect(() => {
    if (user) {
      setRole(user.role);
      setSession(user.id, user.id);
    } else if (!loading) {
      setRole(null);
      setSession(null, null);
    }
  }, [user, loading, setRole, setSession]);

  // Redirect unauthenticated users.
  React.useEffect(() => {
    if (loading) return;
    if (!user) {
      const next = encodeURIComponent(pathname ?? "/");
      router.replace(`${redirectTo}?next=${next}`);
    }
  }, [loading, user, pathname, redirectTo, router]);

  if (loading) {
    return (
      fallback ? (
        <>{fallback}</>
      ) : (
        <div
          className="flex min-h-screen items-center justify-center bg-background"
          role="status"
          aria-live="polite"
        >
          <div className="flex flex-col items-center gap-3 text-muted-foreground">
            <Loader2 className="h-6 w-6 animate-spin" aria-hidden="true" />
            <span className="text-sm">Verifying credentials…</span>
          </div>
        </div>
      )
    );
  }

  if (!user) {
    // Redirect is in flight; render nothing to avoid a flash of content.
    return null;
  }

  if (effectiveRoles && effectiveRoles.length > 0 && !effectiveRoles.includes(user.role)) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background px-4">
        <Card className="w-full max-w-md border-destructive/30">
          <CardHeader className="items-center text-center">
            <div className="mb-2 rounded-full bg-destructive/10 p-3">
              <ShieldAlert
                className="h-8 w-8 text-destructive"
                aria-hidden="true"
              />
            </div>
            <CardTitle>Access denied</CardTitle>
            <CardDescription>
              Your role does not have permission to view this page.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <dl className="grid grid-cols-[auto,1fr] gap-x-4 gap-y-1 rounded-md border bg-muted/30 p-3">
              <dt className="text-muted-foreground">Signed in as</dt>
              <dd className="font-medium">{user.name}</dd>
              <dt className="text-muted-foreground">Current role</dt>
              <dd className="font-mono text-xs uppercase">{user.role}</dd>
              <dt className="text-muted-foreground">Required role</dt>
              <dd className="font-mono text-xs uppercase">
                {(effectiveRoles ?? []).join(" / ")}
              </dd>
            </dl>
            <p className="text-xs text-muted-foreground">
              If you believe this is a mistake, contact your SHO or the SCRB
              administrator. Every access attempt is logged to the immutable
              audit trail (IT Act 2008 § 67C).
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => router.push("/")}
              >
                Back to home
              </Button>
              <Button
                variant="destructive"
                className="flex-1"
                onClick={async () => {
                  try {
                    localStorage.removeItem("sarvik-guest-session");
                  } catch {
                    // ignore
                  }
                  await signOut();
                  router.replace("/login");
                }}
              >
                Sign out
              </Button>
            </div>
          </CardContent>
        </Card>
      </main>
    );
  }

  return <>{children}</>;
}

export default AuthGate;
