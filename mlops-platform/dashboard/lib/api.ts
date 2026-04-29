import type {
  ABHistory,
  ABTestSummary,
  DriftFeature,
  DriftPoint,
  Experiment,
  MetricsSummary,
  RetrainEvent
} from "@/lib/types";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(message: string, status: number, detail: string) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const MLFLOW_URL = process.env.NEXT_PUBLIC_MLFLOW_URL || "http://localhost:5000";

function isDev(): boolean {
  return process.env.NODE_ENV !== "production";
}

async function requestJson<TResponse>(
  path: string,
  init: RequestInit & { method?: string } = {}
): Promise<TResponse> {
  const url = `${API_URL}${path}`;
  const method = init.method ?? "GET";

  if (isDev()) {
    console.info("[api]", method, url);
  }

  const res = await fetch(url, { ...init, cache: "no-store" });
  const text = await res.text();

  if (isDev()) {
    console.info("[api]", method, url, res.status);
  }

  if (!res.ok) {
    throw new ApiError("Request failed", res.status, text || `HTTP ${res.status}`);
  }

  return JSON.parse(text) as TResponse;
}

async function requestVoid(path: string, init: RequestInit): Promise<void> {
  await requestJson<Record<string, unknown>>(path, init);
}

/** Fetches a dashboard-friendly metric snapshot from the API. */
export function fetchMetricsSummary(): Promise<MetricsSummary> {
  return requestJson<MetricsSummary>("/metrics/summary");
}

/** Fetches the current A/B summary (v1 + v2) from the API. */
export async function fetchABTestSummary(): Promise<{ v1: ABTestSummary; v2: ABTestSummary }> {
  const res = await requestJson<ABTestSummary[]>("/ab-test/summary");
  const v1 = res.find((s) => s.version === "v1");
  const v2 = res.find((s) => s.version === "v2");
  if (!v1 || !v2) {
    throw new ApiError("Invalid response", 500, "Missing v1/v2 summaries");
  }
  return { v1, v2 };
}

/** Fetches A/B request history (hourly, last 24h). */
export function fetchABHistory(): Promise<ABHistory> {
  return requestJson<ABHistory>("/ab-test/history");
}

/** Updates the A/B split percent (0-100) at runtime. */
export async function updateABSplit(percent: number): Promise<void> {
  await requestVoid("/ab-test/split", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ split_percent: percent })
  });
}

/** Resets all A/B counters in Redis (admin). */
export async function resetABTest(): Promise<void> {
  await requestVoid("/ab-test/reset", { method: "POST" });
}

/** Triggers a hot reload of models in the API. */
export async function triggerReload(): Promise<void> {
  await requestVoid("/admin/reload", { method: "POST" });
}

/** Fetches drift score history from the API (bucketed hourly). */
export function fetchDriftHistory(hours: number): Promise<DriftPoint[]> {
  const qs = new URLSearchParams({ hours: String(hours) });
  return requestJson<DriftPoint[]>(`/metrics/drift/history?${qs.toString()}`);
}

/** Fetches feature-level drift details (PSI, flags, and trends). */
export function fetchDriftFeatures(): Promise<DriftFeature[]> {
  return requestJson<DriftFeature[]>("/metrics/drift/features");
}

/** Fetches the latest retrain trigger events. */
export function fetchRetrainEvents(): Promise<RetrainEvent[]> {
  return requestJson<RetrainEvent[]>("/metrics/retrain/events");
}

/** Fetches MLflow experiments/runs for the dashboard experiments page. */
export async function fetchExperiments(): Promise<Experiment[]> {
  const url = `${MLFLOW_URL}/api/2.0/mlflow/runs/search`;
  const payload = {
    experiment_ids: [],
    filter: "",
    max_results: 50,
    order_by: ["attributes.start_time DESC"]
  };

  if (isDev()) {
    console.info("[mlflow]", "POST", url);
  }

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store"
  });
  const jsonText = await res.text();
  if (!res.ok) {
    throw new ApiError("MLflow request failed", res.status, jsonText || `HTTP ${res.status}`);
  }

  const parsed: unknown = JSON.parse(jsonText);
  if (!parsed || typeof parsed !== "object") {
    throw new ApiError("MLflow response invalid", 500, "Invalid JSON");
  }

  const runs = (parsed as { runs?: unknown }).runs;
  if (!Array.isArray(runs)) return [];

  return runs.map((r): Experiment => {
    const run = r as {
      info?: { run_id?: string; start_time?: number; status?: string };
      data?: {
        metrics?: Array<{ key: string; value: number }>;
        params?: Array<{ key: string; value: string }>;
        tags?: Array<{ key: string; value: string }>;
      };
    };

    const metrics: Record<string, number> = {};
    for (const m of run.data?.metrics ?? []) {
      metrics[m.key] = Number(m.value);
    }
    const params: Record<string, string> = {};
    for (const p of run.data?.params ?? []) {
      params[p.key] = String(p.value);
    }
    const tags: Record<string, string> = {};
    for (const t of run.data?.tags ?? []) {
      tags[t.key] = String(t.value);
    }

    return {
      run_id: String(run.info?.run_id ?? ""),
      start_time: Number(run.info?.start_time ?? 0),
      status: String(run.info?.status ?? ""),
      metrics,
      params,
      tags
    };
  });
}
