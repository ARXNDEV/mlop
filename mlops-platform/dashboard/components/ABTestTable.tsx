"use client";

import clsx from "clsx";

import type { ABTestSummary } from "@/lib/types";

export default function ABTestTable({
  v1,
  v2,
  winner
}: {
  v1: ABTestSummary | null;
  v2: ABTestSummary | null;
  winner: { winner: string; p_value: number | null } | null;
}) {
  const rows = [
    {
      label: "Requests",
      v1: v1?.n_requests ?? 0,
      v2: v2?.n_requests ?? 0
    },
    {
      label: "Avg latency (ms)",
      v1: (v1?.avg_latency_ms ?? 0).toFixed(2),
      v2: (v2?.avg_latency_ms ?? 0).toFixed(2)
    },
    {
      label: "Avg confidence",
      v1: (v1?.avg_confidence ?? 0).toFixed(3),
      v2: (v2?.avg_confidence ?? 0).toFixed(3)
    },
    {
      label: "Accuracy",
      v1: v1?.accuracy == null ? "—" : v1.accuracy.toFixed(3),
      v2: v2?.accuracy == null ? "—" : v2.accuracy.toFixed(3)
    }
  ];

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="text-sm font-medium text-zinc-100">A/B test</div>
        <div className="text-xs text-zinc-400">
          Winner:{" "}
          <span
            className={clsx("font-medium", {
              "text-emerald-300": winner?.winner === "v2",
              "text-sky-300": winner?.winner === "v1",
              "text-zinc-400": winner?.winner === "inconclusive"
            })}
          >
            {winner?.winner ?? "—"}
          </span>
          {winner?.p_value == null ? null : (
            <span className="ml-2 text-zinc-500">
              p={winner.p_value.toFixed(4)}
            </span>
          )}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-left text-sm">
          <thead>
            <tr className="border-b border-zinc-800 text-xs text-zinc-400">
              <th className="py-2 pr-4 font-medium">Metric</th>
              <th className="py-2 pr-4 font-medium">v1 (Production)</th>
              <th className="py-2 pr-4 font-medium">v2 (Staging)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.label} className="border-b border-zinc-900">
                <td className="py-2 pr-4 text-zinc-300">{r.label}</td>
                <td className="py-2 pr-4 text-zinc-50">{r.v1}</td>
                <td className="py-2 pr-4 text-zinc-50">{r.v2}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
