"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import type { DriftPoint } from "@/lib/types";

/** Drift line chart with threshold labeling, gradient styling, and loading skeleton. */
export default function DriftChart({
  data,
  threshold,
  loading = false
}: {
  data: DriftPoint[];
  threshold: number;
  loading?: boolean;
}) {
  const crossed = data.some((p) => p.drift_score >= threshold);
  if (loading) {
    return (
      <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
        <div className="mb-3 h-4 w-40 animate-pulse rounded bg-zinc-900" />
        <div className="h-[280px] w-full animate-pulse rounded bg-zinc-900" />
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
      <div className="mb-3 text-sm font-medium text-zinc-100">Drift score</div>
      <div className="h-[280px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <defs>
              <linearGradient id="driftStroke" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={crossed ? "#fb7185" : "#38bdf8"} stopOpacity={1} />
                <stop offset="45%" stopColor="#38bdf8" stopOpacity={1} />
                <stop offset="100%" stopColor="#38bdf8" stopOpacity={1} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
            <XAxis
              dataKey="timestamp"
              stroke="#a1a1aa"
              tick={{ fontSize: 12 }}
              minTickGap={18}
              tickFormatter={(v) => {
                const d = new Date(Number(v));
                const hh = String(d.getHours()).padStart(2, "0");
                const mm = String(d.getMinutes()).padStart(2, "0");
                return `${hh}:${mm}`;
              }}
            />
            <YAxis
              domain={[0, 1]}
              stroke="#a1a1aa"
              tick={{ fontSize: 12 }}
              tickFormatter={(v) => Number(v).toFixed(2)}
            />
            <Tooltip
              contentStyle={{
                background: "#09090b",
                border: "1px solid #27272a",
                borderRadius: 8
              }}
              labelStyle={{ color: "#e4e4e7" }}
              itemStyle={{ color: "#e4e4e7" }}
              labelFormatter={(label) => new Date(Number(label)).toLocaleString()}
              formatter={(val) => [Number(val).toFixed(3), "drift_score"]}
            />
            <ReferenceLine
              y={threshold}
              stroke="#fb7185"
              strokeDasharray="6 6"
              label={{
                value: "Retrain threshold",
                position: "insideTopRight",
                fill: "#fb7185",
                fontSize: 12
              }}
            />
            <Line
              type="monotone"
              dataKey="drift_score"
              stroke={crossed ? "url(#driftStroke)" : "#38bdf8"}
              strokeWidth={2}
              dot={false}
              isAnimationActive
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
