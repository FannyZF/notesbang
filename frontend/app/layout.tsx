import type { Metadata } from "next";
import "./globals.css";
import PageView from "../components/PageView";
import { LocaleProvider } from "../lib/i18n";

export const metadata: Metadata = {
  title: "NotesBang — score and rewrite your copy",
  description:
    "Paste or upload your copy and get a platform-aware scorecard with evidence, plus a full rewrite and title/hook options.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">
        <LocaleProvider>{children}</LocaleProvider>
        <PageView />
      </body>
    </html>
  );
}
