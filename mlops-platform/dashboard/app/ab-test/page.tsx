"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useState } from "react";

import ABTestTable from "@/components/ABTestTable";
import { fetchABHistory, fetchABSummary, fetchABWinner } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ABTestPage() {
  const qc = useQueryClient();
  const [split, setSplit] = useState<number>(20);

  const abQ = useQuery({
    queryKey: ["ab-summary"],
    queryFn: fetchABSummary,
    refetchInterval: 30_000
  });

  const winnerQ = useQuery({
    queryKey: ["ab-winner"],
    queryFn: fetchABWinner,
    refetchInterval: 30_000
  });

  const historyQ = useQuery({
    queryKey: ["ab-history"],
    queryFn: fetchABHistory,
    refetchInterval: 30_000
  });

  const setSplitM = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${API_URL}/ab-test/split`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ split_percent: split })
      });
      if (!res.ok) throw new Error(`split update failed: ${res.status}`);
      return res.json();
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["metrics-summary"] });
    }
  });

  const resetM = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${API_URL}/ab-test/reset`, { method: "POST" });
      if (!res.ok) throw new Error(`reset failed: ${res.status}`);
      return res.json();
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["ab-summary"] });
      await qc.invalidateQueries({ queryKey: ["ab-history"] });
      await qc.invalidateQueries({ queryKey: ["ab-winner"] });
    }
  });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <div className="text-lg font-semibold text-zinc-50">A/B test</div>
        <div className="mt-1 text-sm text-zinc-400">
          Deterministic routing by user_id with Redis-backed aggregation.
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-zinc-800 bg-zinc-950 p-4">
        <div className="flex flex-col gap-1">
          <div className="text-xs text-zinc-400">Split to v2 (%)</div>
          <input
            type="number"
            min={0}
            max={100}
            value={split}
            onChange={(e) => setSplit(Number(e.target.value))}
            className="w-40 rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm text-zinc-100"
          />
        </div>
        <button
          type="button"
          onClick={() => setSplitM.mutate()}
          className="rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 transition hover:bg-zinc-800"
        >
          Update split
        </button>
        <button
          type="button"
          onClick={() => resetM.mutate()}
          className="rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm text-zinc-300 transition hover:bg-zinc-900"
        >
          Reset counters
        </button>
        <div className="ml-auto text-xs text-zinc-500">
          {setSplitM.isPending || resetM.isPending ? "Applying…" : null}
        </div>
      </div>

      <ABTestTable
        v1={abQ.data?.v1 ?? null}
        v2={abQ.data?.v2 ?? null}
        winner={winnerQ.data ?? null}
      />

      <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
        <div className="mb-3 text-sm font-medium text-zinc-100">24h request history</div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead>
              <tr className="border-b border-zinc-800 text-xs text-zinc-400">
                <th className="py-2 pr-3 font-medium">Hour (UTC)</th>
                <th className="py-2 pr-3 font-medium">v1</th>
                <th className="py-2 pr-3 font-medium">v2</th>
              </tr>
            </thead>
            <tbody>
              {(historyQ.data?.v1 ?? []).map((p, idx) => (
                <tr key={p.hour} className="border-b border-zinc-900">
                  <td className="py-2 pr-3 text-zinc-300">{p.hour}</td>
                  <td className="py-2 pr-3 text-zinc-50">{p.count}</td>
                  <td className="py-2 pr-3 text-zinc-50">
                    {historyQ.data?.v2?.[idx]?.count ?? 0}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
