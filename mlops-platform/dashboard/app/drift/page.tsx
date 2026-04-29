"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as Dialog from "@radix-ui/react-dialog";
import clsx from "clsx";
import { ArrowDownRight, ArrowUpRight, RotateCcw } from "lucide-react";
import { useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import DriftChart from "@/components/DriftChart";
import MetricCard from "@/components/MetricCard";
import {
  fetchDriftFeatures,
  fetchDriftHistory,
  fetchMetricsSummary,
  fetchRetrainEvents,
  triggerReload
} from "@/lib/api";
import type { DriftFeature, DriftPoint, RetrainEvent } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function driftDelta(points: DriftPoint[] | undefined): number | null {
  if (!points || points.length < 2) return null;
  const a = points[points.length - 2].drift_score;
  const b = points[points.length - 1].drift_score;
  return b - a;
}

function toLocal(ts: number): string {
  return new Date(ts).toLocaleString();
}

/** Drift monitoring page (feature PSI, timeline, retrain log, and report embed). */
export default function DriftPage() {
  const qc = useQueryClient();
  const [confirmOpen, setConfirmOpen] = useState<boolean>(false);

  const metricsQ = useQuery({
    queryKey: ["metrics-summary"],
    queryFn: fetchMetricsSummary,
    refetchInterval: 30_000
  });

  const modelName =
    Object.keys(metricsQ.data?.model_drift_score ?? {})[0] ?? "income-classifier";
  const currentDrift = metricsQ.data?.model_drift_score?.[modelName] ?? 0;
  const driftColor =
    currentDrift < 0.1 ? "success" : currentDrift < 0.2 ? "warning" : "danger";

  const history7dQ = useQuery({
    queryKey: ["drift-history", 168],
    queryFn: () => fetchDriftHistory(168),
    refetchInterval: 60_000
  });

  const historyDelta = driftDelta(history7dQ.data);
  const DeltaIcon = historyDelta != null && historyDelta >= 0 ? ArrowUpRight : ArrowDownRight;

  const featuresQ = useQuery({
    queryKey: ["drift-features"],
    queryFn: fetchDriftFeatures,
    refetchInterval: 60_000
  });

  const eventsQ = useQuery({
    queryKey: ["retrain-events"],
    queryFn: fetchRetrainEvents,
    refetchInterval: 60_000
  });

  const reloadM = useMutation({
    mutationFn: triggerReload,
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["metrics-summary"] });
      await qc.invalidateQueries({ queryKey: ["retrain-events"] });
    }
  });

  const features = [...(featuresQ.data ?? [])].sort((a, b) => b.psi - a.psi);
  const last5 = (eventsQ.data ?? []).slice(0, 5);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <div className="text-lg font-semibold text-zinc-50">Drift</div>
        <div className="mt-1 text-sm text-zinc-400">
          Feature-level monitoring and retrain signals surfaced from Evidently and the drift check DAG.
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <MetricCard
          title="Current drift score"
          value={currentDrift.toFixed(3)}
          delta={historyDelta ?? undefined}
          deltaLabel="Δ vs previous hour"
          color={driftColor}
          icon={DeltaIcon}
          loading={metricsQ.isLoading}
          description="Drift score is updated by the drift check DAG and exposed as a Prometheus gauge."
        />

        <MetricCard
          title="Retrain threshold"
          value={"0.150"}
          color="default"
          icon={RotateCcw}
          loading={false}
          description="If drift exceeds the threshold, the drift check DAG triggers retraining."
        />

        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
          <div className="text-xs text-zinc-400">Manual retrain</div>
          <div className="mt-2 text-sm text-zinc-300">
            Hot reloads models from MLflow registry and records a retrain event.
          </div>

          <div className="mt-4">
            <Dialog.Root open={confirmOpen} onOpenChange={setConfirmOpen}>
              <Dialog.Trigger asChild>
                <button
                  type="button"
                  className="rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 transition hover:bg-zinc-800"
                >
                  Trigger reload
                </button>
              </Dialog.Trigger>
              <Dialog.Portal>
                <Dialog.Overlay className="fixed inset-0 bg-black/70" />
                <Dialog.Content className="fixed left-1/2 top-1/2 w-[92vw] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-lg border border-zinc-800 bg-zinc-950 p-4 shadow-xl">
                  <Dialog.Title className="text-sm font-medium text-zinc-100">
                    Trigger model reload?
                  </Dialog.Title>
                  <div className="mt-2 text-sm text-zinc-400">
                    This calls <span className="font-mono">POST /admin/reload</span> on the API.
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
                        await reloadM.mutateAsync();
                        setConfirmOpen(false);
                      }}
                      className="rounded-md border border-emerald-700/60 bg-emerald-900/20 px-3 py-2 text-sm text-emerald-200 hover:bg-emerald-900/30"
                    >
                      Confirm
                    </button>
                  </div>
                </Dialog.Content>
              </Dialog.Portal>
            </Dialog.Root>
          </div>
          <div className="mt-2 text-xs text-zinc-500">
            {reloadM.isPending ? "Reloading…" : null}
          </div>
        </div>
      </div>

      <DriftChart
        data={history7dQ.data ?? []}
        threshold={0.15}
        loading={history7dQ.isLoading}
      />

      <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
        <div className="mb-3 text-sm font-medium text-zinc-100">Feature drift (PSI)</div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead>
              <tr className="border-b border-zinc-800 text-xs text-zinc-400">
                <th className="py-2 pr-3 font-medium">Feature</th>
                <th className="py-2 pr-3 font-medium">PSI</th>
                <th className="py-2 pr-3 font-medium">Drift detected</th>
                <th className="py-2 pr-3 font-medium">Trend</th>
              </tr>
            </thead>
            <tbody>
              {features.map((f) => (
                <FeatureRow key={f.feature} feature={f} />
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
          <div className="mb-3 text-sm font-medium text-zinc-100">Drift timeline (7d)</div>
          <div className="h-[260px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history7dQ.data ?? []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis
                  dataKey="timestamp"
                  stroke="#a1a1aa"
                  tick={{ fontSize: 12 }}
                  minTickGap={18}
                  tickFormatter={(v) => {
                    const d = new Date(Number(v));
                    const m = String(d.getMonth() + 1).padStart(2, "0");
                    const day = String(d.getDate()).padStart(2, "0");
                    return `${m}/${day}`;
                  }}
                />
                <YAxis domain={[0, 1]} stroke="#a1a1aa" tick={{ fontSize: 12 }} />
                <Tooltip
                  contentStyle={{
                    background: "#09090b",
                    border: "1px solid #27272a",
                    borderRadius: 8
                  }}
                  labelFormatter={(label) => new Date(Number(label)).toLocaleString()}
                  formatter={(val) => [Number(val).toFixed(3), "drift_score"]}
                />
                <Line type="monotone" dataKey="drift_score" stroke="#38bdf8" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
          <div className="mb-3 text-sm font-medium text-zinc-100">Retrain trigger log</div>
          <div className="flex flex-col gap-2">
            {last5.length === 0 ? (
              <div className="text-sm text-zinc-500">No events yet.</div>
            ) : (
              last5.map((e) => <EventRow key={`${e.timestamp}-${e.reason}`} event={e} />)
            )}
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
        <div className="mb-3 text-sm font-medium text-zinc-100">Latest Evidently report</div>
        <iframe
          src={`${API_URL}/metrics/drift/report/latest`}
          className="h-[520px] w-full rounded-md border border-zinc-800 bg-zinc-950"
        />
      </div>
    </div>
  );
}

function FeatureRow({ feature }: { feature: DriftFeature }) {
  const trend = feature.trend.map((v, idx) => ({ idx, v }));
  return (
    <tr className="border-b border-zinc-900">
      <td className="py-2 pr-3 font-mono text-xs text-zinc-300">{feature.feature}</td>
      <td className="py-2 pr-3 text-zinc-50">{feature.psi.toFixed(3)}</td>
      <td className="py-2 pr-3">
        <span
          className={clsx("rounded border px-2 py-0.5 text-xs", {
            "border-rose-700/60 bg-rose-900/20 text-rose-200": feature.drift_detected,
            "border-emerald-700/60 bg-emerald-900/20 text-emerald-200": !feature.drift_detected
          })}
        >
          {feature.drift_detected ? "true" : "false"}
        </span>
      </td>
      <td className="py-2 pr-3">
        <div className="h-10 w-40">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={trend}>
              <Line type="monotone" dataKey="v" stroke="#a78bfa" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </td>
    </tr>
  );
}

function EventRow({ event }: { event: RetrainEvent }) {
  return (
    <div className="rounded-md border border-zinc-800 bg-zinc-950 p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm text-zinc-100">{event.reason}</div>
        <div className="text-xs text-zinc-500">{toLocal(event.timestamp)}</div>
      </div>
      <div className="mt-1 text-xs text-zinc-500">
        run_id: <span className="font-mono">{event.run_id ?? "—"}</span>
      </div>
    </div>
  );
}
