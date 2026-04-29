"use client";

import { useQuery } from "@tanstack/react-query";

import DriftChart from "@/components/DriftChart";
import MetricCard from "@/components/MetricCard";
import { fetchMetricsSummary } from "@/lib/api";
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

export default function DriftPage() {
  const metricsQ = useQuery({
    queryKey: ["metrics-summary"],
    queryFn: fetchMetricsSummary,
    refetchInterval: 30_000
  });

  const driftKey = Object.keys(metricsQ.data?.model_drift_score ?? {})[0] ?? "income-classifier";
  const drift = metricsQ.data?.model_drift_score?.[driftKey] ?? 0;
  const share = drift;

  const driftTone = drift < 0.1 ? "good" : drift < 0.2 ? "warn" : "bad";

  const historyQ = useQuery({
    queryKey: ["drift-history", driftKey],
    queryFn: () => fetchDriftHistory(driftKey),
    refetchInterval: 30_000
  });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <div className="text-lg font-semibold text-zinc-50">Drift</div>
        <div className="mt-1 text-sm text-zinc-400">
          Evidently report runs in Airflow; the API exposes the latest drift score as a Prometheus gauge.
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard
          title="Latest drift score"
          value={drift.toFixed(3)}
          footer={drift < 0.15 ? "Below retrain threshold" : "Above retrain threshold"}
          tone={driftTone}
        />
        <MetricCard
          title="Share drifted"
          value={share.toFixed(3)}
          footer="Derived from drift gauge"
          tone="neutral"
        />
        <MetricCard
          title="Threshold"
          value={"0.150"}
          footer="DRIFT_THRESHOLD"
          tone="neutral"
        />
      </div>

      <DriftChart data={historyQ.data ?? []} threshold={0.15} />
    </div>
  );
}
