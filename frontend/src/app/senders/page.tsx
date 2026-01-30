"use client";

import { useEffect, useState } from "react";
import { api, SenderProfile } from "@/lib/api";

export default function SendersPage() {
  const [senders, setSenders] = useState<SenderProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState("total_emails");

  useEffect(() => {
    loadSenders();
  }, [sortBy]);

  async function loadSenders() {
    setLoading(true);
    try {
      const data = await api.listSenders({ sort_by: sortBy });
      setSenders(data);
    } catch (err) {
      console.error("Failed to load senders:", err);
    } finally {
      setLoading(false);
    }
  }

  const typeColors: Record<string, string> = {
    newsletter: "bg-accent/20 text-accent",
    service: "bg-zinc-700 text-zinc-300",
    person: "bg-success/20 text-success",
    marketing: "bg-warning/20 text-warning",
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Sender Intelligence</h2>
          <p className="text-sm text-zinc-500 mt-1">
            Who emails you, how often, and whether you care.
          </p>
        </div>
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="bg-surface-overlay border border-surface-border rounded-md px-3 py-2 text-sm text-zinc-300"
        >
          <option value="total_emails">Most emails</option>
          <option value="relevance_score">Most relevant</option>
          <option value="last_seen">Most recent</option>
        </select>
      </div>

      {loading ? (
        <div className="text-zinc-500 text-sm">Loading...</div>
      ) : senders.length === 0 ? (
        <div className="bg-surface-raised rounded-lg border border-surface-border p-8 text-center">
          <p className="text-zinc-400">No sender profiles yet.</p>
          <p className="text-zinc-500 text-sm mt-1">
            Classify emails to build sender intelligence.
          </p>
        </div>
      ) : (
        <div className="bg-surface-raised rounded-lg border border-surface-border overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-border text-xs text-zinc-500 uppercase tracking-wider">
                <th className="text-left p-3 font-medium">Sender</th>
                <th className="text-left p-3 font-medium">Type</th>
                <th className="text-right p-3 font-medium">Emails</th>
                <th className="text-right p-3 font-medium">Relevance</th>
                <th className="text-right p-3 font-medium">Last Seen</th>
              </tr>
            </thead>
            <tbody>
              {senders.map((s) => (
                <tr
                  key={s.id}
                  className="border-b border-surface-border/50 hover:bg-surface-overlay/50"
                >
                  <td className="p-3">
                    <div className="text-sm text-zinc-200">
                      {s.display_name || s.email_address}
                    </div>
                    {s.display_name && (
                      <div className="text-xs text-zinc-500">{s.email_address}</div>
                    )}
                  </td>
                  <td className="p-3">
                    <span
                      className={`px-2 py-0.5 rounded text-xs ${
                        typeColors[s.sender_type || ""] || "bg-zinc-700 text-zinc-400"
                      }`}
                    >
                      {s.sender_type || "unknown"}
                    </span>
                  </td>
                  <td className="p-3 text-right font-mono text-sm text-zinc-300">
                    {s.total_emails}
                  </td>
                  <td className="p-3 text-right">
                    {s.relevance_score != null ? (
                      <span
                        className={`font-mono text-sm ${
                          s.relevance_score >= 0.7
                            ? "text-success"
                            : s.relevance_score >= 0.4
                            ? "text-warning"
                            : "text-zinc-500"
                        }`}
                      >
                        {s.relevance_score.toFixed(2)}
                      </span>
                    ) : (
                      <span className="text-zinc-600 text-xs">—</span>
                    )}
                  </td>
                  <td className="p-3 text-right text-xs text-zinc-500">
                    {s.last_seen
                      ? new Date(s.last_seen).toLocaleDateString()
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
