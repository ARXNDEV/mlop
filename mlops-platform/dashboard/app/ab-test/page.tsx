"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import * as Dialog from "@radix-ui/react-dialog";
import clsx from "clsx";
import { Trophy } from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import MetricCard from "@/components/MetricCard";
import {
  fetchABHistory,
  fetchABTestSummary,
  resetABTest,
  updateABSplit
} from "@/lib/api";
import type { ABHistory, ABTestSummary } from "@/lib/types";

type HistoryPoint = { hour: string; v1: number; v2: number };

function buildHistory(history: ABHistory | undefined): HistoryPoint[] {
  if (!history) return [];
  return history.v1.map((p, idx) => ({
    hour: p.hour,
    v1: p.count,
    v2: history.v2[idx]?.count ?? 0
  }));
}

function winnerFromSummary(v1: ABTestSummary, v2: ABTestSummary): { winner: "v1" | "v2" | "inconclusive"; p: number | null } {
  const p = v1.p_value ?? v2.p_value ?? null;
  if (p == null || v1.accuracy == null || v2.accuracy == null) {
    return { winner: "inconclusive", p };
  }
  if (p >= 0.05) return { winner: "inconclusive", p };
  return { winner: v2.accuracy > v1.accuracy ? "v2" : "v1", p };
}

/** A/B test page (stats, significance, split control, and request history). */
export default function ABTestPage() {
  const qc = useQueryClient();
  const [split, setSplit] = useState<number>(20);
  const [confirmOpen, setConfirmOpen] = useState<boolean>(false);

  const abQ = useQuery({
    queryKey: ["ab-summary"],
    queryFn: fetchABTestSummary,
    refetchInterval: 30_000
  });

  const historyQ = useQuery({
    queryKey: ["ab-history"],
    queryFn: fetchABHistory,
    refetchInterval: 30_000
  });

  const setSplitM = useMutation({
    mutationFn: async (p: number) => updateABSplit(p),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["metrics-summary"] });
      await qc.invalidateQueries({ queryKey: ["ab-summary"] });
    }
  });

  const resetM = useMutation({
    mutationFn: resetABTest,
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["ab-summary"] });
      await qc.invalidateQueries({ queryKey: ["ab-history"] });
    }
  });

  const v1 = abQ.data?.v1 ?? null;
  const v2 = abQ.data?.v2 ?? null;

  const stats = v1 && v2 ? winnerFromSummary(v1, v2) : { winner: "inconclusive" as const, p: null };
  const significant = stats.p != null && stats.p < 0.05;

  const history = buildHistory(historyQ.data);
  const accuracyBars =
    v1 && v2
      ? [
          {
            name: "Accuracy",
            v1: v1.accuracy ?? 0,
            v2: v2.accuracy ?? 0
          }
        ]
      : [];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <div className="text-lg font-semibold text-zinc-50">A/B test</div>
        <div className="mt-1 text-sm text-zinc-400">
          Deterministic routing by user_id with Redis-backed aggregation.
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <MetricCard
          title="v1 (Production)"
          value={String(v1?.n_requests ?? 0)}
          delta={v1?.avg_latency_ms}
          deltaLabel="avg latency (ms)"
          color={stats.winner === "v1" && significant ? "success" : "default"}
          icon={stats.winner === "v1" && significant ? Trophy : undefined}
          loading={abQ.isLoading}
          description="v1 is the production model. Requests are deterministically routed based on user_id."
        />
        <MetricCard
          title="v2 (Staging)"
          value={String(v2?.n_requests ?? 0)}
          delta={v2?.avg_latency_ms}
          deltaLabel="avg latency (ms)"
          color={stats.winner === "v2" && significant ? "success" : "default"}
          icon={stats.winner === "v2" && significant ? Trophy : undefined}
          loading={abQ.isLoading}
          description="v2 is the staging model used for live A/B evaluation."
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
          <div className="mb-3 flex items-center justify-between">
            <div className="text-sm font-medium text-zinc-100">Accuracy comparison</div>
            <div className="text-xs text-zinc-400">
              {stats.p == null ? (
                <span>p-value: —</span>
              ) : (
                <span>
                  p={stats.p.toFixed(4)}{" "}
                  <span
                    className={clsx(
                      "ml-2 rounded border px-2 py-0.5",
                      significant
                        ? "border-emerald-700/60 bg-emerald-900/20 text-emerald-200"
                        : "border-zinc-800 bg-zinc-950 text-zinc-300"
                    )}
                  >
                    {significant ? "Statistically significant" : "Not significant"}
                  </span>
                </span>
              )}
            </div>
          </div>

          <div className="h-[260px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={accuracyBars}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis dataKey="name" stroke="#a1a1aa" />
                <YAxis domain={[0, 1]} stroke="#a1a1aa" />
                <Tooltip
                  contentStyle={{
                    background: "#09090b",
                    border: "1px solid #27272a",
                    borderRadius: 8
                  }}
                  formatter={(val) => [Number(val).toFixed(3), "accuracy"]}
                />
                <Bar dataKey="v1" fill="#38bdf8" />
                <Bar dataKey="v2" fill="#a78bfa" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="mt-3 text-xs text-zinc-500">
            {stats.p == null
              ? "Interpretation: need more labeled outcomes to run a significance test."
              : significant
                ? `Interpretation: p < 0.05, winner = ${stats.winner}.`
                : "Interpretation: p ≥ 0.05, result is inconclusive."}
          </div>
        </div>

        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
          <div className="mb-3 flex items-center justify-between">
            <div className="text-sm font-medium text-zinc-100">Traffic split</div>
            <div className="text-xs text-zinc-400">{split}% to v2</div>
          </div>
          <input
            type="range"
            min={0}
            max={100}
            value={split}
            onChange={(e) => setSplit(Number(e.target.value))}
            onMouseUp={() => setSplitM.mutate(split)}
            onKeyUp={() => setSplitM.mutate(split)}
            className="w-full"
          />
          <div className="mt-3 flex items-center justify-between">
            <div className="text-xs text-zinc-500">0 → all v1</div>
            <div className="text-xs text-zinc-500">100 → all v2</div>
          </div>

          <div className="mt-5 flex items-center justify-end">
            <Dialog.Root open={confirmOpen} onOpenChange={setConfirmOpen}>
              <Dialog.Trigger asChild>
                <button
                  type="button"
                  className="rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm text-zinc-300 transition hover:bg-zinc-900"
                >
                  Reset counters
                </button>
              </Dialog.Trigger>
              <Dialog.Portal>
                <Dialog.Overlay className="fixed inset-0 bg-black/70" />
                <Dialog.Content className="fixed left-1/2 top-1/2 w-[92vw] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-lg border border-zinc-800 bg-zinc-950 p-4 shadow-xl">
                  <Dialog.Title className="text-sm font-medium text-zinc-100">
                    Reset A/B counters?
                  </Dialog.Title>
                  <div className="mt-2 text-sm text-zinc-400">
                    This clears Redis aggregates for v1 and v2 (requests, latency, confidence, and accuracy lists).
                  </div>
                  <div className="mt-4 flex justify-end gap-2">
                    <Dialog.Close asChild>
                      <button
                        type="button"
                        className="rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm text-zinc-300 hover:bg-zinc-900"
                      >
                        Cancel
                      </button>
                    </Dialog.Close>
                    <button
                      type="button"
                      onClick={async () => {
                        await resetM.mutateAsync();
                        setConfirmOpen(false);
                      }}
                      className="rounded-md border border-rose-700/60 bg-rose-900/20 px-3 py-2 text-sm text-rose-200 hover:bg-rose-900/30"
                    >
                      Confirm reset
                    </button>
                  </div>
                </Dialog.Content>
              </Dialog.Portal>
            </Dialog.Root>
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
        <div className="mb-3 text-sm font-medium text-zinc-100">Request history (24h)</div>
        <div className="h-[260px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={history}>
              <defs>
                <linearGradient id="v1Fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.45} />
                  <stop offset="100%" stopColor="#38bdf8" stopOpacity={0.05} />
                </linearGradient>
                <linearGradient id="v2Fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#a78bfa" stopOpacity={0.45} />
                  <stop offset="100%" stopColor="#a78bfa" stopOpacity={0.05} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis dataKey="hour" stroke="#a1a1aa" tick={{ fontSize: 12 }} minTickGap={18} />
              <YAxis stroke="#a1a1aa" tick={{ fontSize: 12 }} />
              <Tooltip
                contentStyle={{
                  background: "#09090b",
                  border: "1px solid #27272a",
                  borderRadius: 8
                }}
              />
              <Area type="monotone" dataKey="v1" stackId="1" stroke="#38bdf8" fill="url(#v1Fill)" />
              <Area type="monotone" dataKey="v2" stackId="1" stroke="#a78bfa" fill="url(#v2Fill)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
