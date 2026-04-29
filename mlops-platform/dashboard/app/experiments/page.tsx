import ExperimentsTable from "@/components/ExperimentsTable";
import type { MlflowRun } from "@/lib/types";

async function fetchRuns(): Promise<MlflowRun[]> {
  const url = "http://mlflow:5000/api/2.0/mlflow/runs/search";

  const payload = {
    experiment_ids: [],
    filter: "",
    max_results: 50,
    order_by: ["attributes.start_time DESC"]
  };

  let res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store"
  });
  if (!res.ok) {
    res = await fetch(url, { method: "GET", cache: "no-store" });
  }
  if (!res.ok) return [];

  const json = (await res.json()) as any;
  const runs = (json?.runs ?? []) as any[];

  return runs.map((r) => {
    const metrics: Record<string, number> = {};
    for (const m of r?.data?.metrics ?? []) {
      metrics[m.key] = Number(m.value);
    }
    const params: Record<string, string> = {};
    for (const p of r?.data?.params ?? []) {
      params[p.key] = String(p.value);
    }
    const tags: Record<string, string> = {};
    for (const t of r?.data?.tags ?? []) {
      tags[t.key] = String(t.value);
    }
    return {
      run_id: String(r?.info?.run_id ?? ""),
      start_time: Number(r?.info?.start_time ?? 0),
      status: String(r?.info?.status ?? ""),
      metrics,
      params,
      tags
    };
  });
}

export default async function ExperimentsPage() {
  const runs = await fetchRuns();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <div className="text-lg font-semibold text-zinc-50">Experiments</div>
        <div className="mt-1 text-sm text-zinc-400">
          Browse MLflow runs and compare key metrics.
        </div>
      </div>
      <ExperimentsTable runs={runs} />
    </div>
  );
}
