import type { Metadata, Viewport } from "next";
import "./globals.css";
import PageView from "../components/PageView";
import { LocaleProvider } from "../lib/i18n";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://notesbang.com";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "NotesBang — score and rewrite your copy",
    template: "%s · NotesBang",
  },
  description:
    "Paste or upload your copy and get a platform-aware scorecard with evidence, plus a full rewrite and title/hook options.",
  applicationName: "NotesBang",
  openGraph: {
    type: "website",
    url: SITE_URL,
    siteName: "NotesBang",
    title: "NotesBang — score and rewrite your copy",
    description:
      "A five-expert committee scores your copy across six dimensions and hands you a rewrite you can publish.",
  },
  twitter: {
    card: "summary_large_image",
    title: "NotesBang — score and rewrite your copy",
    description:
      "A five-expert committee scores your copy across six dimensions and hands you a rewrite you can publish.",
  },
};

export const viewport: Viewport = {
  themeColor: "#ffffff",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-full focus:bg-zinc-900 focus:px-4 focus:py-2 focus:text-sm focus:text-white"
        >
          Skip to content
        </a>
        <LocaleProvider>{children}</LocaleProvider>
        <PageView />
      </body>
    </html>
  );
}
