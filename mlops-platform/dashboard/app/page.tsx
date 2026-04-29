"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, Gauge, LineChart, Shield } from "lucide-react";

import ABTestTable from "@/components/ABTestTable";
import DriftChart from "@/components/DriftChart";
import MetricCard from "@/components/MetricCard";
import { fetchABTestSummary, fetchDriftHistory, fetchMetricsSummary } from "@/lib/api";

/** Overview dashboard page (metrics strip, drift chart, and A/B summary). */
export default function OverviewPage() {
  const metricsQ = useQuery({
    queryKey: ["metrics-summary"],
    queryFn: fetchMetricsSummary,
    refetchInterval: 30_000
  });

  const abQ = useQuery({
    queryKey: ["ab-summary"],
    queryFn: fetchABTestSummary,
    refetchInterval: 30_000
  });

  const driftHistoryQ = useQuery({
    queryKey: ["drift-history", 24],
    queryFn: () => fetchDriftHistory(24),
    refetchInterval: 30_000
  });

  const now = new Date();

  const accuracy = metricsQ.data?.model_accuracy?.v1 ?? 0;
  const modelName =
    Object.keys(metricsQ.data?.model_drift_score ?? {})[0] ?? "income-classifier";
  const drift = metricsQ.data?.model_drift_score?.[modelName] ?? 0;
  const p95 = metricsQ.data?.p95_latency_ms ?? 0;
  const active = metricsQ.data?.active_model_version?.production_version
    ? `prod:${metricsQ.data.active_model_version.production_version} / stag:${metricsQ.data.active_model_version.staging_version ?? ""}`
    : "—";

  const driftLabel =
    drift < 0.1 ? "Healthy" : drift < 0.2 ? "Slight drift" : "Significant drift";

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          title="Live accuracy"
          value={accuracy.toFixed(3)}
          color={accuracy >= 0.85 ? "success" : accuracy >= 0.75 ? "warning" : "danger"}
          icon={Activity}
          loading={metricsQ.isLoading}
          description="model_accuracy gauge exposed by the API."
        />
        <MetricCard
          title="Drift score"
          value={drift.toFixed(3)}
          color={drift < 0.1 ? "success" : drift < 0.2 ? "warning" : "danger"}
          icon={LineChart}
          loading={metricsQ.isLoading}
          description={`Latest drift score for ${modelName}. ${driftLabel}.`}
        />
        <MetricCard
          title="P95 latency"
          value={p95.toFixed(0)}
          unit="ms"
          color={p95 <= 200 ? "success" : p95 <= 500 ? "warning" : "danger"}
          icon={Gauge}
          loading={metricsQ.isLoading}
          description="p95 derived from http_request_duration_ms histogram."
        />
        <MetricCard
          title="Active model"
          value={active}
          color="default"
          icon={Shield}
          loading={metricsQ.isLoading}
          description="Versions loaded from MLflow registry (Production and Staging)."
        />
      </div>

      <DriftChart data={driftHistoryQ.data ?? []} threshold={0.15} loading={driftHistoryQ.isLoading} />

      <ABTestTable
        v1={abQ.data?.v1 ?? null}
        v2={abQ.data?.v2 ?? null}
      />

      <div className="pt-2 text-xs text-zinc-500">
        Last updated: {now.toLocaleString()}
      </div>
    </div>
  );
}
