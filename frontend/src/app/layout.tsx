import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Email Engine",
  description: "AI-powered email intelligence dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-surface text-zinc-100 font-sans antialiased min-h-screen">
        <div className="flex h-screen">
          {/* Sidebar */}
          <nav className="w-56 bg-surface-raised border-r border-surface-border flex flex-col shrink-0">
            <div className="p-4 border-b border-surface-border">
              <h1 className="text-lg font-semibold flex items-center gap-2">
                <span className="text-accent">📧</span> Email Engine
              </h1>
              <p className="text-xs text-zinc-500 mt-1">AI-Powered Intelligence</p>
            </div>
            <div className="flex-1 p-2 space-y-0.5">
              <NavLink href="/" label="Dashboard" icon="⚡" />
              <NavLink href="/inbox" label="Inbox" icon="📥" />
              <NavLink href="/links" label="Links" icon="🔗" />
              <NavLink href="/senders" label="Senders" icon="👤" />
              <NavLink href="/proposals" label="Proposals" icon="🧹" />
            </div>
            <div className="p-3 border-t border-surface-border">
              <div id="sync-indicator" className="text-xs text-zinc-500">
                Loading...
              </div>
            </div>
          </nav>

          {/* Main content */}
          <main className="flex-1 overflow-auto">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}

function NavLink({ href, label, icon }: { href: string; label: string; icon: string }) {
  return (
    <a
      href={href}
      className="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm text-zinc-400 hover:text-zinc-100 hover:bg-surface-overlay transition-colors"
    >
      <span className="text-base">{icon}</span>
      {label}
    </a>
  );
}
