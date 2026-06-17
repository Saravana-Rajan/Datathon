import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Sarvik — Investigator's Companion",
  description:
    "Conversational AI for Karnataka State Police investigators. Query, visualize, and forecast crime data by voice or text — Kannada-first, fully audited.",
  applicationName: "Sarvik",
  authors: [{ name: "Sarvik Team" }],
  keywords: [
    "Karnataka Police",
    "KSP",
    "Conversational AI",
    "Crime Analytics",
    "Kannada",
    "Investigator",
    "Datathon 2026",
  ],
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0b1220" },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning className={inter.variable}>
      <head>
        <script
          // Avoid theme flash on initial load
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('ksp-theme');var m=window.matchMedia('(prefers-color-scheme: dark)').matches;if(t==='dark'||(!t&&m)){document.documentElement.classList.add('dark');}}catch(e){}})();`,
          }}
        />
      </head>
      <body className="min-h-screen bg-background font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
