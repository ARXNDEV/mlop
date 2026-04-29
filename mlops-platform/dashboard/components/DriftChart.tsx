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

export default function DriftChart({
  data,
  threshold
}: {
  data: DriftPoint[];
  threshold: number;
}) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
      <div className="mb-3 text-sm font-medium text-zinc-100">
        Drift score (24h)
      </div>
      <div className="h-[280px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
            <XAxis
              dataKey="time"
              stroke="#a1a1aa"
              tick={{ fontSize: 12 }}
              minTickGap={18}
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
            />
            <ReferenceLine
              y={threshold}
              stroke="#fb7185"
              strokeDasharray="6 6"
            />
            <Line
              type="monotone"
              dataKey="drift_score"
              stroke="#38bdf8"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
