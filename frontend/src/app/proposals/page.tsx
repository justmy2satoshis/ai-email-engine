"use client";

import { useEffect, useState } from "react";
import { api, Proposal } from "@/lib/api";

export default function ProposalsPage() {
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    loadProposals();
  }, []);

  async function loadProposals() {
    try {
      const data = await api.listProposals();
      setProposals(data);
    } catch (err) {
      console.error("Failed to load proposals:", err);
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerate() {
    setGenerating(true);
    try {
      await api.generateProposals();
      await loadProposals();
    } catch (err) {
      console.error("Generate failed:", err);
    } finally {
      setGenerating(false);
    }
  }

  async function handleApprove(id: number) {
    await api.approveProposal(id);
    await loadProposals();
  }

  async function handleReject(id: number) {
    await api.rejectProposal(id);
    await loadProposals();
  }

  const statusColors: Record<string, string> = {
    pending: "bg-warning/20 text-warning",
    approved: "bg-success/20 text-success",
    rejected: "bg-danger/20 text-danger",
    executed: "bg-accent/20 text-accent",
  };

  const typeIcons: Record<string, string> = {
    unsubscribe: "🗑️",
    archive: "📦",
    extraction: "🔗",
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Cleanup Proposals</h2>
          <p className="text-sm text-zinc-500 mt-1">
            AI-generated inbox cleanup actions. Review and approve.
          </p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="px-4 py-2 bg-accent hover:bg-accent-hover disabled:opacity-50 rounded-md text-sm font-medium"
        >
          {generating ? "Generating..." : "Generate Proposals"}
        </button>
      </div>

      {loading ? (
        <div className="text-zinc-500 text-sm">Loading...</div>
      ) : proposals.length === 0 ? (
        <div className="bg-surface-raised rounded-lg border border-surface-border p-8 text-center">
          <p className="text-zinc-400">No proposals yet.</p>
          <p className="text-zinc-500 text-sm mt-1">
            Classify some emails first, then generate proposals.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {proposals.map((p) => (
            <div
              key={p.id}
              className="bg-surface-raised rounded-lg border border-surface-border p-5"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-3">
                  <span className="text-2xl">{typeIcons[p.type] || "📋"}</span>
                  <div>
                    <h3 className="font-medium text-zinc-100">{p.title}</h3>
                    <p className="text-sm text-zinc-400 mt-1">{p.description}</p>
                    <div className="flex items-center gap-3 mt-2 text-xs text-zinc-500">
                      <span>{p.affected_count} affected</span>
                      <span>•</span>
                      <span>
                        {p.created_at
                          ? new Date(p.created_at).toLocaleDateString()
                          : ""}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0 ml-4">
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium ${
                      statusColors[p.status] || "bg-zinc-700 text-zinc-400"
                    }`}
                  >
                    {p.status}
                  </span>
                  {p.status === "pending" && (
                    <>
                      <button
                        onClick={() => handleApprove(p.id)}
                        className="px-3 py-1 bg-success/20 text-success hover:bg-success/30 rounded text-xs font-medium"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => handleReject(p.id)}
                        className="px-3 py-1 bg-danger/20 text-danger hover:bg-danger/30 rounded text-xs font-medium"
                      >
                        Reject
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
