"use client";

import { useEffect, useState } from "react";
import { api, ExtractedLink } from "@/lib/api";

export default function LinksPage() {
  const [links, setLinks] = useState<ExtractedLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    loadLinks();
  }, [filter]);

  async function loadLinks() {
    setLoading(true);
    try {
      const params: any = { limit: 100 };
      if (filter !== "all") params.pipeline_status = filter;
      const data = await api.listLinks(params);
      setLinks(data);
    } catch (err) {
      console.error("Failed to load links:", err);
    } finally {
      setLoading(false);
    }
  }

  const typeColors: Record<string, string> = {
    article: "text-accent",
    github: "text-zinc-300",
    arxiv: "text-emerald-400",
    video: "text-rose-400",
    tool: "text-amber-400",
    docs: "text-cyan-400",
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Extracted Links</h2>
          <p className="text-sm text-zinc-500 mt-1">
            URLs extracted from emails, scored by AI for relevance.
          </p>
        </div>
        <div className="flex gap-1 bg-surface-raised rounded-md p-0.5 border border-surface-border">
          {["all", "pending", "queued", "extracted", "skipped"].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1 text-xs rounded capitalize ${
                filter === f
                  ? "bg-accent text-white"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="text-zinc-500 text-sm">Loading...</div>
      ) : links.length === 0 ? (
        <div className="bg-surface-raised rounded-lg border border-surface-border p-8 text-center">
          <p className="text-zinc-400">No links found for this filter.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {links.map((link) => (
            <div
              key={link.id}
              className="bg-surface-raised rounded-lg border border-surface-border p-4 flex items-center justify-between gap-4"
            >
              <div className="min-w-0 flex-1">
                <a
                  href={link.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-accent hover:underline truncate block"
                >
                  {link.url}
                </a>
                <div className="flex items-center gap-3 mt-1.5 text-xs text-zinc-500">
                  <span className="font-mono">{link.domain}</span>
                  {link.link_type && (
                    <span className={`capitalize ${typeColors[link.link_type] || "text-zinc-400"}`}>
                      {link.link_type}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                {link.relevance_score != null && (
                  <div className="text-right">
                    <div className="text-xs text-zinc-500">Relevance</div>
                    <div
                      className={`text-sm font-mono font-medium ${
                        link.relevance_score >= 0.7
                          ? "text-success"
                          : link.relevance_score >= 0.4
                          ? "text-warning"
                          : "text-zinc-500"
                      }`}
                    >
                      {link.relevance_score.toFixed(2)}
                    </div>
                  </div>
                )}
                <span
                  className={`px-2 py-0.5 rounded text-xs ${
                    link.pipeline_status === "pending"
                      ? "bg-warning/20 text-warning"
                      : link.pipeline_status === "queued"
                      ? "bg-accent/20 text-accent"
                      : link.pipeline_status === "extracted"
                      ? "bg-success/20 text-success"
                      : "bg-zinc-700 text-zinc-400"
                  }`}
                >
                  {link.pipeline_status}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
