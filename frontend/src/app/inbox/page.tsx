"use client";

import { useEffect, useState } from "react";
import { api, EmailSummary, EmailDetail } from "@/lib/api";

export default function InboxPage() {
  const [emails, setEmails] = useState<EmailSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<EmailDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadEmails();
  }, [page]);

  async function loadEmails() {
    setLoading(true);
    try {
      const res = await api.listEmails({
        page,
        page_size: 50,
        search: search || undefined,
      });
      setEmails(res.emails);
      setTotal(res.total);
    } catch (err) {
      console.error("Failed to load emails:", err);
    } finally {
      setLoading(false);
    }
  }

  async function openEmail(id: number) {
    try {
      const detail = await api.getEmail(id);
      setSelected(detail);
    } catch (err) {
      console.error("Failed to load email:", err);
    }
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    loadEmails();
  }

  const totalPages = Math.ceil(total / 50);

  return (
    <div className="flex h-full">
      {/* Email List */}
      <div className={`${selected ? "w-1/2" : "w-full"} border-r border-surface-border flex flex-col`}>
        {/* Search bar */}
        <div className="p-4 border-b border-surface-border">
          <form onSubmit={handleSearch} className="flex gap-2">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search emails..."
              className="flex-1 bg-surface-overlay border border-surface-border rounded-md px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-accent"
            />
            <button
              type="submit"
              className="px-4 py-2 bg-accent hover:bg-accent-hover rounded-md text-sm font-medium"
            >
              Search
            </button>
          </form>
          <div className="text-xs text-zinc-500 mt-2">
            {total.toLocaleString()} emails · Page {page} of {totalPages}
          </div>
        </div>

        {/* Email list */}
        <div className="flex-1 overflow-auto">
          {loading ? (
            <div className="p-8 text-center text-zinc-500 text-sm">Loading...</div>
          ) : emails.length === 0 ? (
            <div className="p-8 text-center text-zinc-500 text-sm">No emails found</div>
          ) : (
            emails.map((email) => (
              <div
                key={email.id}
                onClick={() => openEmail(email.id)}
                className={`px-4 py-3 border-b border-surface-border cursor-pointer transition-colors
                  ${selected?.id === email.id ? "bg-accent/10 border-l-2 border-l-accent" : "hover:bg-surface-overlay"}
                  ${!email.is_read ? "bg-surface-raised/50" : ""}`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-sm truncate ${!email.is_read ? "font-medium text-zinc-100" : "text-zinc-400"}`}>
                    {email.from_name || email.from_address || "Unknown"}
                  </span>
                  <span className="text-xs text-zinc-500 shrink-0 ml-2 font-mono">
                    {email.date_sent
                      ? new Date(email.date_sent).toLocaleDateString()
                      : ""}
                  </span>
                </div>
                <div className="text-sm text-zinc-300 truncate">
                  {email.subject || "(no subject)"}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="p-3 border-t border-surface-border flex items-center justify-center gap-2">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page <= 1}
              className="px-3 py-1 text-sm bg-surface-overlay rounded disabled:opacity-30 hover:bg-surface-border"
            >
              ← Prev
            </button>
            <span className="text-xs text-zinc-500">
              {page} / {totalPages}
            </span>
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages}
              className="px-3 py-1 text-sm bg-surface-overlay rounded disabled:opacity-30 hover:bg-surface-border"
            >
              Next →
            </button>
          </div>
        )}
      </div>

      {/* Email Detail */}
      {selected && (
        <div className="w-1/2 flex flex-col overflow-auto">
          <div className="p-4 border-b border-surface-border flex items-center justify-between">
            <h3 className="text-lg font-medium truncate pr-4">
              {selected.subject || "(no subject)"}
            </h3>
            <button
              onClick={() => setSelected(null)}
              className="text-zinc-500 hover:text-zinc-300 text-sm shrink-0"
            >
              ✕ Close
            </button>
          </div>
          <div className="p-4 border-b border-surface-border space-y-1 text-sm">
            <div>
              <span className="text-zinc-500">From:</span>{" "}
              <span className="text-zinc-200">
                {selected.from_name && `${selected.from_name} `}
                &lt;{selected.from_address}&gt;
              </span>
            </div>
            {selected.date_sent && (
              <div>
                <span className="text-zinc-500">Date:</span>{" "}
                <span className="text-zinc-300">
                  {new Date(selected.date_sent).toLocaleString()}
                </span>
              </div>
            )}
          </div>
          <div className="flex-1 p-4 overflow-auto">
            {selected.body_html ? (
              <iframe
                srcDoc={selected.body_html}
                className="w-full h-full border-0 bg-white rounded"
                sandbox="allow-same-origin"
                title="Email content"
              />
            ) : (
              <pre className="text-sm text-zinc-300 whitespace-pre-wrap font-mono">
                {selected.body_text || "(empty)"}
              </pre>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
