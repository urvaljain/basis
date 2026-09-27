import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Basis — evidence-first site intelligence",
  description:
    "Answers a blocking project question from the governing regulation and the site's measured context — with the passage, the conflict, and what could not be read.",
};

const NAV = [
  { href: "/workspace", label: "Workspace" },
  { href: "/compare", label: "Compare" },
  { href: "/documents", label: "Documents" },
  { href: "/demo", label: "Demo" },
  { href: "/corpus", label: "Corpus" },
  { href: "/evaluation", label: "Evaluation" },
  { href: "/method", label: "Method" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <div className="flex min-h-screen flex-col">
          <header className="sticky top-0 z-40 border-b border-line bg-bg/95 backdrop-blur">
            <div className="mx-auto flex h-13 max-w-content items-center gap-4 px-4 sm:px-6">
              <Link
                href="/"
                className="flex shrink-0 items-baseline gap-2.5 whitespace-nowrap no-underline"
              >
                <span className="text-[15px] font-semibold tracking-tight text-ink">Basis</span>
                {/* Hidden until there is genuinely room. Seven nav items plus a tagline
                    wrapped the brand onto two lines on a narrow pane. */}
                <span className="hidden text-[11px] text-ink-4 xl:inline">
                  evidence before conclusions
                </span>
              </Link>

              <nav
                aria-label="Main"
                className="-mx-1 ml-auto flex min-w-0 items-center gap-0.5 overflow-x-auto px-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
              >
                {NAV.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className="whitespace-nowrap rounded px-2 py-1.5 text-[13px] text-ink-2 no-underline transition-colors hover:bg-hover hover:text-ink"
                  >
                    {item.label}
                  </Link>
                ))}
              </nav>
            </div>
          </header>

          <main className="flex-1">{children}</main>

          <footer className="border-t border-line px-4 py-5 sm:px-6">
            <div className="mx-auto flex max-w-content flex-col gap-2 text-[11px] leading-relaxed text-ink-4 sm:flex-row sm:items-start sm:justify-between">
              <p className="max-w-2xl">
                Basis reads a <strong className="font-medium text-ink-3">draft</strong> master
                plan and reports what it found. It does not certify compliance. Interpretation
                of development control regulations is a licensed professional activity, and
                local authority discretion may override the written rule.
              </p>
              <p className="whitespace-nowrap">
                Document © BDA · Spatial data © OpenStreetMap contributors (ODbL)
              </p>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
