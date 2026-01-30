"use client";

import { useEffect, useState } from "react";
import { api, SyncStatus, ProcessingStats } from "@/lib/api";

export default function Dashboard() {
  const [sync, setSync] = useState<SyncStatus | null>(null);
  const [stats, setStats] = useState<ProcessingStats | null>(null);
  const [emailStats, setEmailStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [processing, setProcessing] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    try {
      const [s, p, e] = await Promise.all([
        api.syncStatus(),
        api.processingStats(),
        api.emailStats(),
      ]);
      setSync(s);
      setStats(p);
      setEmailStats(e);
    } catch (err) {
      console.error("Failed to load data:", err);
    } finally {
      setLoading(false);
    }
  }

  async function handleSync() {
    setSyncing(true);
    try {
      if (!sync?.connected) await api.syncConnect();
      await api.syncRun();
      await loadData();
    } catch (err) {
      console.error("Sync failed:", err);
    } finally {
      setSyncing(false);
    }
  }

  async function handleProcess() {
    setProcessing(true);
    try {
      await api.processEmails(50);
      await loadData();
    } catch (err) {
      console.error("Processing failed:", err);
    } finally {
      setProcessing(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-zinc-500 text-sm">Loading dashboard...</div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Dashboard</h2>
          <p className="text-sm text-zinc-500 mt-1">
            Email intelligence overview
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleSync}
            disabled={syncing}
            className="px-4 py-2 bg-accent hover:bg-accent-hover disabled:opacity-50 rounded-md text-sm font-medium transition-colors"
          >
            {syncing ? "Syncing..." : "Sync Inbox"}
          </button>
          <button
            onClick={handleProcess}
            disabled={processing}
            className="px-4 py-2 bg-surface-overlay hover:bg-surface-border rounded-md text-sm font-medium transition-colors"
          >
            {processing ? "Processing..." : "Classify Emails"}
          </button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Total Emails"
          value={stats?.total_emails ?? 0}
          color="text-zinc-100"
        />
        <StatCard
          label="Classified"
          value={stats?.classified ?? 0}
          sub={stats ? `${Math.round((stats.classified / Math.max(stats.total_emails, 1)) * 100)}%` : undefined}
          color="text-success"
        />
        <StatCard
          label="Unclassified"
          value={stats?.unclassified ?? 0}
          color="text-warning"
        />
        <StatCard
          label="Links Found"
          value={stats?.total_links ?? 0}
          sub={stats ? `${stats.pending_links} pending` : undefined}
          color="text-accent"
        />
      </div>

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Connection Status */}
        <div className="bg-surface-raised rounded-lg border border-surface-border p-5">
          <h3 className="text-sm font-medium text-zinc-400 mb-4">IMAP Status</h3>
          <div className="space-y-3">
            <StatusRow
              label="Connection"
              value={sync?.connected ? "Connected" : "Disconnected"}
              ok={sync?.connected}
            />
            <StatusRow
              label="Syncing"
              value={sync?.syncing ? "In progress" : "Idle"}
              ok={!sync?.syncing}
            />
            {sync?.stats?.sync_states?.map((s) => (
              <StatusRow
                key={s.folder}
                label={s.folder}
                value={`${s.total_synced} synced`}
                sub={s.last_sync ? `Last: ${new Date(s.last_sync).toLocaleString()}` : "Never"}
                ok={true}
              />
            ))}
            {sync?.last_error && (
              <div className="text-xs text-danger mt-2 p-2 bg-danger/10 rounded">
                {sync.last_error}
              </div>
            )}
          </div>
        </div>

        {/* Categories */}
        <div className="bg-surface-raised rounded-lg border border-surface-border p-5">
          <h3 className="text-sm font-medium text-zinc-400 mb-4">Categories</h3>
          {stats?.by_category && Object.keys(stats.by_category).length > 0 ? (
            <div className="space-y-2">
              {Object.entries(stats.by_category)
                .sort(([, a], [, b]) => b - a)
                .map(([cat, count]) => (
                  <CategoryBar
                    key={cat}
                    category={cat}
                    count={count}
                    total={stats.classified}
                  />
                ))}
            </div>
          ) : (
            <p className="text-sm text-zinc-500">
              No classifications yet. Click &quot;Classify Emails&quot; to start.
            </p>
          )}
        </div>
      </div>

      {/* Top Senders */}
      {emailStats?.top_senders?.length > 0 && (
        <div className="bg-surface-raised rounded-lg border border-surface-border p-5">
          <h3 className="text-sm font-medium text-zinc-400 mb-4">Top Senders</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {emailStats.top_senders.slice(0, 10).map((s: any) => (
              <div
                key={s.address}
                className="flex items-center justify-between py-1.5 px-3 rounded bg-surface-overlay/50"
              >
                <span className="text-sm text-zinc-300 truncate">{s.address}</span>
                <span className="text-xs text-zinc-500 font-mono ml-2 shrink-0">
                  {s.count}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  sub,
  color = "text-zinc-100",
}: {
  label: string;
  value: number;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="bg-surface-raised rounded-lg border border-surface-border p-4">
      <div className="text-xs text-zinc-500 font-medium uppercase tracking-wider">
        {label}
      </div>
      <div className={`text-2xl font-semibold mt-1 font-mono ${color}`}>
        {value.toLocaleString()}
      </div>
      {sub && <div className="text-xs text-zinc-500 mt-0.5">{sub}</div>}
    </div>
  );
}

function StatusRow({
  label,
  value,
  sub,
  ok,
}: {
  label: string;
  value: string;
  sub?: string;
  ok?: boolean;
}) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <div className="text-sm text-zinc-300">{label}</div>
        {sub && <div className="text-xs text-zinc-500">{sub}</div>}
      </div>
      <div className="flex items-center gap-2">
        <span className="text-sm text-zinc-400">{value}</span>
        <span
          className={`w-2 h-2 rounded-full ${ok ? "bg-success" : "bg-danger"}`}
        />
      </div>
    </div>
  );
}

function CategoryBar({
  category,
  count,
  total,
}: {
  category: string;
  count: number;
  total: number;
}) {
  const pct = total > 0 ? (count / total) * 100 : 0;
  const colors: Record<string, string> = {
    newsletter: "bg-accent",
    personal: "bg-success",
    transactional: "bg-zinc-500",
    notification: "bg-yellow-500",
    marketing: "bg-orange-500",
    actionable: "bg-emerald-400",
    noise: "bg-zinc-700",
  };

  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-zinc-300 capitalize">{category}</span>
        <span className="text-zinc-500 font-mono">{count}</span>
      </div>
      <div className="h-1.5 bg-surface-overlay rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${colors[category] || "bg-zinc-600"}`}
          style={{ width: `${Math.max(pct, 2)}%` }}
        />
      </div>
    </div>
  );
}
