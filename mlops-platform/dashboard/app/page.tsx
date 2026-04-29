"use client";

import { useQuery } from "@tanstack/react-query";

import ABTestTable from "@/components/ABTestTable";
import DriftChart from "@/components/DriftChart";
import MetricCard from "@/components/MetricCard";
import { fetchABSummary, fetchABWinner, fetchMetricsSummary } from "@/lib/api";
import type { DriftPoint } from "@/lib/types";

async function fetchDriftHistory(modelName: string): Promise<DriftPoint[]> {
  const end = Math.floor(Date.now() / 1000);
  const start = end - 24 * 60 * 60;
  const url = new URL("http://localhost:9090/api/v1/query_range");
  url.searchParams.set("query", `model_drift_score{model_name="${modelName}"}`);
  url.searchParams.set("start", String(start));
  url.searchParams.set("end", String(end));
  url.searchParams.set("step", "3600");

  const res = await fetch(url.toString(), { cache: "no-store" });
  if (!res.ok) return [];
  const json = (await res.json()) as any;
  const series = json?.data?.result?.[0]?.values ?? [];
  return series.map((v: [number, string]) => {
    const d = new Date(v[0] * 1000);
    const hh = String(d.getHours()).padStart(2, "0");
    return { time: `${hh}:00`, drift_score: Number(v[1]) };
  });
}

export default function OverviewPage() {
  const metricsQ = useQuery({
    queryKey: ["metrics-summary"],
    queryFn: fetchMetricsSummary,
    refetchInterval: 30_000
  });

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

  const driftKey = Object.keys(metricsQ.data?.model_drift_score ?? {})[0] ?? "income-classifier";
  const driftHistoryQ = useQuery({
    queryKey: ["drift-history", driftKey],
    queryFn: () => fetchDriftHistory(driftKey),
    refetchInterval: 30_000
  });

  const now = new Date();

  const accuracy = metricsQ.data?.model_accuracy?.v1 ?? 0;
  const drift = metricsQ.data?.model_drift_score?.[driftKey] ?? 0;
  const p95 = metricsQ.data?.p95_latency_ms ?? 0;
  const active = metricsQ.data?.active_model_version?.production_version
    ? `prod:${metricsQ.data.active_model_version.production_version} / stag:${metricsQ.data.active_model_version.staging_version ?? ""}`
    : "—";

  const driftTone = drift < 0.1 ? "good" : drift < 0.2 ? "warn" : "bad";
  const driftLabel =
    drift < 0.1 ? "Healthy" : drift < 0.2 ? "Slight drift" : "Significant drift";

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          title="Live accuracy"
          value={`${accuracy.toFixed(3)}`}
          footer="v1 gauge from API"
          tone="neutral"
        />
        <MetricCard
          title="Drift score"
          value={`${drift.toFixed(3)}`}
          footer={driftLabel}
          tone={driftTone}
        />
        <MetricCard
          title="P95 latency"
          value={`${p95.toFixed(0)} ms`}
          footer="HTTP middleware histogram"
          tone="neutral"
        />
        <MetricCard
          title="Active model"
          value={active}
          footer="Production / Staging"
          tone="neutral"
        />
      </div>

      <DriftChart data={driftHistoryQ.data ?? []} threshold={0.15} />

      <ABTestTable
        v1={abQ.data?.v1 ?? null}
        v2={abQ.data?.v2 ?? null}
        winner={winnerQ.data ?? null}
      />

      <div className="pt-2 text-xs text-zinc-500">
        Last updated: {now.toLocaleString()}
      </div>
    </div>
  );
}
